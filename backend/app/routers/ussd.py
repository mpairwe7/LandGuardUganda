"""USSD + SMS verification endpoints (Africa's Talking-compatible).

A citizen with a feature phone dials ``*247*256#`` (a placeholder shortcode;
the real one is assigned by UCC). They are offered three choices:

  1. Verify a title
  2. Check parcel status
  3. Help / contact District Land Office

For (1) they enter the title number; the app calls the public verifier and
returns a 160-character result. The same backend logic is also exposed via
``POST /api/v1/sms/verify`` for inbound-SMS gateways.

Audit-emitted so equity-of-access is observable in the same chain everyone
else writes to.

Like ``routers/verify.py``, we skip ``from __future__ import annotations``
so slowapi-wrapped handlers don't trip Pydantic's forward-ref resolution.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response

from app.audit import audit_emit
from app.middleware.limits import limit_anon
from app.models.verify import VerifyTitleRequest
from app.routers.verify import verify_title
from app.util.ussd import (
    UssdRequest,
    con,
    end,
    format_verify_result,
    session_load,
    session_save,
)

router = APIRouter(prefix="/api/v1", tags=["accessibility"])
logger = logging.getLogger(__name__)


@router.post("/ussd", response_class=Response)
@limit_anon
async def ussd_callback(
    request: Request,
    sessionId: Annotated[str, Form()] = "",
    serviceCode: Annotated[str, Form()] = "",
    phoneNumber: Annotated[str, Form()] = "",
    text: Annotated[str, Form()] = "",
) -> Response:
    """Africa's Talking USSD callback handler.

    The body is x-www-form-urlencoded; the response is plain text starting
    with ``CON`` (continue session) or ``END`` (terminate). Idempotent — the
    state machine is rebuilt from ``text`` on every call so we tolerate
    Africa's Talking redelivering on transient timeouts.
    """
    ussd = UssdRequest.from_form(
        {
            "sessionId": sessionId,
            "serviceCode": serviceCode,
            "phoneNumber": phoneNumber,
            "text": text,
        }
    )
    body = await _route(ussd, request)
    return Response(content=body, media_type="text/plain")


async def _route(ussd: UssdRequest, request: Request) -> str:
    steps = ussd.steps
    if not steps:
        return con(
            "LandGuard Uganda\n"
            "1. Verify title\n"
            "2. Check parcel status\n"
            "3. Help / contact District Land Office"
        )

    choice = steps[0]
    if choice == "1":
        if len(steps) == 1:
            return con(
                "Enter the title number\n"
                "(format: UG-DDD-TNNNNN/YYYY)\n"
                "e.g. UG-MIT-T00007/2026"
            )
        title_no = steps[1].strip().upper()
        await session_save(
            ussd.session_id,
            {"action": "verify", "title_no": title_no, "phone": ussd.phone_number},
        )
        result = await verify_title(
            request=request,
            payload=VerifyTitleRequest(title_no=title_no),
        )
        audit_emit(
            event_type="USSD_VERIFY",
            payload={
                "title_no": title_no,
                "phone_sha": _hash_phone(ussd.phone_number),
                "valid": bool(result.valid),
                "reason": result.reason,
            },
            district_id=0,  # cross-district public action
            actor_user_id=f"ussd:{ussd.session_id[:8]}",
        )
        return end(format_verify_result(result.model_dump()))

    if choice == "2":
        if len(steps) == 1:
            return con("Enter parcel UPI\n(e.g. UG-MIT-024718/2026)")
        # For brevity in the prototype the status path goes through the same
        # verify endpoint; production would surface owner/area/dispute.
        upi = steps[1].strip().upper()
        # Find the latest title for this parcel and verify it.
        from app.database import get_connection

        with get_connection() as conn:
            row = conn.execute(
                "SELECT title_no FROM titles WHERE parcel_id = ? ORDER BY issued_at DESC LIMIT 1",
                (upi,),
            ).fetchone()
        if not row:
            return end(f"No title found for parcel {upi}.")
        title_no = str(row[0])
        result = await verify_title(
            request=request, payload=VerifyTitleRequest(title_no=title_no)
        )
        return end(format_verify_result(result.model_dump()))

    if choice == "3":
        return end(
            "Help: District Land Office Mityana 0414-XXXXXX. "
            "MoLHUD hotline 0800-100-300. "
            "More: landguard.ug"
        )

    return end("Unknown option. Dial again.")


@router.post("/sms/verify")
@limit_anon
async def sms_verify(
    request: Request,
    From: Annotated[str, Form()] = "",
    Body: Annotated[str, Form()] = "",
) -> dict[str, str]:
    """SMS inbound: body is the title number; response is the 160-char result.

    Compatible with Africa's Talking inbound-SMS and Twilio-style gateways.
    Returns JSON ``{message}`` — gateway adapters render the SMS reply.
    """
    title_no = (Body or "").strip().upper()
    if not title_no:
        return {"message": "Send the title number, e.g. UG-MIT-T00007/2026"}
    result = await verify_title(
        request=request, payload=VerifyTitleRequest(title_no=title_no)
    )
    audit_emit(
        event_type="SMS_VERIFY",
        payload={
            "title_no": title_no,
            "phone_sha": _hash_phone(From),
            "valid": bool(result.valid),
        },
        district_id=0,
        actor_user_id=f"sms:{_hash_phone(From)[:8]}",
    )
    return {"message": format_verify_result(result.model_dump())}


def _hash_phone(msisdn: str) -> str:
    """We never log raw phone numbers — the audit ledger sees only sha256(msisdn)."""
    from app.audit.merkle import sha256_hex

    return sha256_hex(msisdn or "anonymous")
