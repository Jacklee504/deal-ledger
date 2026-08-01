"""Promote one manually approved Amazon US draft into live Hugo content.

The scraper only creates a pending draft. Promotion deliberately requires the
reviewer to paste an Amazon Associates/SiteStripe URL and confirm a currently
public price. Prime-only, coupon-only, member-only, or unverified prices must
stay out of the live site.

Usage:
  python scripts/promote_deals.py --asin B012345678 \\
    --affiliate-url 'https://www.amazon.com/dp/B012345678?tag=yourtag-20' \\
    --public-price 59.99 --public-reference-price 99.99 \\
    --confirm-public-price
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "review-queue" / "deals"
TARGET_DIR = ROOT / "content" / "deals"
SYNC_SCRIPT = ROOT / "scripts" / "sync_listing_from_urls.py"
ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$", re.IGNORECASE)


class PromotionError(RuntimeError):
    """The draft is not ready for safe publication."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def split_front_matter(text: str) -> tuple[str, str]:
    if not text.startswith("+++\n"):
        raise PromotionError("draft does not use TOML front matter")
    end = text.find("\n+++\n", 4)
    if end < 0:
        raise PromotionError("draft TOML front matter is not closed")
    return text[4:end], text[end + 5 :]


def toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
    return json.dumps(str(value), ensure_ascii=True)


def upsert_front_matter(front: str, values: dict[str, object]) -> str:
    result = front.rstrip("\n")
    for key, value in values.items():
        rendered = f"{key} = {toml_value(value)}"
        pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
        if pattern.search(result):
            result = pattern.sub(rendered, result, count=1)
        else:
            result += f"\n{rendered}"
    return result + "\n"


def is_valid_associates_url(url: str) -> bool:
    """Accept a tagged amazon.com URL or a SiteStripe amzn.to short link."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    host = parsed.hostname.lower() if parsed.hostname else ""
    if host == "amzn.to" or host.endswith(".amzn.to"):
        return True
    if host not in {"amazon.com", "www.amazon.com"}:
        return False
    return bool(parse_qs(parsed.query).get("tag"))


def validate_draft(metadata: dict[str, object], asin: str) -> None:
    if str(metadata.get("asin") or "").upper() != asin:
        raise PromotionError("draft ASIN does not match --asin")
    if metadata.get("review_status") != "pending" or metadata.get("draft") is not True:
        raise PromotionError("only pending drafts may be promoted")
    if not metadata.get("product_url") or not (metadata.get("listing_image") or metadata.get("image")):
        raise PromotionError("draft is missing provider-backed listing metadata")


def promote(*, asin: str, affiliate_url: str, public_price: float,
            public_reference_price: float, confirm_public_price: bool) -> Path:
    asin = asin.upper()
    if not ASIN_PATTERN.fullmatch(asin):
        raise PromotionError("--asin must be a 10-character Amazon ASIN")
    if not confirm_public_price:
        raise PromotionError("pass --confirm-public-price only after confirming the price is public to all shoppers")
    if public_price <= 0 or public_reference_price <= public_price:
        raise PromotionError("--public-reference-price must be greater than --public-price")
    if not is_valid_associates_url(affiliate_url):
        raise PromotionError("--affiliate-url must be a tagged amazon.com URL or an https://amzn.to SiteStripe link")

    source = SOURCE_DIR / f"{asin}.md"
    if not source.exists():
        raise PromotionError(f"pending draft not found: {source.relative_to(ROOT)}")
    destination = TARGET_DIR / f"{asin}.md"
    if destination.exists():
        raise PromotionError(f"refusing to overwrite existing live deal: {destination.relative_to(ROOT)}")

    raw = source.read_text(encoding="utf-8")
    front, body = split_front_matter(raw)
    try:
        metadata = tomllib.loads(front)
    except tomllib.TOMLDecodeError as exc:
        raise PromotionError(f"draft front matter is invalid TOML: {exc}") from exc
    validate_draft(metadata, asin)

    discount = 1 - (public_price / public_reference_price)
    reviewed_at = utc_now()
    updates: dict[str, object] = {
        "draft": False,
        "review_status": "approved",
        "affiliate_ready": True,
        "affiliate_url": affiliate_url,
        "price_access": "public",
        "price_review_required": False,
        "public_price_confirmed_at": reviewed_at,
        "sale_price": public_price,
        "list_price": public_reference_price,
        "discount_pct": discount,
        "listing_source": "manual-public-confirmation",
        "listing_sale_price": public_price,
        "listing_list_price": public_reference_price,
        "listing_discount_pct": discount,
        "listing_synced_at": reviewed_at,
    }
    review_note = "Review the current Amazon US price, availability, and seller before promoting."
    published_note = "Price and public availability were manually confirmed before publication."
    published_body = body.replace(review_note, published_note)
    patched = f"+++\n{upsert_front_matter(front, updates)}+++\n{published_body}"

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    destination.write_text(patched, encoding="utf-8")
    source.unlink()
    try:
        display_destination = destination.relative_to(ROOT)
    except ValueError:
        display_destination = destination
    print(f"[promote_deals] promoted {source.name} -> {display_destination}")

    # Required repository hygiene: ensure the new live file has all listing
    # fields. This script is provider-metadata-only for Amazon and does not
    # make a direct Amazon request.
    completed = subprocess.run([sys.executable, str(SYNC_SCRIPT), str(destination)], cwd=ROOT, check=False)
    if completed.returncode:
        raise PromotionError("promotion wrote the live file but its listing metadata check failed")
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asin", required=True, help="Pending draft ASIN to promote")
    parser.add_argument("--affiliate-url", required=True, help="Amazon US SiteStripe/Associates URL")
    parser.add_argument("--public-price", required=True, type=float, help="Price visible to every shopper now")
    parser.add_argument("--public-reference-price", required=True, type=float, help="Current public reference/list price")
    parser.add_argument(
        "--confirm-public-price",
        action="store_true",
        help="Required acknowledgement that this is not a Prime/member/coupon-only price",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        promote(
            asin=args.asin,
            affiliate_url=args.affiliate_url.strip(),
            public_price=args.public_price,
            public_reference_price=args.public_reference_price,
            confirm_public_price=args.confirm_public_price,
        )
    except PromotionError as exc:
        print(f"[promote_deals] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
