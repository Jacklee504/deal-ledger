# Amazon US Deal Intake: Current Architecture

## Objective

Find Amazon US deals without PA-API access while keeping publication manual and
auditable. The static site never scrapes Amazon directly and never publishes a
provider result automatically.

## Implemented flow

```text
Bright Data Products Search (documented dataset `gd_lwdb4vjm1ehb499uxs`)
  -> clean amazon.com ASIN URLs
  -> Bright Data Amazon scraper (with configured delivery ZIP)
  -> local policy and duplicate checks
  -> ignored review-queue/deals/<ASIN>.md
  -> Hugo draft preview at /deals-review/
  -> manual Amazon/SiteStripe/public-price check
  -> content/deals/<ASIN>.md
  -> Hugo deployment
```

### Responsibilities

| Stage | Source of truth | Guardrail |
| --- | --- | --- |
| Discovery | Bright Data Amazon Products Search | `amazon.com` product URLs and 10-character ASINs only |
| Verification | Separate Bright Data Amazon PDP dataset | USD, availability, image, seller and minimum price |
| Drafting | `scripts/fetch_deals_serpapi.py` | Explicit local write mode; exclusive creation only |
| Review | Hugo draft page + Amazon product page | Human checks seller, availability, and public eligibility |
| Promotion | `scripts/promote_deals.py` | One ASIN, SiteStripe/Associates URL, public price/reference price, explicit confirmation |
| Rejection | `scripts/reject_deals.py` | Records reason and suppresses the ASIN on later intake |

## Scope

- Marketplace: `amazon.com` only
- Currency: USD only
- Delivery context: ZIP in `scripts/deal_discovery_config.json`
- Search candidates with a displayed 20% reduction are preferred; records with no displayed comparison price can proceed to browser review. $20 is the minimum sale price.
- Seller policy: any disclosed Amazon Marketplace buy-box seller; human review
  decides whether it is suitable
- Publishing: local, one deal at a time

## Important limitations

- `initial_price` is a currently displayed provider comparison price, not price
  history or a “lowest ever” claim. Missing or inconsistent PDP comparison
  prices do not block a pending draft; the draft records that browser reference-price verification is required.
- Bright Data may surface Prime, coupon, member, or ZIP-specific pricing. Every
  draft is marked `price_access = "unknown"`; it cannot be promoted until a
  reviewer confirms a price available to all shoppers.
- A published deal is a manually confirmed price snapshot. It needs periodic
  human review if it stays live for a long time.
- No affiliate URL is inferred or generated. The reviewer creates it using
  Amazon Associates SiteStripe.

## Safe commands

```bash
# First verify a very small batch; writes only a report.
set -a; source .env; set +a
python scripts/fetch_deals_serpapi.py --dry-run \\
  --max-queries 1 --max-products 3 \\
  --report-out Media/brightdata-search-pdp-dry-run.json

# Intentionally create local review drafts after inspecting a dry run.
python scripts/fetch_deals_serpapi.py --write-review-drafts \\
  --max-queries 2 --max-products 6 \\
  --report-out Media/brightdata-search-pdp-review-drafts.json
python scripts/sync_review_preview.py
hugo server -D

# Reject a Prime/member/coupon-only or otherwise unsuitable result.
python scripts/reject_deals.py --asin B0XXXXXXXX --reason 'Prime-only price'

# Promote a genuine public deal after making its US SiteStripe link.
python scripts/promote_deals.py --asin B0XXXXXXXX \\
  --affiliate-url 'https://www.amazon.com/dp/B0XXXXXXXX?tag=yourtag-20' \\
  --public-price 59.99 --public-reference-price 99.99 \\
  --confirm-public-price
```

## GitHub Actions

The `serpapi-deal-intake.yml` workflow is a manually triggered dry run. It
uses a Bright Data API token secret and the existing PDP dataset variable. The
Products Search dataset ID is already configured; no Global Products account,
new credential, or new repository variable is needed. It uploads a redacted
report and cannot write drafts or publish content.

Deployment only builds the static site and validates newly added live deals;
it does not call PA-API, run an Amazon HTML scraper, or refresh prices.
