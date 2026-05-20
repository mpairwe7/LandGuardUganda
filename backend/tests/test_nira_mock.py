"""Mock NIRA client deterministic behaviour."""

from __future__ import annotations

import pytest

from app.nira import get_nira_client
from app.nira.client import reset_nira_client


@pytest.fixture(autouse=True)
def _reset_client():
    reset_nira_client()
    yield
    reset_nira_client()


@pytest.mark.asyncio
async def test_seeded_match():
    client = get_nira_client()
    result = await client.verify_nin("CM82010110A4P0")
    assert result.nin_valid
    assert result.matched
    assert result.demographics is not None
    assert result.demographics.full_name == "Sarah Nakato"


@pytest.mark.asyncio
async def test_seeded_no_match_fraudster():
    client = get_nira_client()
    result = await client.verify_nin("CM82010110A4P9")
    assert result.nin_valid
    assert not result.matched
    assert result.reason == "nin_not_in_register"


@pytest.mark.asyncio
async def test_format_rejection():
    client = get_nira_client()
    result = await client.verify_nin("INVALID")
    assert not result.nin_valid
    assert result.reason == "format_invalid"
