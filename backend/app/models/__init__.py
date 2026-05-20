"""Pydantic v2 strict models for LandGuard's HTTP API."""

from __future__ import annotations

from .anchors import AnchorRecord, AnchorListResponse
from .common import PaginatedResponse, Pagination
from .disputes import DisputeFileRequest, DisputeRecord, DisputeResolveRequest
from .fraud import FraudScoreResponse, FraudSignalResponse
from .owners import KycVerifyRequest, OwnerCreateRequest, OwnerRecord
from .parcels import GeoSearchRequest, ParcelCreateRequest, ParcelRecord
from .titles import TitleIssueRequest, TitleRecord
from .transfers import TransferCreateRequest, TransferRecord
from .verify import VerifyTitleRequest, VerifyTitleResponse

__all__ = [
    "AnchorListResponse",
    "AnchorRecord",
    "DisputeFileRequest",
    "DisputeRecord",
    "DisputeResolveRequest",
    "FraudScoreResponse",
    "FraudSignalResponse",
    "GeoSearchRequest",
    "KycVerifyRequest",
    "OwnerCreateRequest",
    "OwnerRecord",
    "PaginatedResponse",
    "Pagination",
    "ParcelCreateRequest",
    "ParcelRecord",
    "TitleIssueRequest",
    "TitleRecord",
    "TransferCreateRequest",
    "TransferRecord",
    "VerifyTitleRequest",
    "VerifyTitleResponse",
]
