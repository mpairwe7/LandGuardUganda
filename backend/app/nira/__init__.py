"""NIRA (National Identity and Registration Authority) integration.

In production this talks to NIRA's verification API. In the prototype
we use :class:`MockNIRAClient` which is fully deterministic — the
same NIN always produces the same outcome — and pre-seeds a handful
of identities to drive the showcase demo's fraud scenario.

# MIGRATION TO LIVE NIRA: see ``live_client.py``. The single env-var
# switch ``NIRA_PROVIDER=live`` is enough. Audit, caching, and breaker
# wrapping all stay unchanged.
"""

from __future__ import annotations

from .client import (
    NIRABiometricMatch,
    NIRAClient,
    NIRADemographics,
    NIRAVerifyResult,
    get_nira_client,
)

__all__ = [
    "NIRABiometricMatch",
    "NIRAClient",
    "NIRADemographics",
    "NIRAVerifyResult",
    "get_nira_client",
]
