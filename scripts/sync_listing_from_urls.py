"""Normalize provider-backed listing metadata for live deal files.

Usage:
  python scripts/sync_listing_from_urls.py
  python scripts/sync_listing_from_urls.py content/deals/B012345678.md

This is intentionally *not* an Amazon HTML scraper. Direct browser-style
fetches are fragile and outside the review-first provider pipeline. SerpApi +
Bright Data provide the intake snapshot; this helper copies that approved
snapshot into the ``listing_*`` fields consumed by Hugo and verifies the file
is ready for deployment.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEALS_DIR = ROOT / "content" / "deals"


class MetadataError(RuntimeError):
    """A live deal cannot safely be normalized from its stored snapshot."""


def split_front_matter(raw: str) -> tuple[str, str]:
    if not raw.startswith("+++\n"):
        raise MetadataError("does not use TOML front matter")
    end = raw.find("\n+++\n", 4)
    if end < 0:
        raise MetadataError("TOML front matter is not closed")
    return raw[4:end], raw[end + 5 :]


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):.6f}".rstrip("0").rstrip(".")
    return json.dumps(str(value), ensure_ascii=True)


def upsert(front: str, key: str, value: Any) -> str:
    rendered = f"{key} = {toml_value(value)}"
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    if pattern.search(front):
        # TOML strings use JSON escapes such as ``\\u2011``. Supplying the
        # rendered value directly makes ``re.sub`` parse those as regex
        # backreferences; a callable replacement preserves the literal TOML.
        return pattern.sub(lambda _: rendered, front, count=1)
    return front.rstrip("\n") + f"\n{rendered}\n"


def canonical_amazon_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"amazon.com", "www.amazon.com"}:
        return url
    asin = re.search(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)", parsed.path, re.IGNORECASE)
    if not asin:
        return url
    return f"https://www.amazon.com/dp/{asin.group(1).upper()}"


def as_number(value: Any, key: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise MetadataError(f"missing or invalid {key}")


def normalized_front(front: str, metadata: dict[str, Any]) -> str:
    product_url = str(metadata.get("product_url") or "").strip()
    title = str(metadata.get("title") or "").strip()
    summary = str(metadata.get("summary") or title).strip()
    image = str(metadata.get("image") or metadata.get("listing_image") or "").strip()
    sale = as_number(metadata.get("sale_price"), "sale_price")
    list_price = as_number(metadata.get("list_price"), "list_price")
    if not product_url or not title or not image or sale <= 0 or list_price <= sale:
        raise MetadataError("needs product_url, title, image, and a valid positive price reduction")
    discount = 1 - (sale / list_price)
    if discount <= 0:
        raise MetadataError("has no positive verified discount")
    synced_at = str(metadata.get("public_price_confirmed_at") or metadata.get("verified_at") or "").strip()
    if not synced_at:
        synced_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    values = {
        "listing_url": canonical_amazon_url(product_url),
        "listing_title": title,
        "listing_summary": summary,
        "listing_image": image,
        "listing_sale_price": sale,
        "listing_list_price": list_price,
        "listing_discount_pct": discount,
        "listing_synced_at": synced_at,
    }
    result = front
    for key, value in values.items():
        result = upsert(result, key, value)
    return result


def resolve_paths(file_args: list[str]) -> list[Path]:
    selected = []
    raw_paths = file_args or [str(DEALS_DIR)]
    for raw in raw_paths:
        path = Path(raw)
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        if path.is_dir():
            selected.extend(path.glob("*.md"))
        elif path.suffix == ".md":
            selected.append(path)
    return sorted({path.resolve() for path in selected if path.exists() and path.name != "_index.md"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="Live deal markdown files, or a directory (defaults to content/deals).")
    args = parser.parse_args()
    paths = resolve_paths(args.files)
    if not paths:
        print("[sync_listing_from_urls] no files selected")
        return 0

    updated = 0
    failed = 0
    for path in paths:
        try:
            front, body = split_front_matter(path.read_text(encoding="utf-8"))
            metadata = tomllib.loads(front)
            next_front = normalized_front(front, metadata)
            if next_front != front:
                path.write_text(f"+++\n{next_front.rstrip()}\n+++\n{body}", encoding="utf-8")
                updated += 1
                try:
                    display = path.relative_to(ROOT)
                except ValueError:
                    display = path
                print(f"[sync_listing_from_urls] normalized {display}")
        except (OSError, MetadataError, tomllib.TOMLDecodeError) as exc:
            failed += 1
            try:
                display = path.relative_to(ROOT)
            except ValueError:
                display = path
            print(f"[sync_listing_from_urls] {display}: {exc}", file=sys.stderr)

    print(f"[sync_listing_from_urls] done: {updated} file(s) normalized, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
