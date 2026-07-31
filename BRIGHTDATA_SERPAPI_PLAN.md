# Amazon Deal Intake Plan: SerpApi + Bright Data

## Purpose

Replace the legacy PA-API-dependent candidate intake with a scheduled, review-first
pipeline for Amazon UK deals:

1. SerpApi discovers candidate Amazon UK products from focused keyword searches.
2. Bright Data's Amazon product URL scraper verifies the candidates with a current
   product-page snapshot.
3. The site stores a price snapshot and writes only review-queue drafts.
4. A human approves a draft, creates the approved affiliate link through Amazon's
   permitted tooling, and promotes it to `content/deals/`.

No provider result is published automatically.

## Why Both Providers Are Needed

The Bright Data scraper currently configured in this project requires one or more
product `url` inputs. It is a product verifier/tracker, not a deal-discovery source.

| Responsibility | Provider | Output used by this project |
| --- | --- | --- |
| Find new products for a keyword | SerpApi Amazon search | ASIN, title, product URL, visible price/reference-price data |
| Verify a specific product | Bright Data Amazon scraper | Current price, reference price, availability, buy-box seller, image, category, timestamp |
| Decide whether to queue it | Local policy | Candidate accepted/rejected with a reason |
| Price history and deduplication | Local state | Observations keyed by marketplace + ASIN |
| Affiliate link and publication | Human + existing promotion script | Approved live deal |

## Scope and Non-goals

### In scope

- Amazon UK (`amazon.co.uk`) and GBP only for the first release.
- Scheduled discovery, verification, history, and review-draft creation.
- Conservative seller, availability, and discount checks.
- Reusing the existing `review-queue/deals/` and promotion workflow.
- Updating the README and GitHub Actions configuration for the new intake.

### Not in scope for the first release

- Automatic publishing or automatic affiliate-link construction.
- A direct Amazon scraper, bot-evasion logic, or CAPTCHA handling in this repo.
- Broad, all-category crawling.
- Historical "lowest ever" claims. The local history begins when this pipeline is
  deployed; Keepa can be evaluated later if that claim becomes important.
- A user-facing price tracker. Existing alerts run only against live, approved deals.

## Required Account Setup

Create the following GitHub Actions secrets; never commit or paste their values in
repository files or chat.

| Secret | Purpose |
| --- | --- |
| `SERPAPI_API_KEY` | Amazon UK keyword discovery |
| `BRIGHTDATA_API_TOKEN` | Bright Data product URL verification |

Bright Data setup must use the **Amazon Scraper API** already configured in the
dashboard, not the paid Amazon Products Global Dataset. The scraper identifier used
by its API examples is expected to be `gd_l7q7dkf244hwjntr0`; implementation will
keep it configurable as `BRIGHTDATA_DATASET_ID` rather than hard-code it.

Optional repository variable (not secret):

```text
BRIGHTDATA_DATASET_ID=gd_l7q7dkf244hwjntr0
```

Before enabling the schedule, confirm in the Bright Data dashboard that a product
URL from `amazon.co.uk` returns `domain` equal to `https://www.amazon.co.uk/` and
`currency` equal to `GBP`. The code will reject any other market/currency even if a
provider returns it.

## Proposed Repository Changes

| Path | Change |
| --- | --- |
| `scripts/deal_discovery_config.json` | New versioned list of UK search keywords, categories, limits, and policy settings. |
| `scripts/fetch_deals_serpapi.py` | New discovery and orchestration script. Calls SerpApi, filters candidates, invokes Bright Data, persists state, and writes review drafts. |
| `scripts/brightdata_client.py` | Small standard-library API client for Bright Data async trigger, progress polling, and snapshot download. |
| `.state/deal-price-history.json` | Private operational state keyed by marketplace and ASIN; persisted to the existing `state` branch, not committed to `main`. |
| `.state/deal-intake-dedupe.json` | Tracks recently queued/rejected ASINs and prevents repeat drafts. |
| `.github/workflows/serpapi-deal-intake.yml` | Scheduled/manual workflow. Restores and persists state, runs the intake, commits review drafts only. |
| `README.md` | Replaces PA-API intake setup instructions with the new provider setup and runbook. |
| `scripts/fetch_deals.py` | Retained initially as legacy PA-API code; documented as deprecated rather than deleted during the first rollout. |

The exact file names may be adjusted during implementation if existing state-branch
helpers make a different layout safer.

## Data Flow

```text
GitHub Actions (daily)
  -> SerpApi: Amazon UK keyword searches
  -> local candidate filter and ASIN dedupe
  -> Bright Data: asynchronous product URL batch
  -> local verification and price-history update
  -> review-queue/deals/<marketplace>-<asin>.md
  -> existing manual preview and promotion process
  -> existing live-deal listing sync and alert workflows
```

### 1. SerpApi discovery

The job runs a small, versioned keyword list against `amazon.co.uk`. It keeps only
results with a valid ASIN or Amazon product URL and enough visible data to evaluate
as a candidate. It derives a clean, non-affiliate URL in this form:

```text
https://www.amazon.co.uk/dp/<ASIN>
```

It does not pass a SerpApi URL, search-result URL, tracking parameter, or affiliate
tag to Bright Data.

### 2. Candidate pre-filter

Before spending a Bright Data record, reject a candidate if any of the following is
true:

- it is not an `amazon.co.uk` result;
- it has no ASIN, no current price, or no title;
- its ASIN has already been queued or rejected within the dedupe window;
- it does not match an allowed category/keyword policy.

Amazon search results often omit comparison-price information. That is not a
discovery-stage rejection: the result may consume one Bright Data verification
record, where the full product-page price and reference-price policy is applied.

Initial throughput: at most 6 SerpApi searches and 15 Bright Data product checks per
day. Limits belong in configuration, not source code.

### 3. Bright Data verification

Submit the clean URLs to Bright Data as one asynchronous batch. The client will:

1. trigger a collection and record the returned snapshot ID;
2. poll its status with a bounded timeout;
3. download the JSON snapshot once the status is ready;
4. retain the raw provider response as a temporary workflow artifact only;
5. normalize the verified fields used by the queue and history.

The job will fail closed if Bright Data returns the wrong marketplace, a non-GBP
currency, missing availability, missing final price/reference price, an insufficient
verified reduction, an untrusted buy-box seller, or a malformed ASIN/URL.

### 4. Local verification policy

Initial policy values (all configuration-driven):

| Rule | Initial value |
| --- | --- |
| Marketplace | `amazon.co.uk` only |
| Currency | `GBP` only |
| Minimum reduction | 20% |
| Minimum sale price | GBP 20 |
| Availability | `is_available == true` |
| Seller | Amazon buy box / explicitly trusted seller only |
| Draft expiry | 24 hours after last verification |
| Queue dedupe | 7 days after creation or rejection |

`initial_price` is a provider/Amazon displayed comparison price. It permits wording
such as “was £X” only when it is present. It does not establish a historical-low
claim. The generated draft will preserve the source and verification timestamp.

### 5. Price history and drafts

For every Bright Data-verified product, store a compact observation such as:

```json
{
  "marketplace": "amazon.co.uk",
  "asin": "B012345678",
  "checked_at": "2026-08-01T07:00:00Z",
  "price": 49.99,
  "reference_price": 79.99,
  "currency": "GBP",
  "available": true,
  "buybox_seller": "Amazon"
}
```

For an accepted candidate, create a review draft with:

- title, ASIN, clean retailer URL, image, category/tags;
- current and reference price, calculated discount, and verification time;
- `draft = true` and a review status such as `pending`;
- a 24-hour expiry time;
- source metadata identifying SerpApi discovery and Bright Data verification;
- no affiliate tag.

Existing `scripts/sync_review_preview.py` can expose these drafts for local review.
Only after a human promotion adds a live deal under `content/deals/` must
`python3 scripts/sync_listing_from_urls.py` run, as required by `AGENTS.md`.

## Workflow Behaviour

`serpapi-deal-intake.yml` will support both:

- `workflow_dispatch` with optional safe limits for testing; and
- a daily schedule after manual verification succeeds.

It will:

1. check out `main` and restore state from the `state` branch;
2. run the intake script with repository secrets;
3. upload a redacted JSON report as an artifact;
4. commit new/updated `review-queue/deals/` drafts to `main` only when there are
   meaningful changes;
5. persist only state files to the `state` branch;
6. never commit API responses containing unnecessary product detail or credentials.

If either API is unavailable, the job should log a concise error, leave existing
drafts untouched, and not publish or remove a deal.

## Testing and Rollout

### Phase 0 — account acceptance

- Add both GitHub secrets.
- Confirm the Bright Data scraper accepts a single `amazon.co.uk` product URL.
- Confirm its returned domain and currency are UK/GBP.
- Confirm SerpApi returns Amazon UK ASINs/URLs for one configured keyword.

### Phase 1 — local dry run

- Run one SerpApi keyword and cap Bright Data at three URLs.
- Inspect the normalized report and ensure no US/USD records pass.
- Confirm a valid item creates exactly one review draft.
- Confirm a second run creates no duplicate draft.
- Check that no generated URL contains an affiliate tag.

### Phase 2 — manual workflow run

- Run `workflow_dispatch` with the same safe cap.
- Verify the state branch and review queue are updated correctly.
- Preview the queue locally with `python scripts/sync_review_preview.py`.
- Promote one approved deal, add its approved affiliate link manually, and run
  `python3 scripts/sync_listing_from_urls.py`.

### Phase 3 — daily operation

- Enable the daily schedule at six discovery searches and fifteen verification
  records maximum.
- Review queue quality, duplicate rate, and provider usage for one week.
- Adjust keywords, seller policy, and thresholds before raising the caps.

## Acceptance Criteria

The first implementation is complete when:

- a manual GitHub workflow run finds Amazon UK candidates through SerpApi;
- only clean Amazon UK product URLs are sent to Bright Data;
- US/USD and invalid/third-party/unavailable results are rejected;
- verified candidates create non-live review drafts with current timestamps;
- reruns do not duplicate queue entries;
- price observations persist across runs on the `state` branch;
- no API key, raw credential, or affiliate tag is committed;
- no deal is published or emailed without the existing human approval step.

## Decisions Made and Open Decisions

### Decided

- Use SerpApi for discovery and Bright Data's URL scraper for verification.
- Keep the existing review-first workflow.
- Start Amazon UK/GBP only.
- Do not purchase the Amazon Products Global Dataset.

### Resolve before enabling the daily schedule

1. Confirm Bright Data's scraper allowance/rate card in this account and its UK URL
   support.
2. Choose the first 6–12 keyword/category themes.
3. Confirm which sellers count as trusted beyond Amazon itself, if any.
4. Confirm the Amazon Associate account/link-generation status; until then, drafts
   use only clean product URLs.
5. Confirm whether the GBP 20 floor and 20% minimum reduction suit the site.
