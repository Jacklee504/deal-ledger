"""Run a non-writing Amazon UK deal-intake dry run.

SerpApi discovers Amazon UK product candidates. Bright Data then verifies the
candidate product URLs. The script writes only a redacted report when explicitly
asked; it never creates deal drafts, affiliate links, commits, or sends emails.

Usage:
  SERPAPI_API_KEY=... BRIGHTDATA_API_TOKEN=... \\
  BRIGHTDATA_DATASET_ID=... \\
  python scripts/fetch_deals_serpapi.py --dry-run --max-queries 1 \\
    --max-products 3 --report-out /tmp/deal-intake-report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "scripts" / "deal_discovery_config.json"
SERPAPI_URL = "https://serpapi.com/search.json"
BRIGHTDATA_BASE_URL = "https://api.brightdata.com/datasets/v3"
REQUIRED_ENVS = ("SERPAPI_API_KEY", "BRIGHTDATA_API_TOKEN", "BRIGHTDATA_DATASET_ID")
ASIN_PATTERN = re.compile(r"\b([A-Z0-9]{10})\b", re.IGNORECASE)
# Bright Data's Amazon UK responses currently label pounds as "GPB". Preserve
# the raw value in reports, but normalize this known provider typo before the
# ISO-currency policy check.
CURRENCY_ALIASES = {"GPB": "GBP"}


class ProviderError(RuntimeError):
    """An external provider returned an unusable response."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ProviderError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Configuration file is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ProviderError("Configuration root must be a JSON object")
    return value


def require_env() -> dict[str, str]:
    values = {name: os.getenv(name, "").strip() for name in REQUIRED_ENVS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ProviderError("Missing required environment variable(s): " + ", ".join(missing))
    return values


def request_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
                 payload: Any | None = None) -> Any:
    body = None
    request_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, method=method, headers=request_headers)
    try:
        with urlopen(request, timeout=45) as response:  # noqa: S310 - fixed provider URLs
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ProviderError(f"Provider HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Provider request failed: {exc}") from exc


def extract_asin(*values: Any) -> str | None:
    for value in values:
        match = ASIN_PATTERN.search(str(value or ""))
        if match:
            return match.group(1).upper()
    return None


def parse_price(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"(-?\d[\d,]*(?:\.\d{1,2})?)", value)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def clean_amazon_url(asin: str, marketplace: str) -> str:
    return f"https://www.{marketplace}/dp/{asin}"


def is_marketplace_url(url: str, marketplace: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    expected = marketplace.lower()
    return host == expected or host == f"www.{expected}"


def serpapi_products(api_key: str, keyword: str, marketplace: str) -> list[dict[str, Any]]:
    params = {
        "engine": "amazon",
        "amazon_domain": marketplace,
        "k": keyword,
        "api_key": api_key,
    }
    response = request_json(f"{SERPAPI_URL}?{urlencode(params)}")
    if not isinstance(response, dict):
        raise ProviderError("SerpApi returned an unexpected response type")
    if response.get("error"):
        raise ProviderError(f"SerpApi error: {response['error']}")
    for key in ("organic_results", "search_results", "products"):
        products = response.get(key)
        if isinstance(products, list):
            return [item for item in products if isinstance(item, dict)]
    return []


def discovery_candidate(result: dict[str, Any], *, keyword: str, marketplace: str,
                        minimum_discount: float, minimum_sale_price: float) -> tuple[dict[str, Any] | None, str | None]:
    source_url = str(result.get("link") or result.get("url") or result.get("product_url") or "")
    asin = extract_asin(result.get("asin"), result.get("product_id"), source_url)
    title = str(result.get("title") or "").strip()
    sale_price = parse_price(result.get("extracted_price"))
    if sale_price is None:
        sale_price = parse_price(result.get("price"))
    reference_price = parse_price(result.get("extracted_original_price"))
    if reference_price is None:
        reference_price = parse_price(result.get("original_price"))

    if not asin:
        return None, "missing ASIN"
    if source_url and not is_marketplace_url(source_url, marketplace):
        return None, "not an Amazon UK product URL"
    if not title:
        return None, "missing title"
    if sale_price is None:
        return None, "missing current price"
    if sale_price < minimum_sale_price:
        return None, "below minimum sale price"
    # Amazon search results often omit a reference price even when the product
    # page has one. Bright Data is the authoritative verification step, so do
    # not spend the entire verification budget only on results with this
    # optional search-result field.
    discount = None
    if reference_price is not None and reference_price > sale_price:
        discount = 1 - (sale_price / reference_price)

    return {
        "asin": asin,
        "keyword": keyword,
        "title": title,
        "url": clean_amazon_url(asin, marketplace),
        "serpapi_sale_price": sale_price,
        "serpapi_reference_price": reference_price,
        "serpapi_discount_pct": round(discount * 100, 2) if discount is not None else None,
    }, None


def unique_by_asin(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        asin = str(item.get("asin") or "")
        if not asin or asin in seen:
            continue
        seen.add(asin)
        unique.append(item)
    return unique


def brightdata_verify(token: str, dataset_id: str, urls: list[str], *, timeout_seconds: int = 150) -> list[dict[str, Any]]:
    if not urls:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    trigger_url = f"{BRIGHTDATA_BASE_URL}/trigger?{urlencode({'dataset_id': dataset_id, 'format': 'json'})}"
    trigger = request_json(
        trigger_url,
        method="POST",
        headers=headers,
        payload=[{"url": url} for url in urls],
    )
    if not isinstance(trigger, dict) or not trigger.get("snapshot_id"):
        raise ProviderError("Bright Data trigger response did not include snapshot_id")
    snapshot_id = str(trigger["snapshot_id"])
    deadline = time.monotonic() + timeout_seconds
    progress_url = f"{BRIGHTDATA_BASE_URL}/progress/{snapshot_id}"

    while time.monotonic() < deadline:
        progress = request_json(progress_url, headers=headers)
        status = str((progress or {}).get("status") or "").lower()
        if status == "ready":
            snapshot_url = f"{BRIGHTDATA_BASE_URL}/snapshot/{snapshot_id}?format=json"
            snapshot = request_json(snapshot_url, headers=headers)
            if isinstance(snapshot, list):
                return [item for item in snapshot if isinstance(item, dict)]
            if isinstance(snapshot, dict) and isinstance(snapshot.get("data"), list):
                return [item for item in snapshot["data"] if isinstance(item, dict)]
            raise ProviderError("Bright Data snapshot did not contain a record list")
        if status == "failed":
            raise ProviderError("Bright Data collection failed")
        time.sleep(5)

    raise ProviderError(f"Bright Data collection {snapshot_id} timed out")


def verified_record(record: dict[str, Any], *, marketplace: str, currency: str,
                    trusted_seller_terms: list[str], minimum_discount: float = 0.20,
                    minimum_sale_price: float = 20.0) -> tuple[dict[str, Any] | None, str | None]:
    url = str(record.get("url") or "")
    domain = str(record.get("domain") or "")
    source_currency = str(record.get("currency") or "").upper()
    record_currency = CURRENCY_ALIASES.get(source_currency, source_currency)
    asin = extract_asin(record.get("asin"), url)
    title = str(record.get("title") or "").strip()
    final_price = parse_price(record.get("final_price"))
    initial_price = parse_price(record.get("initial_price"))
    seller = str(record.get("buybox_seller") or record.get("seller_name") or "").strip()
    available = record.get("is_available") is True

    if not asin or not title:
        return None, "missing ASIN or title"
    if not is_marketplace_url(url, marketplace) or marketplace not in domain.lower():
        return None, "Bright Data returned a non-UK product"
    if record_currency != currency:
        return None, f"Bright Data currency is {record_currency or 'missing'}, not {currency}"
    if not available:
        return None, "not available"
    if final_price is None:
        return None, "missing final price"
    if final_price < minimum_sale_price:
        return None, "below minimum sale price"
    if not seller or not any(term.lower() in seller.lower() for term in trusted_seller_terms):
        return None, "buy-box seller is not trusted"

    if initial_price is None or initial_price <= final_price:
        return None, "no valid Bright Data reference price"
    discount = 1 - (final_price / initial_price)
    if discount < minimum_discount:
        return None, "below minimum verified discount"
    discount_pct = round(discount * 100, 2)

    return {
        "asin": asin,
        "title": title,
        "url": clean_amazon_url(asin, marketplace),
        "price": final_price,
        "reference_price": initial_price,
        "discount_pct": discount_pct,
        "currency": record_currency,
        "source_currency": source_currency,
        "available": available,
        "buybox_seller": seller,
        "image_url": record.get("image_url") or record.get("image") or "",
        "verified_at": str(record.get("timestamp") or utc_now()),
    }, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--dry-run", action="store_true", help="Required acknowledgement; no writing mode exists yet.")
    parser.add_argument("--max-queries", type=int, default=1)
    parser.add_argument("--max-products", type=int, default=3)
    parser.add_argument("--report-out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        raise ProviderError("This initial intake only supports --dry-run")
    if args.max_queries < 1 or args.max_products < 1:
        raise ProviderError("--max-queries and --max-products must be positive")

    environment = require_env()
    config = load_json(args.config)
    marketplace = str(config.get("marketplace") or "").lower()
    currency = str(config.get("currency") or "").upper()
    keywords = [str(value).strip() for value in config.get("keywords", []) if str(value).strip()]
    limits = config.get("limits") if isinstance(config.get("limits"), dict) else {}
    policy = config.get("policy") if isinstance(config.get("policy"), dict) else {}
    max_queries = min(args.max_queries, int(limits.get("max_serpapi_queries_per_run", args.max_queries)))
    max_products = min(args.max_products, int(limits.get("max_brightdata_products_per_run", args.max_products)))
    minimum_discount = float(policy.get("minimum_discount_pct", 20)) / 100
    minimum_sale_price = float(policy.get("minimum_sale_price", 20))
    trusted_seller_terms = [str(value) for value in policy.get("trusted_seller_terms", ["amazon"])]
    if marketplace != "amazon.co.uk" or currency != "GBP":
        raise ProviderError("Initial dry run is restricted to amazon.co.uk and GBP")
    if not keywords:
        raise ProviderError("No discovery keywords are configured")

    report: dict[str, Any] = {
        "schema_version": "2026-07-31-brightdata-verification-v2",
        "code_revision": os.getenv("GITHUB_SHA", "local-run"),
        "mode": "dry-run",
        "generated_at": utc_now(),
        "marketplace": marketplace,
        "currency": currency,
        "limits": {"max_queries": max_queries, "max_products": max_products},
        "discovery": {"queries": [], "candidates": [], "rejected": []},
        "verification": {"submitted": [], "accepted": [], "rejected": []},
        "next_step": "No files were written. Inspect this report before enabling draft creation.",
    }

    candidates: list[dict[str, Any]] = []
    for keyword in keywords[:max_queries]:
        products = serpapi_products(environment["SERPAPI_API_KEY"], keyword, marketplace)
        report["discovery"]["queries"].append({"keyword": keyword, "results_received": len(products)})
        for product in products:
            candidate, reason = discovery_candidate(
                product,
                keyword=keyword,
                marketplace=marketplace,
                minimum_discount=minimum_discount,
                minimum_sale_price=minimum_sale_price,
            )
            if candidate:
                candidates.append(candidate)
            else:
                report["discovery"]["rejected"].append({
                    "keyword": keyword,
                    "asin": extract_asin(product.get("asin"), product.get("link"), product.get("url")),
                    "title": str(product.get("title") or "")[:180],
                    "reason": reason,
                })

    selected = unique_by_asin(candidates)[:max_products]
    report["discovery"]["candidates"] = selected
    report["verification"]["submitted"] = [item["url"] for item in selected]

    verified = brightdata_verify(
        environment["BRIGHTDATA_API_TOKEN"],
        environment["BRIGHTDATA_DATASET_ID"],
        [item["url"] for item in selected],
    )
    for record in verified:
        normalized, reason = verified_record(
            record,
            marketplace=marketplace,
            currency=currency,
            trusted_seller_terms=trusted_seller_terms,
            minimum_discount=minimum_discount,
            minimum_sale_price=minimum_sale_price,
        )
        if normalized:
            report["verification"]["accepted"].append(normalized)
        else:
            report["verification"]["rejected"].append({
                "asin": extract_asin(record.get("asin"), record.get("url")),
                "title": str(record.get("title") or "")[:180],
                "reason": reason,
            })

    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        "[fetch_deals_serpapi] dry run complete: "
        f"{len(selected)} candidate(s) submitted, "
        f"{len(report['verification']['accepted'])} verified; report: {args.report_out}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProviderError as exc:
        print(f"[fetch_deals_serpapi] {exc}", file=sys.stderr)
        sys.exit(1)
