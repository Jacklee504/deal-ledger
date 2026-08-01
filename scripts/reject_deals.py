"""Archive a reviewed-but-unsuitable pending deal so intake will not rediscover it.

Usage:
  python scripts/reject_deals.py --asin B012345678 --reason 'Prime-only price'
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PENDING_DIR = ROOT / "review-queue" / "deals"
REJECTED_DIR = ROOT / "review-queue" / "rejected"
ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$", re.IGNORECASE)


def upsert(text: str, key: str, value: str) -> str:
    rendered = f"{key} = {json.dumps(value, ensure_ascii=True)}"
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(rendered, text, count=1)
    return text.replace("+++\n", f"+++\n{rendered}\n", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asin", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    asin = args.asin.upper()
    reason = args.reason.strip()
    if not ASIN_PATTERN.fullmatch(asin) or not reason:
        parser.error("provide a valid ASIN and a non-empty rejection reason")

    source = PENDING_DIR / f"{asin}.md"
    if not source.exists():
        print(f"[reject_deals] pending draft not found: {source.relative_to(ROOT)}", file=sys.stderr)
        return 1
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    destination = REJECTED_DIR / source.name
    if destination.exists():
        print(f"[reject_deals] refusing to overwrite existing rejection: {destination.relative_to(ROOT)}", file=sys.stderr)
        return 1
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    text = source.read_text(encoding="utf-8")
    text = upsert(text, "review_status", "rejected")
    text = upsert(text, "rejection_reason", reason)
    text = upsert(text, "rejected_at", timestamp)
    destination.write_text(text, encoding="utf-8")
    source.unlink()
    print(f"[reject_deals] rejected {asin}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
