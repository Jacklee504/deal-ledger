# Amazon US Deal Intake: Current Architecture

## Objective

Find Amazon US deals without PA-API access while keeping publication manual and
auditable. The static site never scrapes Amazon directly and never publishes a
provider result automatically.

## Implemented flow

```text
SerpApi keyword search
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
| Discovery | SerpApi Amazon US search | `amazon.com` product URLs and 10-character ASINs only |
| Verification | Bright Data Amazon scraper | USD, availability, image, seller, minimum price and reduction |
| Drafting | `scripts/fetch_deals_serpapi.py` | Explicit local write mode; exclusive creation only |
| Review | Hugo draft page + Amazon product page | Human checks seller, availability, and public eligibility |
| Promotion | `scripts/promote_deals.py` | One ASIN, SiteStripe/Associates URL, public price/reference price, explicit confirmation |
| Rejection | `scripts/reject_deals.py` | Records reason and suppresses the ASIN on later intake |

## Scope

- Marketplace: `amazon.com` only
- Currency: USD only
- Delivery context: ZIP in `scripts/deal_discovery_config.json`
- Initial threshold: 20% off and $20 minimum sale price
- Seller policy: any disclosed Amazon Marketplace buy-box seller; human review
  decides whether it is suitable
- Publishing: local, one deal at a time

## Important limitations

- `initial_price` is a currently displayed provider comparison price, not price
  history or a “lowest ever” claim.
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
  --report-out Media/serpapi-brightdata-dry-run.json

# Intentionally create local review drafts after inspecting a dry run.
python scripts/fetch_deals_serpapi.py --write-review-drafts \\
  --max-queries 2 --max-products 6 \\
  --report-out Media/serpapi-brightdata-review-drafts.json
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
uses repository secrets for the two API keys and a repository variable for the
dataset ID, then uploads a redacted report artifact. It cannot write drafts or
publish content.

Deployment only builds the static site and validates newly added live deals;
it does not call PA-API, run an Amazon HTML scraper, or refresh prices.
