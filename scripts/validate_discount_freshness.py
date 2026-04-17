"""Validate (and optionally refresh) listing prices/discounts for live deals.

Usage:
  python scripts/validate_discount_freshness.py
  python scripts/validate_discount_freshness.py --apply
  python scripts/validate_discount_freshness.py --json-out review-queue/deal-validity-report.json

Behavior:
  - Scans content/deals/*.md (excluding _index.md)
  - Fetches each deal's listing URL (listing_url/product_url/affiliate_url)
  - Extracts live sale/list prices and discount
  - Compares against listing_* values in front matter
  - Prints stale/unreachable/unknown report
  - Optional --apply writes updated listing_* price fields
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEALS_DIR = ROOT / "content" / "deals"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def split_front_matter(raw: str):
    if not raw.startswith("+++\n"):
        return None
    end = raw.find("\n+++\n", 4)
    if end == -1:
        return None
    front = raw[4:end]
    body = raw[end + 5 :]
    return front, body


def toml_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def value_to_toml(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return f'"{toml_escape(value)}"'


def upsert_line(front: str, key: str, value: Any) -> str:
    rendered = f"{key} = {value_to_toml(value)}"
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    if pattern.search(front):
        return pattern.sub(rendered, front, count=1)
    front = front.rstrip("\n")
    return f"{front}\n{rendered}\n"


def get_front_value(front: str, key: str) -> Optional[str]:
    quoted = re.search(rf'^{re.escape(key)}\s*=\s*"([^"]+)"\s*$', front, re.MULTILINE)
    if quoted:
        return quoted.group(1).strip()
    numeric = re.search(rf"^{re.escape(key)}\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*$", front, re.MULTILINE)
    if numeric:
        return numeric.group(1)
    return None


def canonicalize_amazon_url(url: str) -> str:
    parsed = urlparse(url)
    if "amazon." not in parsed.netloc:
        return url
    asin_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", url)
    if not asin_match:
        return url
    asin = asin_match.group(1)
    return f"{parsed.scheme or 'https'}://{parsed.netloc}/dp/{asin}"


def fetch_html(url: str, timeout: int) -> tuple[Optional[str], Optional[str]]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-IE,en-US;q=0.9,en;q=0.8"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace"), None
    except HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except URLError as exc:
        return None, f"network error: {exc}"
    except TimeoutError:
        return None, "timeout"


def parse_money(raw: str) -> Optional[float]:
    token_matches = re.findall(r"([0-9][0-9.,\s]{0,20})", raw or "")
    if not token_matches:
        return None
    token = token_matches[0].replace(" ", "").strip(".,")
    if not token:
        return None

    if "." in token and "," in token:
        decimal_sep = "." if token.rfind(".") > token.rfind(",") else ","
        thousand_sep = "," if decimal_sep == "." else "."
        token = token.replace(thousand_sep, "")
        token = token.replace(decimal_sep, ".")
    elif "," in token:
        if re.search(r",[0-9]{2}$", token):
            token = token.replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "." in token:
        if not re.search(r"\.[0-9]{2}$", token):
            token = token.replace(".", "")

    try:
        return float(token)
    except ValueError:
        return None


def detect_blocked_page(html_doc: str) -> bool:
    text = (html_doc or "").lower()
    blocked_markers = [
        "api-services-support@amazon.com",
        "automated access",
        "enter the characters you see below",
        "type the characters you see in this image",
        "sorry, we just need to make sure you're not a robot",
        "captcha",
    ]
    return any(marker in text for marker in blocked_markers)


def first_money_match(text: str, ordered_patterns: list[tuple[str, str]]) -> tuple[Optional[float], str]:
    for label, pattern in ordered_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        value = parse_money(m.group(1))
        if value is not None:
            return value, label
    return None, "none"


def extract_prices(html_doc: str) -> tuple[Optional[float], Optional[float], Optional[float], str]:
    sale = None
    list_price = None
    sale_source = "none"
    list_source = "none"
    core_block = ""

    core_match = re.search(
        r'<div[^>]+id="(?:corePriceDisplay_desktop_feature_div|corePrice_feature_div)"[\s\S]{0,5000}?</div>',
        html_doc,
        re.IGNORECASE,
    )
    if core_match:
        core_block = core_match.group(0)

    # Ordered sale preference: structured product price -> core buy-box DOM price.
    sale, sale_source = first_money_match(
        html_doc,
        [
            ("priceToPay", r'"priceToPay"\s*:\s*\{[^}]*"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)'),
            ("priceAmount", r'"priceAmount"\s*:\s*"([0-9][0-9.,]+)"'),
            ("displayPrice", r'"displayPrice"\s*:\s*"([^"]+)"'),
            ("priceCurrencyTagged", r'"price"\s*:\s*"(?:EUR|GBP|USD)\s*([0-9]+(?:[.,][0-9]+)?)"'),
        ],
    )

    # Ordered list/reference preference: structured comparator fields first.
    list_price, list_source = first_money_match(
        html_doc,
        [
            ("basisPrice", r'"basisPrice"\s*:\s*\{[^}]*"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)'),
            ("listPriceAmount", r'"listPrice"\s*:\s*\{[^}]*"amount"\s*:\s*([0-9]+(?:\.[0-9]+)?)'),
            ("priceBeforeDeal", r'"priceBeforeDeal"\s*:\s*"([^"]+)"'),
            ("priceWas", r'"priceWas"\s*:\s*"([^"]+)"'),
        ],
    )

    # DOM fallback: class-based visible prices inside core buy-box.
    if sale is None and core_block:
        offscreen_match = re.search(
            r'<span[^>]*class="[^"]*a-offscreen[^"]*"[^>]*>\s*([^<]+)\s*</span>',
            core_block,
            re.IGNORECASE,
        )
        if offscreen_match:
            sale = parse_money(offscreen_match.group(1))
            if sale is not None:
                sale_source = "coreOffscreen"

    if sale is None:
        scope = core_block if core_block else html_doc
        m = re.search(
            r'<span[^>]*class="[^"]*a-price-whole[^"]*"[^>]*>\s*([^<]+)\s*</span>'
            r'[\s\S]{0,80}?<span[^>]*class="[^"]*a-price-fraction[^"]*"[^>]*>\s*([^<]+)\s*</span>',
            scope,
            re.IGNORECASE,
        )
        if m:
            sale = parse_money(f"{m.group(1)}.{m.group(2)}")
            if sale is not None:
                sale_source = "wholeFraction"

    # List fallback preference: strike-through price in core block, then nearest higher core comparator.
    if list_price is None and core_block:
        strike_match = re.search(
            r'<span[^>]*class="[^"]*a-text-price[^"]*"[^>]*>[\s\S]{0,180}?<span[^>]*class="[^"]*a-offscreen[^"]*"[^>]*>\s*([^<]+)\s*</span>',
            core_block,
            re.IGNORECASE,
        )
        if strike_match:
            strike_value = parse_money(strike_match.group(1))
            if strike_value is not None and (sale is None or strike_value > sale + 0.001):
                list_price = strike_value
                list_source = "coreStrikePrice"

    if list_price is None and core_block:
        core_vals = []
        for raw in re.findall(r'<span[^>]*class="[^"]*a-offscreen[^"]*"[^>]*>\s*([^<]+)\s*</span>', core_block, re.IGNORECASE):
            val = parse_money(raw)
            if val is None:
                continue
            if 0.5 <= val <= 100000:
                core_vals.append(val)
        core_vals = sorted(set(core_vals))
        if sale is None and core_vals:
            sale = core_vals[0]
            sale_source = "coreOffscreen"
        if sale is not None and len(core_vals) >= 2:
            higher = [v for v in core_vals if v > sale + 0.001]
            if higher:
                list_price = min(higher)
                list_source = "coreNearestHigher"

    discount = None
    if sale is not None and list_price and list_price > 0:
        discount = max(0.0, min(1.0, 1 - (sale / list_price)))
    source = f"sale:{sale_source}|list:{list_source}"
    return sale, list_price, discount, source


def to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def changed(a: Optional[float], b: Optional[float], tol: float) -> bool:
    if a is None or b is None:
        return a != b
    return abs(a - b) > tol


def changed_when_both(a: Optional[float], b: Optional[float], tol: float) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) > tol


def fmt(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write updated listing price fields when stale.")
    parser.add_argument("--tolerance", type=float, default=0.01, help="Price delta tolerance before flagging stale.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds.")
    parser.add_argument("--limit", type=int, default=0, help="Max number of deals to check (0 = all).")
    parser.add_argument("--include-ok", action="store_true", help="Print [ok] rows too.")
    parser.add_argument("--json-out", default="", help="Optional report output path.")
    parser.add_argument("--fail-on-stale", action="store_true", help="Exit non-zero if any stale prices are found.")
    parser.add_argument("--fail-on-unreachable", action="store_true", help="Exit non-zero if any listing URLs cannot be fetched.")
    args = parser.parse_args()

    now_iso = datetime.now(timezone.utc).isoformat()
    checked = 0
    stale = 0
    updated = 0
    unreachable = 0
    blocked = 0
    unknown = 0
    report: list[dict[str, Any]] = []

    for path in sorted(DEALS_DIR.glob("*.md")):
        if path.name == "_index.md":
            continue
        if args.limit and checked >= args.limit:
            break

        raw = path.read_text(encoding="utf-8")
        split = split_front_matter(raw)
        if not split:
            continue
        front, body = split

        source_url = (
            get_front_value(front, "listing_url")
            or get_front_value(front, "product_url")
            or get_front_value(front, "affiliate_url")
        )
        if not source_url:
            continue

        checked += 1
        listing_url = canonicalize_amazon_url(source_url)
        html_doc, fetch_err = fetch_html(listing_url, timeout=args.timeout)

        current_sale = to_float(get_front_value(front, "listing_sale_price"))
        current_list = to_float(get_front_value(front, "listing_list_price"))
        current_discount = to_float(get_front_value(front, "listing_discount_pct"))

        row: dict[str, Any] = {
            "file": str(path.relative_to(ROOT)),
            "url": listing_url,
            "current_sale_price": current_sale,
            "current_list_price": current_list,
            "current_discount_pct": current_discount,
            "live_sale_price": None,
            "live_list_price": None,
            "live_discount_pct": None,
            "price_source": "none",
            "status": "",
            "details": "",
            "updated": False,
        }

        if fetch_err or not html_doc:
            unreachable += 1
            row["status"] = "unreachable"
            row["details"] = fetch_err or "no response body"
            print(f"[unreachable] {path.relative_to(ROOT)} ({row['details']})")
            report.append(row)
            continue

        if detect_blocked_page(html_doc):
            blocked += 1
            row["status"] = "blocked"
            row["details"] = "amazon anti-bot/captcha page detected"
            print(f"[blocked] {path.relative_to(ROOT)} (amazon anti-bot page)")
            report.append(row)
            continue

        live_sale, live_list, live_discount, price_source = extract_prices(html_doc)
        row["live_sale_price"] = live_sale
        row["live_list_price"] = live_list
        row["live_discount_pct"] = live_discount
        row["price_source"] = price_source


        if live_sale is None and live_list is None and live_discount is None:
            unknown += 1
            row["status"] = "unknown"
            row["details"] = "price parse failed"
            print(f"[unknown] {path.relative_to(ROOT)} (could not parse live pricing)")
            report.append(row)
            continue

        sale_changed = changed(current_sale, live_sale, args.tolerance)
        # If live list/discount are missing, treat as unavailable rather than stale-by-default.
        list_changed = changed_when_both(current_list, live_list, args.tolerance)
        discount_changed = changed_when_both(current_discount, live_discount, 0.001)
        is_stale = sale_changed or list_changed or discount_changed

        if not is_stale:
            row["status"] = "ok"
            row["details"] = "prices unchanged"
            if args.include_ok:
                print(
                    f"[ok] {path.relative_to(ROOT)} "
                    f"(sale {fmt(live_sale)}, list {fmt(live_list)}, discount {fmt(live_discount)})"
                )
            report.append(row)
            continue

        stale += 1
        row["status"] = "stale"
        row["details"] = (
            f"sale {fmt(current_sale)} -> {fmt(live_sale)}, "
            f"list {fmt(current_list)} -> {fmt(live_list)}, "
            f"discount {fmt(current_discount)} -> {fmt(live_discount)}"
        )
        print(f"[stale] {path.relative_to(ROOT)}")
        print(f"  sale: {fmt(current_sale)} -> {fmt(live_sale)}")
        print(f"  list: {fmt(current_list)} -> {fmt(live_list)}")
        print(f"  discount: {fmt(current_discount)} -> {fmt(live_discount)}")

        if args.apply:
            next_front = front
            if live_sale is not None:
                next_front = upsert_line(next_front, "listing_sale_price", live_sale)
            if live_list is not None:
                next_front = upsert_line(next_front, "listing_list_price", live_list)
            if live_discount is not None:
                next_front = upsert_line(next_front, "listing_discount_pct", live_discount)
            next_front = upsert_line(next_front, "listing_synced_at", now_iso)

            if next_front != front:
                path.write_text(f"+++\n{next_front.rstrip()}\n+++\n{body}", encoding="utf-8")
                updated += 1
                row["updated"] = True
        report.append(row)

    print(
        f"[validate_discount_freshness] checked={checked} stale={stale} "
        f"unreachable={unreachable} blocked={blocked} unknown={unknown} "
        f"updated={updated if args.apply else 0} apply={args.apply}"
    )

    if args.json_out:
        out = Path(args.json_out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "summary": {
                "checked": checked,
                "stale": stale,
                "unreachable": unreachable,
                "blocked": blocked,
                "unknown": unknown,
                "updated": updated if args.apply else 0,
                "apply": args.apply,
            },
            "results": report,
        }
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[validate_discount_freshness] wrote report to {out.relative_to(ROOT)}")

    should_fail = (args.fail_on_stale and stale > 0) or (
        args.fail_on_unreachable and unreachable > 0
    )
    if should_fail:
        sys.exit(2)


if __name__ == "__main__":
    main()
