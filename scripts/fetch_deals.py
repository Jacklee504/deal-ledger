"""Fetch deals from Amazon PA-API and write Hugo content files.

Usage:
  Requires env vars: AMZ_PAAPI_ACCESS_KEY, AMZ_PAAPI_SECRET_KEY, AMZ_PARTNER_TAG
  Optional env: AMZ_MARKETPLACE (domain like www.amazon.co.uk or www.amazon.com)

Behavior:
  - If any required env is missing, exits cleanly (so CI won't fail while unconfigured).
  - Reads seeds.json for ASINs and per-ASIN tags; skip if seeds are still placeholders.
  - Calls PA-API in batches, writes markdown to content/deals/generated/<asin>.md
    with front matter compatible with existing templates.
"""
from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from amazon.paapi import AmazonApi, AmazonException

ROOT = Path(__file__).resolve().parents[1]
SEEDS_PATH = ROOT / "scripts" / "seeds.json"
OUTPUT_DIR = ROOT / "content" / "deals" / "generated"

REQUIRED_ENVS = ["AMZ_PAAPI_ACCESS_KEY", "AMZ_PAAPI_SECRET_KEY", "AMZ_PARTNER_TAG"]


def has_required_env() -> bool:
    return all(os.getenv(key) for key in REQUIRED_ENVS)


def load_seeds():
    if not SEEDS_PATH.exists():
        print("[fetch_deals] seeds.json not found; skipping")
        return None
    data = json.loads(SEEDS_PATH.read_text())
    asins = data.get("asins", [])
    if not asins or any(x.startswith("EDIT_ME_") for x in asins):
        print("[fetch_deals] seeds.json not configured with real ASINs; skipping")
        return None
    marketplace = os.getenv("AMZ_MARKETPLACE") or data.get("marketplace") or "www.amazon.com"
    tags_map = data.get("tags", {})
    return marketplace, asins, tags_map


def host_to_country(host: str) -> str:
    host = host.lower()
    if host.endswith(".co.uk") or host.endswith(".uk"):
        return "UK"
    if host.endswith(".de"):
        return "DE"
    if host.endswith(".fr"):
        return "FR"
    if host.endswith(".ca"):
        return "CA"
    if host.endswith(".co.jp") or host.endswith(".jp"):
        return "JP"
    if host.endswith(".in"):
        return "IN"
    if host.endswith(".it"):
        return "IT"
    if host.endswith(".es"):
        return "ES"
    if host.endswith(".com.au"):
        return "AU"
    if host.endswith(".com.br"):
        return "BR"
    if host.endswith(".com.mx"):
        return "MX"
    if host.endswith(".com.tr"):
        return "TR"
    if host.endswith(".ae") or host.endswith(".sa"):
        return "AE"
    if host.endswith(".nl"):
        return "NL"
    if host.endswith(".se"):
        return "SE"
    if host.endswith(".pl"):
        return "PL"
    if host.endswith(".eg"):
        return "EG"
    if host.endswith(".be"):
        return "BE"
    return "US"


def client(country: str) -> AmazonApi:
    return AmazonApi(
        os.environ["AMZ_PAAPI_ACCESS_KEY"],
        os.environ["AMZ_PAAPI_SECRET_KEY"],
        os.environ["AMZ_PARTNER_TAG"],
        country=country,
    )


def batches(iterable: List[str], size: int = 10):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def write_deal(asin: str, payload: dict, tags: List[str]):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    title = payload.get("title", asin)
    url = payload.get("url", "")
    image = payload.get("image", "")
    price = payload.get("price")
    list_price = payload.get("list_price")
    discount = None
    if price and list_price and list_price > 0:
        discount = max(0.0, min(1.0, 1 - (price / list_price)))
    featured = bool(discount and discount >= 0.3)
    summary = payload.get("summary", "")
    now_iso = datetime.utcnow().isoformat() + "Z"
    fm_lines = [
        "+++",
        f"title = \"{title}\"",
        f"date = \"{now_iso}\"",
        f"list_price = {list_price if list_price is not None else 0}",
        f"sale_price = {price if price is not None else 0}",
        f"discount_pct = {discount if discount is not None else 0}",
        f"featured = {str(featured).lower()}",
        f"tags = {json.dumps(tags)}",
        f"categories = [\"deals\"]",
        f"affiliate_url = \"{url}\"",
        f"image = \"{image}\"",
        f"summary = \"{summary}\"",
        "+++",
        "",
        summary or "A curated pick from the latest feed.",
        "",
    ]
    outfile = OUTPUT_DIR / f"{asin}.md"
    outfile.write_text("\n".join(fm_lines))
    print(f"[fetch_deals] wrote {outfile}")


def main():
    if not has_required_env():
        print("[fetch_deals] Missing PA-API env vars; skipping")
        return
    seeds = load_seeds()
    if not seeds:
        return
    marketplace, asins, tags_map = seeds
    country = host_to_country(marketplace)
    api = client(country)

    for batch in batches(asins, size=10):
        try:
            products = api.get_items(batch)
        except AmazonException as exc:
            print(f"[fetch_deals] batch {batch} failed: {exc}")
            continue
        if not products:
            print(f"[fetch_deals] No items returned for {batch}")
            continue

        for product in products:
            asin = product.asin
            raw_offers: Dict = (product.raw or {}).get("Offers") or {}
            listings = raw_offers.get("Listings") or []
            price = None
            list_price = None
            if listings:
                listing = listings[0]
                price_info = listing.get("Price") or {}
                savings = price_info.get("Savings") or {}
                amount = price_info.get("Amount")
                basis = price_info.get("SavingsBasis")
                if amount is not None:
                    price = amount
                if basis is not None:
                    list_price = basis
                elif amount is not None and savings.get("Amount") is not None:
                    list_price = amount + savings["Amount"]
            payload = {
                "title": product.title or asin,
                "url": product.url or "",
                "image": (product.images.large if product.images else ""),
                "price": price,
                "list_price": list_price,
                "summary": (product.features[0] if product.features else ""),
            }
            write_deal(asin, payload, tags_map.get(asin, []))


if __name__ == "__main__":
    main()

