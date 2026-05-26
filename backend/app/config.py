"""Pydantic-settings configuration with strict prod validation."""

from __future__ import annotations

import base64
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration.

    Reads ``.env`` at the backend root. In production, env vars override.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "landguard-backend"
    log_level: str = "INFO"
    demo_mode: bool = True

    # --- Database ---
    db_backend: Literal["sqlite", "postgres"] = "sqlite"
    sqlite_path: str = "./data_store/landguard.db"
    postgres_dsn: str = "postgresql+asyncpg://landguard:landguard@postgres:5432/landguard"

    # --- Redis ---
    redis_url: str = "redis://redis:6379/0"

    # --- Auth ---
    auth_mode: Literal["dev", "oidc"] = "dev"
    auth_required: bool = True
    jwt_hs256_secret: str = "change-me-dev-only-please-replace-in-prod-with-32-chars"
    jwt_issuer: str = "landguard.ug"
    jwt_audience: str = "landguard-backend"
    oidc_jwks_url: str = ""
    flag_multi_tenant: bool = True

    # --- Blockchain ---
    blockchain_provider: Literal["mock", "anvil", "sepolia"] = "anvil"
    anvil_rpc_url: str = "http://anvil:8545"
    anvil_chain_id: int = 31337
    sepolia_rpc_url: str = ""
    sepolia_chain_id: int = 11155111
    registrar_private_key: str = (
        "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    )
    contract_address_file: str = "./data_store/contract_address.json"
    anchor_flush_interval_seconds: int = 300
    anchor_flush_batch_size: int = 100

    # --- Custody (multi-sig) ---
    # Production posture: 3-of-5 MultiSigRegistrar holds the only REGISTRAR_ROLE
    # on the LandRegistryAnchor. The backend's key signs first; co-signers
    # (MoLHUD, NITA-U, district board, auditor) complete the threshold.
    # See docs/CUSTODY.md.
    multisig_enabled: bool = False
    # Co-signer keys are used by the demo co-signer daemon (scripts/co_sign_daemon.py).
    # In production they live in HSMs / KMS, never in env.
    cosigner_private_keys: str = ""  # comma-separated for demo only

    # --- NIRA ---
    nira_provider: Literal["mock", "live"] = "mock"
    nira_base_url: str = ""
    nira_api_key: str = ""
    nira_cache_ttl_seconds: int = 86400

    # --- Encryption ---
    pii_encryption_key: str = "dGhpc19pc19hX2RldmVsb3BtZW50X29ubHlfa2V5X3JlcGxhY2VfaXRfbm93"

    # --- Rate limits ---
    rate_limit_anon: str = "10/minute"
    rate_limit_auth: str = "60/minute"
    rate_limit_admin: str = "300/minute"
    rate_limit_public_verify: str = "20/minute"

    # --- Observability ---
    otel_enabled: bool = True
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = "landguard-backend"
    prometheus_metrics_enabled: bool = True

    # --- CORS ---
    # The deployed Crane Cloud frontend talks directly to the backend
    # (browser → public ingress) because Crane Cloud RENU pods have no
    # outbound internet egress, so the frontend pod's /api/proxy route
    # cannot reach this backend's public URL itself. The browser-direct
    # path requires this origin in the allowlist.
    cors_allow_origins: str = (
        "http://localhost:3000,"
        "http://frontend:3000,"
        "https://landguard-frontend-3d8aba74.renu-01.cranecloud.io"
    )

    @field_validator("jwt_hs256_secret")
    @classmethod
    def _check_secret_strength(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_HS256_SECRET must be at least 32 characters")
        return v

    @field_validator("pii_encryption_key")
    @classmethod
    def _check_pii_key(cls, v: str) -> str:
        try:
            decoded = base64.b64decode(v)
        except Exception as exc:
            raise ValueError("PII_ENCRYPTION_KEY must be base64-encoded") from exc
        if len(decoded) < 32:
            raise ValueError("PII_ENCRYPTION_KEY must be at least 32 bytes after b64 decode")
        return v

    def assert_prod_safety(self) -> None:
        """Hard-fail at startup if running prod with dev defaults."""
        if self.app_env != "production":
            return
        bad = []
        if "change-me" in self.jwt_hs256_secret:
            bad.append("JWT_HS256_SECRET")
        if self.auth_mode == "dev":
            bad.append("AUTH_MODE=dev")
        if self.demo_mode:
            bad.append("DEMO_MODE=true")
        if self.blockchain_provider == "mock":
            bad.append("BLOCKCHAIN_PROVIDER=mock")
        if "development_only" in base64.b64decode(self.pii_encryption_key).decode("utf-8", "ignore"):
            bad.append("PII_ENCRYPTION_KEY")
        if bad:
            raise RuntimeError(
                f"production configuration uses dev defaults for: {', '.join(bad)}"
            )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def rpc_url(self) -> str:
        return (
            self.sepolia_rpc_url
            if self.blockchain_provider == "sepolia"
            else self.anvil_rpc_url
        )

    @property
    def chain_id(self) -> int:
        return (
            self.sepolia_chain_id
            if self.blockchain_provider == "sepolia"
            else self.anvil_chain_id
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
