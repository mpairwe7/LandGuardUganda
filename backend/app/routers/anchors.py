"""Anchor batch endpoints — list, detail, materialise proof, manual flush."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import AuthContext, Role, require_role, require_user
from app.blockchain.anchor_service import build_proof_for_event, flush_district
from app.database import get_connection
from app.models.anchors import AnchorListResponse, AnchorRecord

router = APIRouter(prefix="/api/v1/anchors", tags=["anchors"])


def _row_to_anchor(row) -> AnchorRecord:
    return AnchorRecord(
        batch_id=row[0],
        district_id=int(row[1]),
        root_hash=row[2],
        first_seq=int(row[3]),
        last_seq=int(row[4]),
        leaf_count=int(row[5]),
        tx_hash=row[6],
        block_number=int(row[7]) if row[7] is not None else None,
        anchored_at=float(row[8]),
        confirmed_at=float(row[9]) if row[9] is not None else None,
        status=row[10],
    )


@router.get("", response_model=AnchorListResponse)
async def list_anchors(
    ctx: Annotated[AuthContext, Depends(require_user)],
    district_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AnchorListResponse:
    where = ""
    params: list[object] = []
    if district_id is not None:
        where = " WHERE district_id = ?"
        params.append(district_id)
    with get_connection() as conn:
        total_row = conn.execute(
            f"SELECT COUNT(*) FROM anchors{where}", params
        ).fetchone()
        total = int(total_row[0])
        rows = conn.execute(
            "SELECT batch_id, district_id, root_hash, first_seq, last_seq, leaf_count, "
            " tx_hash, block_number, anchored_at, confirmed_at, status "
            f"FROM anchors{where} ORDER BY anchored_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    return AnchorListResponse(items=[_row_to_anchor(r) for r in rows], total=total)


@router.get("/{batch_id}", response_model=AnchorRecord)
async def get_anchor(
    batch_id: str,
    ctx: Annotated[AuthContext, Depends(require_user)],
) -> AnchorRecord:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT batch_id, district_id, root_hash, first_seq, last_seq, leaf_count, "
            " tx_hash, block_number, anchored_at, confirmed_at, status "
            "FROM anchors WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="anchor batch not found")
    return _row_to_anchor(row)


@router.get("/title/{title_no}/proof")
async def proof_for_title(
    title_no: str,
    ctx: Annotated[AuthContext, Depends(require_user)],
) -> dict[str, object]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT district_id FROM titles WHERE title_no = ?",
            (title_no,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="title not found")
        district_id = int(row[0])
        seq_row = conn.execute(
            "SELECT seq FROM audit_events "
            "WHERE tenant_id = ? AND event_type = 'TITLE_ISSUED' "
            "AND payload_json LIKE ?",
            (str(district_id), f'%"title_no": "{title_no}"%'),
        ).fetchone()
    if not seq_row:
        raise HTTPException(status_code=409, detail="title not yet recorded in ledger")
    proof = build_proof_for_event(district_id=district_id, leaf_seq=int(seq_row[0]))
    if not proof:
        raise HTTPException(status_code=409, detail="title not yet anchored")
    return proof.to_dict()


@router.post("/flush/{district_id}", dependencies=[Depends(require_role(Role.ADMIN, Role.REGISTRAR))])
async def manual_flush(district_id: int) -> dict[str, object]:
    """Force an immediate anchor flush for one district. Used by the demo control panel."""
    return await flush_district(district_id, force=True)
