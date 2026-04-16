#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[post_add_refresh] Syncing listing fields from URLs..."
python3 scripts/sync_listing_from_urls.py || true

echo "[post_add_refresh] Building site..."
hugo --gc --minify

echo "[post_add_refresh] Checking for deals missing listing_image..."
python3 - <<'PY'
from pathlib import Path
import re

root = Path(".")
deals_dir = root / "content" / "deals"

def split_front_matter(raw: str):
    if not raw.startswith("+++\n"):
        return None
    end = raw.find("\n+++\n", 4)
    if end == -1:
        return None
    return raw[4:end]

def get(front: str, key: str) -> str:
    m = re.search(rf'^{re.escape(key)}\s*=\s*"([^"]+)"\s*$', front, re.MULTILINE)
    return m.group(1).strip() if m else ""

missing = []
for path in sorted(deals_dir.glob("*.md")):
    if path.name == "_index.md":
        continue
    raw = path.read_text()
    front = split_front_matter(raw)
    if not front:
        continue
    listing_url = get(front, "listing_url") or get(front, "product_url") or get(front, "affiliate_url")
    if not listing_url:
        continue
    if not get(front, "listing_image"):
        missing.append(path.name)

if missing:
    print("[post_add_refresh] Missing listing_image in:")
    for name in missing:
        print(f"  - {name}")
else:
    print("[post_add_refresh] All deal files with retailer URLs have listing_image set.")
PY

echo "[post_add_refresh] Done."
