#!/usr/bin/env python3
"""Self-contained CycloneDX 1.5 BOM generator for the frontend.

Used by `scripts/generate_sbom.sh` when @cyclonedx/cyclonedx-npm is
unavailable or refuses to traverse the graph (e.g. React 19 peer-dep
strictness against bun-managed node_modules).

Inputs:
  --package-json path/to/package.json   (direct dependencies + version)
  --lockfile     path/to/bun.lock        (full resolved graph; optional)
  --out          path/to/frontend-cyclonedx.json

Output: CycloneDX 1.5 JSON. Every component carries:
  - bom-ref     deterministic purl
  - name, version
  - purl        pkg:npm/<name>@<version>
  - scope       required | optional (devDependencies)

The script is deliberately dependency-free (stdlib only) so it runs in
any CI runner without an install step.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import uuid
from pathlib import Path

CYCLONEDX_SPEC = "1.5"


def _purl(name: str, version: str) -> str:
    """Build a pkg:npm purl. Names may be scoped (@scope/name)."""
    if name.startswith("@"):
        scope, _, pkg = name[1:].partition("/")
        return f"pkg:npm/%40{scope}/{pkg}@{version}"
    return f"pkg:npm/{name}@{version}"


_LOCKLINE = re.compile(r'"([^"]+)@([^"]+)":')


def _parse_bun_lock(lockfile: Path) -> dict[str, str]:
    """Return {package_name: resolved_version} from bun.lock.

    bun.lock is JSON-like but uses a lockfile-specific dialect. We do a
    line-level parse that's tolerant of formatting variations.
    """
    resolved: dict[str, str] = {}
    if not lockfile.exists():
        return resolved
    try:
        text = lockfile.read_text(encoding="utf-8")
    except Exception:
        return resolved
    for line in text.splitlines():
        m = _LOCKLINE.search(line.strip())
        if not m:
            continue
        name, version = m.group(1), m.group(2)
        # Skip protocol-prefixed selectors (file:, link:, workspace:, etc.)
        if "://" in version or version.startswith(("file:", "link:", "workspace:")):
            continue
        # Keep the first resolution we see — bun.lock lists the canonical first.
        if name not in resolved:
            resolved[name] = version
    return resolved


def _from_package_json(pj: dict) -> list[dict]:
    """Return a list of (name, version, scope) tuples from package.json deps."""
    components: list[dict] = []
    for scope_key, scope_label in (
        ("dependencies", "required"),
        ("devDependencies", "optional"),
        ("peerDependencies", "optional"),
    ):
        for name, spec in (pj.get(scope_key) or {}).items():
            components.append(
                {
                    "name": name,
                    "version_spec": spec,
                    "scope": scope_label,
                }
            )
    return components


def build_bom(package_json: Path, lockfile: Path) -> dict:
    pj = json.loads(package_json.read_text(encoding="utf-8"))
    resolved = _parse_bun_lock(lockfile)
    declared = _from_package_json(pj)

    components: list[dict] = []
    seen: set[str] = set()

    for d in declared:
        name = d["name"]
        # Prefer resolved version from bun.lock; fall back to declared spec.
        version = resolved.get(name) or d["version_spec"]
        # Strip semver range operators for cleaner purls.
        clean_version = re.sub(r"^[\^~><=]+", "", version)
        ref = f"pkg:npm/{name}@{clean_version}"
        if ref in seen:
            continue
        seen.add(ref)
        components.append(
            {
                "type": "library",
                "bom-ref": ref,
                "name": name,
                "version": clean_version,
                "purl": _purl(name, clean_version),
                "scope": d["scope"],
            }
        )

    # Also include any extra entries from the lockfile that aren't directly
    # declared — these are transitive but valuable for an SBOM audit.
    declared_names = {d["name"] for d in declared}
    for name, version in resolved.items():
        if name in declared_names:
            continue
        clean_version = re.sub(r"^[\^~><=]+", "", version)
        ref = f"pkg:npm/{name}@{clean_version}"
        if ref in seen:
            continue
        seen.add(ref)
        components.append(
            {
                "type": "library",
                "bom-ref": ref,
                "name": name,
                "version": clean_version,
                "purl": _purl(name, clean_version),
                "scope": "required",  # transitive of a runtime dep — best-effort
            }
        )

    return {
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_SPEC,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": _dt.datetime.now(tz=_dt.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": [
                {
                    "vendor": "LandGuard Uganda",
                    "name": "sbom-frontend-fallback",
                    "version": "1.0.0",
                }
            ],
            "component": {
                "type": "application",
                "bom-ref": f"pkg:npm/{pj.get('name', 'landguard-frontend')}@{pj.get('version', '0.1.0')}",
                "name": pj.get("name", "landguard-frontend"),
                "version": pj.get("version", "0.1.0"),
            },
        },
        "components": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-json", required=True, type=Path)
    parser.add_argument("--lockfile", required=False, type=Path, default=None)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    bom = build_bom(args.package_json, args.lockfile or Path("/dev/null"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")
    print(
        f"  ✓ {args.out} — {len(bom['components'])} components"
        f" (declared+transitive from bun.lock)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
