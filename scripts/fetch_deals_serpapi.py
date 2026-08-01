"""Run a manually initiated Amazon US deal-intake.

Bright Data Amazon Search discovers Amazon US product candidates. A separate
Bright Data Amazon product-page dataset then verifies candidate URLs. By
default, ``--dry-run`` writes only a redacted report.
The separate, conspicuous ``--write-review-drafts`` mode creates local review-
queue drafts from accepted Bright Data records only. It never creates affiliate
links, commits, or sends emails.

Usage:
  BRIGHTDATA_API_TOKEN=... BRIGHTDATA_DATASET_ID=... \\
  python scripts/fetch_deals_serpapi.py --dry-run --max-queries 1 \\
    --max-products 3 --report-out /tmp/deal-intake-report.json

  python scripts/fetch_deals_serpapi.py --write-review-drafts --max-queries 1 \\
    --max-products 3 --report-out /tmp/deal-intake-report.json

  # Continue with the next configured keyword(s).
  python scripts/fetch_deals_serpapi.py --write-review-drafts --query-offset 3 \\
    --max-queries 3 --max-products 9 --report-out /tmp/deal-intake-report.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "scripts" / "deal_discovery_config.json"
DEFAULT_QUEUE_DIR = ROOT / "review-queue" / "deals"
REJECTED_QUEUE_DIR = ROOT / "review-queue" / "rejected"
LIVE_DEALS_DIR = ROOT / "content" / "deals"
BRIGHTDATA_BASE_URL = "https://api.brightdata.com/datasets/v3"
BRIGHTDATA_TOKEN_ENV = "BRIGHTDATA_API_TOKEN"
DEFAULT_BRIGHTDATA_SEARCH_DATASET_ID = "gd_lwdb4vjm1ehb499uxs"
BRIGHTDATA_PDP_DATASET_ENV = "BRIGHTDATA_DATASET_ID"
ASIN_PATTERN = re.compile(r"\b([A-Z0-9]{10})\b", re.IGNORECASE)
AMAZON_ASIN_URL_PATTERN = re.compile(
    r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)",
    re.IGNORECASE,
)
SUPPORTED_MARKETPLACE = "amazon.com"
SUPPORTED_CURRENCY = "USD"
MARKETPLACE_LABEL = "Amazon US"
MARKETPLACE_TAG = "amazon-us"
CURRENCY_ALIASES: dict[str, str] = {}
MEMBER_ONLY_PRICE_PATTERN = re.compile(
    r"\b(?:prime(?:\s+(?:member|members))?\s+(?:only|exclusive|price|deal)|"
    r"(?:member|members)\s+only|exclusive\s+to\s+prime|prime-only)\b",
    re.IGNORECASE,
)


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


def brightdata_search_dataset_id(config: dict[str, Any]) -> str:
    discovery = config.get("discovery")
    if not isinstance(discovery, dict):
        raise ProviderError("Configuration 'discovery' must be an object")
    dataset_id = str(discovery.get("dataset_id") or DEFAULT_BRIGHTDATA_SEARCH_DATASET_ID).strip()
    if not re.fullmatch(r"gd_[a-z0-9]+", dataset_id):
        raise ProviderError("Configuration discovery.dataset_id must be a Bright Data dataset ID")
    return dataset_id


def require_env() -> dict[str, str]:
    required = (BRIGHTDATA_TOKEN_ENV, BRIGHTDATA_PDP_DATASET_ENV)
    values = {name: os.getenv(name, "").strip() for name in required}
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


def asin_from_amazon_url(value: Any) -> str | None:
    """Extract an ASIN from Amazon's product-path segment, never its slug."""
    match = AMAZON_ASIN_URL_PATTERN.search(str(value or ""))
    return match.group(1).upper() if match else None


def parse_price(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    if not isinstance(value, str):
        return None
    match = re.search(r"(-?\d[\d,]*(?:\.\d{1,2})?)", value)
    if not match:
        return None
    try:
        parsed = float(match.group(1).replace(",", ""))
        return parsed if math.isfinite(parsed) else None
    except ValueError:
        return None


def has_member_only_price_label(value: Any) -> bool:
    """Return true only for an explicit Prime/member price label.

    A plain ``amazon_prime: true`` means Prime delivery is available; it does
    not prove the displayed price is Prime-exclusive, so it is deliberately
    not treated as a rejection signal.
    """
    if isinstance(value, str):
        return bool(MEMBER_ONLY_PRICE_PATTERN.search(value))
    if isinstance(value, dict):
        return any(has_member_only_price_label(item) for item in value.values())
    if isinstance(value, list):
        return any(has_member_only_price_label(item) for item in value)
    return False


def clean_amazon_url(asin: str, marketplace: str) -> str:
    return f"https://www.{marketplace}/dp/{asin}"


def is_marketplace_url(url: str, marketplace: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    expected = marketplace.lower()
    return host == expected or host == f"www.{expected}"


def record_value(record: dict[str, Any], *keys: str) -> Any:
    """Find a provider field across the usual Bright Data record variants."""
    for key in keys:
        value = record.get(key)
        if isinstance(value, dict):
            for nested_key in ("value", "amount", "price", "current", "url", "href"):
                if nested_key in value:
                    value = value[nested_key]
                    break
        if value not in (None, ""):
            return value
    return None


def amazon_search_url(keyword: str, marketplace: str) -> str:
    return f"https://www.{marketplace}/s?{urlencode({'k': keyword})}"


def discovery_candidate(result: dict[str, Any], *, keyword: str, marketplace: str,
                        minimum_discount: float, minimum_sale_price: float) -> tuple[dict[str, Any] | None, str | None]:
    source_url = str(record_value(result, "url", "product_url", "product_link", "link", "product_page_url") or "")
    url_asin = asin_from_amazon_url(source_url)
    title = str(record_value(result, "title", "product_title", "name", "product_name") or "").strip()
    sale_price = parse_price(record_value(result, "final_price", "current_price", "sale_price", "price", "extracted_price"))
    reference_price = parse_price(record_value(result, "initial_price", "reference_price", "list_price", "original_price", "extracted_original_price"))
    source_currency = str(record_value(result, "currency", "price_currency") or "").upper()

    if not source_url or not is_marketplace_url(source_url, marketplace):
        return None, "not an Amazon US product URL"
    # The returned product URL, not a standalone provider identifier, is the
    # authoritative identity. This prevents a search/listing URL paired with
    # an unrelated ASIN field from being promoted to a canonical PDP URL.
    if not url_asin:
        return None, "Amazon URL is not a product URL"
    asin = url_asin
    if source_currency and CURRENCY_ALIASES.get(source_currency, source_currency) != SUPPORTED_CURRENCY:
        return None, f"Bright Data Search currency is {source_currency}, not {SUPPORTED_CURRENCY}"
    if not title:
        return None, "missing title"
    if sale_price is None:
        return None, "missing current price"
    if sale_price < minimum_sale_price:
        return None, "below minimum sale price"
    if has_member_only_price_label(result):
        return None, "Prime/member-only price"
    # Amazon search results often omit a reference price even when the product
    # page has one. Bright Data is the authoritative verification step, so do
    # not spend the entire verification budget only on results with this
    # optional search-result field.
    discount = None
    if reference_price is not None and reference_price > sale_price:
        discount = 1 - (sale_price / reference_price)
        if discount < minimum_discount:
            return None, "below minimum Bright Data Search discount"

    return {
        "asin": asin,
        "keyword": keyword,
        "title": title,
        "url": clean_amazon_url(asin, marketplace),
        "brightdata_search_sale_price": sale_price,
        "brightdata_search_reference_price": reference_price,
        "brightdata_search_discount_pct": round(discount * 100, 2) if discount is not None else None,
        "brightdata_search_discount_eligible": discount is not None,
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


def select_candidates(items: Iterable[dict[str, Any]], maximum: int) -> list[dict[str, Any]]:
    """Pick unique candidates fairly, favouring search records with a deal signal."""
    by_keyword: dict[str, list[dict[str, Any]]] = {}
    fallback_by_keyword: dict[str, list[dict[str, Any]]] = {}
    seen_asins: set[str] = set()
    for item in items:
        asin = str(item.get("asin") or "")
        keyword = str(item.get("keyword") or "")
        if not asin or not keyword or asin in seen_asins:
            continue
        seen_asins.add(asin)
        bucket = by_keyword if item.get("brightdata_search_discount_eligible") else fallback_by_keyword
        bucket.setdefault(keyword, []).append(item)

    selected: list[dict[str, Any]] = []
    for groups in (by_keyword, fallback_by_keyword):
        index = 0
        while len(selected) < maximum:
            added = False
            for candidates in groups.values():
                if index < len(candidates):
                    selected.append(candidates[index])
                    added = True
                    if len(selected) == maximum:
                        break
            if not added:
                break
            index += 1
    return selected


def brightdata_collect(token: str, dataset_id: str, inputs: list[dict[str, Any]], *,
                       collection_name: str, timeout_seconds: int = 150) -> list[dict[str, Any]]:
    """Collect one Bright Data dataset snapshot without assuming its record shape."""
    if not inputs:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    trigger_url = f"{BRIGHTDATA_BASE_URL}/trigger?{urlencode({'dataset_id': dataset_id, 'format': 'json'})}"
    trigger = request_json(
        trigger_url,
        method="POST",
        headers=headers,
        payload=inputs,
    )
    if not isinstance(trigger, dict) or not trigger.get("snapshot_id"):
        raise ProviderError(f"Bright Data {collection_name} trigger did not include snapshot_id")
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
            raise ProviderError(f"Bright Data {collection_name} snapshot did not contain a record list")
        if status == "failed":
            raise ProviderError(f"Bright Data {collection_name} collection failed")
        time.sleep(5)

    raise ProviderError(f"Bright Data {collection_name} collection {snapshot_id} timed out")


def brightdata_search_inputs(keywords: Iterable[str], marketplace: str,
                             discovery: dict[str, Any]) -> list[dict[str, Any]]:
    """Build documented Bright Data Products Search inputs for Amazon US."""
    pages = discovery.get("pages_to_search", 1)
    if isinstance(pages, bool) or not isinstance(pages, int) or pages < 1:
        raise ProviderError("Configuration discovery.pages_to_search must be a positive integer")
    return [
        {"keyword": keyword, "url": f"https://www.{marketplace}", "pages_to_search": pages}
        for keyword in keywords
    ]


def brightdata_search(token: str, dataset_id: str, inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Discover product records through Bright Data's Amazon Products Search dataset."""
    return brightdata_collect(token, dataset_id, inputs, collection_name="Amazon Search")


def search_record_keyword(record: dict[str, Any], selected_keywords: list[str]) -> str | None:
    """Associate a Search record with its submitted keyword when the dataset exposes it."""
    provider_keyword = str(record_value(record, "keyword", "search_keyword", "search_term", "query") or "").strip()
    if provider_keyword:
        for keyword in selected_keywords:
            if provider_keyword.casefold() == keyword.casefold():
                return keyword
    return selected_keywords[0] if len(selected_keywords) == 1 else None


def brightdata_verify(token: str, dataset_id: str, inputs: list[dict[str, str]], *, timeout_seconds: int = 150) -> list[dict[str, Any]]:
    """Verify configured product inputs with the separate Bright Data PDP dataset."""
    return brightdata_collect(
        token,
        dataset_id,
        inputs,
        collection_name="Amazon PDP",
        timeout_seconds=timeout_seconds,
    )


def verified_record(record: dict[str, Any], *, marketplace: str, currency: str,
                    trusted_seller_terms: list[str], minimum_discount: float = 0.20,
                    minimum_sale_price: float = 20.0) -> tuple[dict[str, Any] | None, str | None]:
    url = str(record_value(record, "url", "product_url", "product_page_url") or "")
    domain = str(record_value(record, "domain", "domain_name") or "")
    source_currency = str(record_value(record, "currency", "price_currency") or "").upper()
    record_currency = CURRENCY_ALIASES.get(source_currency, source_currency)
    record_asin = extract_asin(record_value(record, "asin", "product_asin", "product_id"))
    url_asin = asin_from_amazon_url(url)
    title = str(record_value(record, "title", "product_title", "name") or "").strip()
    final_price = parse_price(record_value(record, "final_price", "current_price", "sale_price", "price"))
    initial_price = parse_price(record_value(record, "initial_price", "reference_price", "list_price", "original_price"))
    seller = str(record_value(record, "buybox_seller", "seller_name", "seller") or "").strip()
    available = record.get("is_available") is True

    # Bright Data can label a variant page with its parent ASIN. The product
    # URL is the identifier we actually submitted and is therefore the
    # authoritative identity for this intake. Keep the provider field in the
    # report/draft for diagnosis, but never let it change the product URL.
    if not url_asin or not title:
        return None, "missing URL ASIN or title"
    asin = url_asin
    if not is_marketplace_url(url, marketplace) or marketplace not in domain.lower():
        return None, "Bright Data returned a non-US product"
    if record_currency != currency:
        return None, f"Bright Data currency is {record_currency or 'missing'}, not {currency}"
    if not available:
        return None, "not available"
    if has_member_only_price_label(record):
        return None, "Prime/member-only price"
    if final_price is None:
        return None, "missing final price"
    if final_price < minimum_sale_price:
        return None, "below minimum sale price"
    if not seller:
        return None, "missing buy-box seller"
    if trusted_seller_terms and not any(term.lower() in seller.lower() for term in trusted_seller_terms):
        return None, "buy-box seller is not trusted"

    image_url = str(record_value(record, "image_url", "image", "main_image", "image_link") or "").strip()
    if not image_url:
        return None, "missing product image"
    reference_price = initial_price if initial_price is not None and initial_price > final_price else None
    discount_pct = round((1 - (final_price / reference_price)) * 100, 2) if reference_price is not None else None

    return {
        "asin": asin,
        "provider_asin": record_asin or "",
        "url_asin": url_asin,
        "provider_asin_matches_url": record_asin == url_asin if record_asin else None,
        "title": title,
        "url": clean_amazon_url(asin, marketplace),
        "price": final_price,
        # A missing or inconsistent comparison price is not proof that this is
        # ineligible. Preserve it for the reviewer, but never fabricate a
        # reference price or a discount from it.
        "provider_reference_price": initial_price,
        "reference_price": reference_price,
        "discount_pct": discount_pct,
        "currency": record_currency,
        "source_currency": source_currency,
        "available": available,
        "buybox_seller": seller,
        "image_url": image_url,
        "verified_at": str(record.get("timestamp") or utc_now()),
    }, None


def toml_string(value: Any) -> str:
    """Return a TOML-compatible basic string without front-matter injection."""
    return json.dumps("" if value is None else str(value), ensure_ascii=True)


def validate_review_draft(draft_text: str) -> None:
    """Reject malformed front matter before an exclusive queue file is created."""
    segments = draft_text.split("+++\n", 2)
    if len(segments) != 3:
        raise ProviderError("Refusing to create a review draft with malformed front matter")
    try:
        tomllib.loads(segments[1])
    except tomllib.TOMLDecodeError as exc:
        raise ProviderError(f"Refusing to create a review draft with invalid TOML: {exc}") from exc


def render_review_draft(verified: dict[str, Any], discovery: dict[str, Any] | None = None) -> str:
    """Render one pending, non-affiliate deal draft from a verified provider record."""
    asin = str(verified["asin"])
    title = str(verified["title"])
    price = float(verified["price"])
    reference_price = parse_price(verified.get("reference_price"))
    discount_pct = parse_price(verified.get("discount_pct"))
    has_verified_reference = reference_price is not None and reference_price > price and discount_pct is not None
    verified_at = str(verified["verified_at"])
    discovery = discovery or {}
    keyword = str(discovery.get("keyword") or "")
    tags = ["amazon", MARKETPLACE_TAG]
    if keyword:
        tags.append(keyword)
    summary = f"Verified {MARKETPLACE_LABEL} candidate: {price:.2f} {verified['currency']}."
    if has_verified_reference:
        summary = (
            f"Verified {MARKETPLACE_LABEL} deal: {price:.2f} {verified['currency']} "
            f"(was {reference_price:.2f} {verified['currency']})."
        )

    front_matter = [
        "+++",
        f"title = {toml_string(title)}",
        f"date = {toml_string(utc_now())}",
        "draft = true",
        'review_status = "pending"',
        f"asin = {toml_string(asin)}",
        "affiliate_ready = false",
        'intake_source = "brightdata-search+brightdata-pdp"',
        f"marketplace = {toml_string(SUPPORTED_MARKETPLACE)}",
        f"currency = {toml_string(verified['currency'])}",
        f"sale_price = {price:.2f}",
        f"product_url = {toml_string(verified['url'])}",
        f"image = {toml_string(verified.get('image_url') or '')}",
        # These are the provider-backed fields consumed by the live Hugo
        # templates. They make promotion self-contained and avoid attempting
        # to fetch Amazon pages directly after approval.
        'listing_source = "brightdata"',
        f"listing_url = {toml_string(verified['url'])}",
        f"listing_title = {toml_string(title)}",
        f"listing_summary = {toml_string(summary)}",
        f"listing_image = {toml_string(verified.get('image_url') or '')}",
        f"listing_sale_price = {price:.2f}",
        f"listing_synced_at = {toml_string(verified_at)}",
        # Bright Data can surface Prime/coupon/member prices. The provider
        # cannot prove public eligibility, so the reviewer must confirm it at
        # promotion time. Unknown prices never become live automatically.
        'price_access = "unknown"',
        "price_review_required = true",
        f"reference_price_status = {toml_string('provider-reported' if has_verified_reference else 'unavailable-requires-browser-verification')}",
        f"tags = {json.dumps(tags, ensure_ascii=True)}",
        'categories = ["deals"]',
        f"summary = {toml_string(summary)}",
        'verification_provider = "brightdata-pdp"',
        f"verification_url = {toml_string(verified['url'])}",
        f"verified_at = {toml_string(verified_at)}",
        f"verified_provider_asin = {toml_string(verified.get('provider_asin') or '')}",
        f"verified_url_asin = {toml_string(verified.get('url_asin') or verified['asin'])}",
        f"verified_currency_source = {toml_string(verified.get('source_currency') or '')}",
        f"verified_buybox_seller = {toml_string(verified.get('buybox_seller') or '')}",
        "+++",
        "",
        f"Verified by Bright Data at {verified_at}. Review the current Amazon US price, availability, and seller before promoting.",
        "",
    ]
    if has_verified_reference:
        discount = float(discount_pct) / 100
        reference_fields = [
            f"list_price = {reference_price:.2f}",
            f"discount_pct = {discount:.6f}",
        ]
        product_url_index = front_matter.index(f"product_url = {toml_string(verified['url'])}")
        front_matter[product_url_index:product_url_index] = reference_fields
        listing_price_index = front_matter.index(f"listing_synced_at = {toml_string(verified_at)}")
        front_matter[listing_price_index:listing_price_index] = [
            f"listing_list_price = {reference_price:.2f}",
            f"listing_discount_pct = {discount:.6f}",
            'reference_price_basis = "brightdata_initial_price"',
        ]
    provider_reference_price = parse_price(verified.get("provider_reference_price"))
    if provider_reference_price is not None:
        front_matter.insert(-3, f"brightdata_pdp_reference_price = {provider_reference_price:.2f}")
    discovery_fields = [
        f"brightdata_search_keyword = {toml_string(keyword)}",
        f"brightdata_search_candidate_url = {toml_string(discovery.get('url') or '')}",
        f"brightdata_search_sale_price = {toml_string(discovery.get('brightdata_search_sale_price') or '')}",
        f"brightdata_search_reference_price = {toml_string(discovery.get('brightdata_search_reference_price') or '')}",
        f"brightdata_search_discount_pct = {toml_string(discovery.get('brightdata_search_discount_pct') or '')}",
    ]
    front_matter[-3:-3] = discovery_fields
    return "\n".join(front_matter)


def asin_from_draft(path: Path) -> str | None:
    """Read a draft's explicit ASIN, falling back to its safe filename."""
    try:
        match = re.search(r'^asin\s*=\s*"([A-Z0-9]{10})"\s*$', path.read_text(encoding="utf-8"), re.MULTILINE)
    except OSError:
        return None
    if match:
        return match.group(1).upper()
    return path.stem.upper() if ASIN_PATTERN.fullmatch(path.stem.upper()) else None


def known_asin_states() -> dict[str, str]:
    """Return ASINs already pending, rejected, or live so intake is idempotent."""
    states: dict[str, str] = {}
    for directory, state in (
        (DEFAULT_QUEUE_DIR, "pending"),
        (REJECTED_QUEUE_DIR, "rejected"),
        (LIVE_DEALS_DIR, "live"),
    ):
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            if path.name == "_index.md":
                continue
            asin = asin_from_draft(path)
            if asin:
                states.setdefault(asin, state)
    return states


def build_brightdata_inputs(urls: Iterable[str], verification: dict[str, Any]) -> list[dict[str, str]]:
    """Build only documented Bright Data input fields for each clean URL."""
    # The configured Bright Data Amazon US scraper accepts a delivery ZIP.
    # Its `language` field is a console-only selector and rejects API values,
    # so do not send it as part of the dataset input.
    defaults = {"zipcode": str(verification.get("zipcode") or "").strip()}
    return [
        {"url": url, **{key: value for key, value in defaults.items() if value}}
        for url in urls
    ]


def write_review_draft(verified: dict[str, Any], discovery: dict[str, Any] | None = None,
                       *, queue_dir: Path = DEFAULT_QUEUE_DIR) -> bool:
    """Create a draft once, without ever replacing an existing queued ASIN."""
    asin = str(verified.get("asin") or "").upper()
    if not ASIN_PATTERN.fullmatch(asin):
        raise ProviderError(f"Refusing to write a draft with an invalid ASIN: {asin!r}")

    draft_text = render_review_draft(verified, discovery)
    validate_review_draft(draft_text)
    queue_dir.mkdir(parents=True, exist_ok=True)
    destination = queue_dir / f"{asin}.md"
    try:
        with destination.open("x", encoding="utf-8") as draft:
            draft.write(draft_text)
    except FileExistsError:
        print(f"[brightdata_deal_intake] skip {asin}: queued draft already exists")
        return False
    try:
        display_destination = destination.relative_to(ROOT)
    except ValueError:
        display_destination = destination
    print(f"[brightdata_deal_intake] queued review draft: {display_destination}")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Write only the report; never create review drafts.")
    mode.add_argument(
        "--write-review-drafts",
        action="store_true",
        help="Explicit local-only mode: create pending review drafts from accepted Bright Data records.",
    )
    parser.add_argument("--max-queries", type=int, default=1)
    parser.add_argument("--max-products", type=int, default=3)
    parser.add_argument(
        "--query-offset",
        type=int,
        default=0,
        help="Zero-based offset into configured keywords (use this to continue with later categories).",
    )
    parser.add_argument("--report-out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_queries < 1 or args.max_products < 1 or args.query_offset < 0:
        raise ProviderError("--max-queries and --max-products must be positive; --query-offset cannot be negative")

    config = load_json(args.config)
    marketplace = str(config.get("marketplace") or "").lower()
    currency = str(config.get("currency") or "").upper()
    keywords = [str(value).strip() for value in config.get("keywords", []) if str(value).strip()]
    limits = config.get("limits") if isinstance(config.get("limits"), dict) else {}
    policy = config.get("policy") if isinstance(config.get("policy"), dict) else {}
    max_queries = min(args.max_queries, int(limits.get("max_brightdata_search_queries_per_run", args.max_queries)))
    max_products = min(args.max_products, int(limits.get("max_brightdata_products_per_run", args.max_products)))
    minimum_discount = float(policy.get("minimum_discount_pct", 20)) / 100
    minimum_sale_price = float(policy.get("minimum_sale_price", 20))
    trusted_seller_terms = [str(value) for value in policy.get("trusted_seller_terms", ["amazon"])]
    verification = config.get("verification") if isinstance(config.get("verification"), dict) else {}
    discovery = config.get("discovery") if isinstance(config.get("discovery"), dict) else {}
    if marketplace != SUPPORTED_MARKETPLACE or currency != SUPPORTED_CURRENCY:
        raise ProviderError("Initial intake is restricted to amazon.com and USD")
    if not keywords:
        raise ProviderError("No discovery keywords are configured")
    selected_keywords = keywords[args.query_offset : args.query_offset + max_queries]
    if not selected_keywords:
        raise ProviderError("--query-offset is beyond the configured keyword list")
    search_dataset_id = brightdata_search_dataset_id(config)
    search_inputs = brightdata_search_inputs(selected_keywords, marketplace, discovery)
    environment = require_env()

    mode = "dry-run" if args.dry_run else "write-review-drafts"
    report: dict[str, Any] = {
        "schema_version": "2026-08-01-brightdata-search-pdp-v3",
        "code_revision": os.getenv("GITHUB_SHA", "local-run"),
        "mode": mode,
        "generated_at": utc_now(),
        "marketplace": marketplace,
        "currency": currency,
        "providers": {
            "discovery": "brightdata-amazon-products-search",
            "discovery_dataset_id": search_dataset_id,
            "verification": "brightdata-amazon-pdp",
        },
        "limits": {
            "max_queries": max_queries,
            "max_products": max_products,
            "query_offset": args.query_offset,
            "configured_keywords_selected": selected_keywords,
        },
        "discovery": {"queries": [], "candidates": [], "rejected": [], "skipped_known": []},
        "verification": {"submitted": [], "inputs": [], "accepted": [], "rejected": []},
        "drafts": {"created": [], "skipped_existing": [], "skipped_known": []},
        "next_step": "No review drafts were written. Inspect this report before any manual draft-writing run.",
    }

    candidates: list[dict[str, Any]] = []
    search_records = brightdata_search(
        environment[BRIGHTDATA_TOKEN_ENV],
        search_dataset_id,
        search_inputs,
    )
    records_by_keyword: dict[str, list[dict[str, Any]]] = {keyword: [] for keyword in selected_keywords}
    for product in search_records:
        keyword = search_record_keyword(product, selected_keywords)
        if keyword is None:
            report["discovery"]["rejected"].append({
                "keyword": "",
                "asin": extract_asin(record_value(product, "asin", "product_asin", "product_id")),
                "title": str(record_value(product, "title", "product_title", "name") or "")[:180],
                "reason": "Bright Data Search record did not identify a submitted keyword",
            })
            continue
        records_by_keyword[keyword].append(product)
    for keyword in selected_keywords:
        products = records_by_keyword[keyword]
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
                    "asin": (
                        extract_asin(record_value(product, "asin", "product_asin", "product_id"))
                        or asin_from_amazon_url(record_value(product, "url", "product_url", "link"))
                    ),
                    "title": str(record_value(product, "title", "product_title", "name") or "")[:180],
                    "reason": reason,
                })

    selected = select_candidates(candidates, max_products)
    known = known_asin_states()
    unreviewed: list[dict[str, Any]] = []
    for candidate in selected:
        asin = str(candidate["asin"])
        if asin in known:
            report["discovery"]["skipped_known"].append({"asin": asin, "state": known[asin]})
        else:
            unreviewed.append(candidate)
    selected = unreviewed
    submitted_asins = {str(item["asin"]) for item in selected}
    report["discovery"]["candidates"] = selected
    report["verification"]["submitted"] = [item["url"] for item in selected]
    verification_inputs = build_brightdata_inputs(report["verification"]["submitted"], verification)
    report["verification"]["inputs"] = verification_inputs

    verified = brightdata_verify(
        environment[BRIGHTDATA_TOKEN_ENV],
        environment[BRIGHTDATA_PDP_DATASET_ENV],
        verification_inputs,
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
            if normalized["asin"] in submitted_asins:
                report["verification"]["accepted"].append(normalized)
            else:
                report["verification"]["rejected"].append({
                    "asin": normalized["asin"],
                    "title": normalized["title"][:180],
                    "reason": "Bright Data ASIN was not among submitted candidates",
                })
        else:
            report["verification"]["rejected"].append({
                "asin": extract_asin(record_value(record, "asin", "product_asin", "product_id")) or asin_from_amazon_url(record_value(record, "url", "product_url")),
                "title": str(record_value(record, "title", "product_title", "name") or "")[:180],
                "reason": reason,
            })

    if args.write_review_drafts:
        discoveries = {str(item["asin"]): item for item in selected}
        for accepted in report["verification"]["accepted"]:
            asin = str(accepted["asin"])
            if asin in known:
                report["drafts"]["skipped_known"].append({"asin": asin, "state": known[asin]})
                continue
            if write_review_draft(accepted, discoveries.get(asin)):
                report["drafts"]["created"].append(asin)
            else:
                report["drafts"]["skipped_existing"].append(asin)
        report["next_step"] = (
            "Pending drafts were created only for accepted Bright Data records. "
            "Review each draft locally before promotion."
        )

    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"[brightdata_deal_intake] {mode} complete: "
        f"{len(selected)} candidate(s) submitted, "
        f"{len(report['verification']['accepted'])} verified, "
        f"{len(report['drafts']['created'])} draft(s) created; report: {args.report_out}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProviderError as exc:
        print(f"[brightdata_deal_intake] {exc}", file=sys.stderr)
        sys.exit(1)
