"""Validate that newly promoted live deals are safe to deploy without scraping.

Usage:
  python scripts/validate_live_deal_metadata.py content/deals/B012345678.md
"""
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def split_front_matter(raw: str) -> str:
    if not raw.startswith("+++\n"):
        raise ValueError("does not use TOML front matter")
    end = raw.find("\n+++\n", 4)
    if end < 0:
        raise ValueError("TOML front matter is not closed")
    return raw[4:end]


def associates_url(url: object) -> bool:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return False
    if host == "amzn.to" or host.endswith(".amzn.to"):
        return True
    return host in {"amazon.com", "www.amazon.com"} and bool(parse_qs(parsed.query).get("tag"))


def amazon_us_url(url: object) -> bool:
    parsed = urlparse(str(url or ""))
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in {"amazon.com", "www.amazon.com"}


def validate(path: Path) -> list[str]:
    try:
        data = tomllib.loads(split_front_matter(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [str(exc)]
    errors: list[str] = []
    for key in ("listing_title", "listing_image", "listing_url", "listing_synced_at", "product_url", "asin"):
        if not str(data.get(key) or "").strip():
            errors.append(f"missing {key}")
    for key in ("sale_price", "list_price", "listing_sale_price", "listing_list_price"):
        if not isinstance(data.get(key), (int, float)) or isinstance(data.get(key), bool):
            errors.append(f"missing or invalid {key}")
    if not errors and float(data["list_price"]) <= float(data["sale_price"]):
        errors.append("list_price must exceed sale_price")
    if data.get("review_status") != "approved" or data.get("draft") is not False:
        errors.append("deal is not approved live content")
    if not re.fullmatch(r"[A-Z0-9]{10}", str(data.get("asin") or ""), re.IGNORECASE):
        errors.append("invalid ASIN")
    if data.get("marketplace") != "amazon.com" or data.get("currency") != "USD":
        errors.append("deal is not scoped to amazon.com/USD")
    if not amazon_us_url(data.get("product_url")) or not amazon_us_url(data.get("listing_url")):
        errors.append("product/listing URL is not an Amazon US URL")
    if data.get("price_access") != "public" or data.get("price_review_required") is not False:
        errors.append("public-price confirmation is missing")
    if data.get("affiliate_ready") is not True or not associates_url(data.get("affiliate_url")):
        errors.append("valid Amazon Associates/SiteStripe affiliate_url is missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="One or more new content/deals markdown files")
    args = parser.parse_args()
    failed = False
    for raw in args.files:
        path = Path(raw)
        errors = validate(path)
        if errors:
            failed = True
            print(f"[validate_live_deal_metadata] {path}: {'; '.join(errors)}", file=sys.stderr)
        else:
            print(f"[validate_live_deal_metadata] ok: {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
