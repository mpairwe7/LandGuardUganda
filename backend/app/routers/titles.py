"""Title issuance, lookup, revocation."""

from __future__ import annotations

import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.audit import audit_emit
from app.auth import AuthContext, Role, require_role
from app.blockchain.anchor_service import build_proof_for_event
from app.database import get_connection
from app.fraud.worker import enqueue_score
from app.models.titles import TitleIssueRequest, TitleRecord
from app.util.hashing import content_hash
from app.util.ids import make_title_no

router = APIRouter(prefix="/api/v1/titles", tags=["titles"])


def _read_title_row(title_no: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT title_no, parcel_id, issued_at, registrar_id, district_id, "
            "       content_hash, merkle_proof, revoked_at, revoke_reason "
            "FROM titles WHERE title_no = ?",
            (title_no,),
        ).fetchone()


def _attach_anchor(row) -> TitleRecord:
    # Pull anchor info via audit_events → anchors join, mirroring the
    # public verifier endpoint. The parcel_id fallback rescues legacy
    # seeded titles whose TITLE_ISSUED payload pre-dates the title_no
    # field (see app/bootstrap/seed.py).
    title_no = row[0]
    parcel_id = row[1]
    with get_connection() as conn:
        anchor = conn.execute(
            "SELECT a.tx_hash, a.block_number, a.status "
            "FROM anchors a "
            "WHERE a.batch_id = ("
            "  SELECT anchored_in FROM audit_events "
            "  WHERE event_type = 'TITLE_ISSUED' AND payload_json LIKE ? "
            "  ORDER BY seq DESC LIMIT 1"
            ")",
            (f'%"title_no": "{title_no}"%',),
        ).fetchone()
        if not anchor:
            anchor = conn.execute(
                "SELECT a.tx_hash, a.block_number, a.status "
                "FROM anchors a "
                "WHERE a.batch_id = ("
                "  SELECT anchored_in FROM audit_events "
                "  WHERE event_type = 'TITLE_ISSUED' AND payload_json LIKE ? "
                "  ORDER BY seq DESC LIMIT 1"
                ")",
                (f'%"parcel_id": "{parcel_id}"%',),
            ).fetchone()
    return TitleRecord(
        title_no=row[0],
        parcel_id=row[1],
        issued_at=float(row[2]),
        registrar_id=row[3],
        district_id=int(row[4]),
        content_hash=row[5],
        merkle_proof=json.loads(row[6]) if row[6] else None,
        revoked_at=float(row[7]) if row[7] is not None else None,
        revoke_reason=row[8],
        anchor_status=anchor[2] if anchor else "PENDING",
        tx_hash=anchor[0] if anchor else None,
        block_number=int(anchor[1]) if anchor and anchor[1] is not None else None,
    )


@router.post("/issue", response_model=TitleRecord, status_code=201)
async def issue_title(
    payload: TitleIssueRequest,
    ctx: Annotated[AuthContext, Depends(require_role(Role.REGISTRAR))],
) -> TitleRecord:
    with get_connection() as conn:
        parcel = conn.execute(
            "SELECT parcel_id, district_id, status FROM parcels WHERE parcel_id = ?",
            (payload.parcel_id,),
        ).fetchone()
        if not parcel:
            raise HTTPException(status_code=404, detail="parcel not found")
        if parcel[2] not in ("ACTIVE", "TRANSFERRED"):
            raise HTTPException(
                status_code=409,
                detail=f"parcel status is {parcel[2]} — cannot issue title",
            )
        owner = conn.execute(
            "SELECT id, full_name, kyc_status FROM owners WHERE id = ?",
            (payload.owner_id,),
        ).fetchone()
        if not owner:
            raise HTTPException(status_code=404, detail="owner not found")
        if owner[2] != "VERIFIED":
            raise HTTPException(
                status_code=409,
                detail="owner KYC not VERIFIED — run /owners/{id}/kyc first",
            )
        district_id = int(parcel[1])
        seq_row = conn.execute(
            "SELECT COUNT(*) FROM titles WHERE district_id = ?",
            (district_id,),
        ).fetchone()
        sequence = int(seq_row[0]) + 1
        title_no = make_title_no(district_id, sequence)
        canonical_payload = {
            "title_no": title_no,
            "parcel_id": payload.parcel_id,
            "owner_id": payload.owner_id,
            "owner_full_name": owner[1],
            "issued_at": time.time(),
            "registrar_id": ctx.user_id,
            "district_id": district_id,
        }
        c_hash = content_hash(canonical_payload)
        conn.execute(
            "INSERT INTO titles (title_no, parcel_id, issued_at, registrar_id, "
            " district_id, content_hash, merkle_proof) VALUES (?,?,?,?,?,?,?)",
            (
                title_no,
                payload.parcel_id,
                canonical_payload["issued_at"],
                ctx.user_id,
                district_id,
                c_hash,
                None,
            ),
        )
        conn.execute(
            "UPDATE parcels SET current_owner_id = ?, status = 'ACTIVE', updated_at = ? "
            "WHERE parcel_id = ?",
            (payload.owner_id, time.time(), payload.parcel_id),
        )
        conn.commit()

    audit_emit(
        event_type="TITLE_ISSUED",
        payload=canonical_payload,
        district_id=district_id,
        actor_user_id=ctx.user_id,
    )
    await enqueue_score(subject_type="TITLE", subject_id=title_no)
    return _attach_anchor(_read_title_row(title_no))


@router.get("/{title_no:path}", response_model=TitleRecord)
async def get_title(
    title_no: str,
    ctx: Annotated[AuthContext, Depends(require_role(*Role))],
) -> TitleRecord:
    # ``:path`` converter so title_no may contain ``/`` (e.g.
    # ``MITYANA/V1/20260001``); FastAPI/Starlette otherwise splits on
    # ``/`` and silently 404s. The audit-event proof lookup also falls
    # back to parcel_id to cover legacy seeded data.
    row = _read_title_row(title_no)
    if not row:
        raise HTTPException(status_code=404, detail="title not found")
    record = _attach_anchor(row)
    # Best-effort: if anchor exists, materialise the Merkle proof for the certificate.
    if record.tx_hash and record.merkle_proof is None:
        with get_connection() as conn:
            seq_row = conn.execute(
                "SELECT seq FROM audit_events "
                "WHERE tenant_id = ? AND event_type = 'TITLE_ISSUED' "
                "AND payload_json LIKE ?",
                (str(record.district_id), f'%"title_no": "{title_no}"%'),
            ).fetchone()
            if not seq_row:
                seq_row = conn.execute(
                    "SELECT seq FROM audit_events "
                    "WHERE tenant_id = ? AND event_type = 'TITLE_ISSUED' "
                    "AND payload_json LIKE ?",
                    (str(record.district_id), f'%"parcel_id": "{record.parcel_id}"%'),
                ).fetchone()
        if seq_row:
            proof = build_proof_for_event(
                district_id=record.district_id, leaf_seq=int(seq_row[0])
            )
            if proof:
                record = record.model_copy(update={"merkle_proof": proof.to_dict()})
    return record


@router.get("", response_model=list[TitleRecord])
async def list_titles(
    ctx: Annotated[AuthContext, Depends(require_role(*Role))],
    district_id: int | None = Query(default=None),
    parcel_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[TitleRecord]:
    where: list[str] = []
    params: list[object] = []
    if district_id is not None:
        where.append("district_id = ?")
        params.append(district_id)
    if parcel_id:
        where.append("parcel_id = ?")
        params.append(parcel_id)
    sql = (
        "SELECT title_no, parcel_id, issued_at, registrar_id, district_id, "
        " content_hash, merkle_proof, revoked_at, revoke_reason FROM titles"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY issued_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_attach_anchor(r) for r in rows]


@router.post("/{title_no}/revoke")
async def revoke_title(
    title_no: str,
    reason: str,
    ctx: Annotated[AuthContext, Depends(require_role(Role.REGISTRAR))],
) -> dict[str, object]:
    row = _read_title_row(title_no)
    if not row:
        raise HTTPException(status_code=404, detail="title not found")
    with get_connection() as conn:
        conn.execute(
            "UPDATE titles SET revoked_at = ?, revoke_reason = ? WHERE title_no = ?",
            (time.time(), reason, title_no),
        )
        conn.commit()
    audit_emit(
        event_type="TITLE_REVOKED",
        payload={"title_no": title_no, "reason": reason},
        district_id=int(row[4]),
        actor_user_id=ctx.user_id,
    )
    return {"title_no": title_no, "revoked": True}
