# Deal Ledger (Hugo)

Static Hugo deals site with:
- provider-backed Amazon US deal discovery
- manual review and publishing safeguards
- GitHub Actions deploy to GitHub Pages

## Amazon US deal workflow

This project deliberately does not scrape Amazon product pages directly or
publish discovered prices automatically. Bright Data Products Search discovers
products and a separate Bright Data PDP dataset verifies a small batch of product pages; the static Hugo review page
lets you inspect the result before any live content is created.

### One-time setup

1. Put the credentials in local `.env` (it is ignored by Git):

   ```bash
   BRIGHTDATA_API_TOKEN=...
   BRIGHTDATA_DATASET_ID=...
   ```

2. Configure Amazon US discovery in
   [`scripts/deal_discovery_config.json`](scripts/deal_discovery_config.json):
   - `keywords` are sent to Bright Data Products Search. Its documented default
     dataset ID is configured already; no Global Products account or extra
     credential is needed. `discovery.dataset_id` is only an optional override.
   - `verification.zipcode` is the US delivery ZIP used for the Bright Data
     snapshot; set it to the ZIP whose availability you want to represent.
   - `minimum_discount_pct` and `minimum_sale_price` are the first-pass filter.
   - An empty `trusted_seller_terms` allows any marketplace buy-box seller;
     seller identity remains visible in the review draft.

3. Add the same two values to GitHub Actions if you want remote dry-run
   reports:
   - `BRIGHTDATA_API_TOKEN` as a repository secret
   - `BRIGHTDATA_DATASET_ID` as a repository variable

### Daily operating flow

1. Start with a small, non-writing verification run. It consumes provider
   credits but cannot create a draft, affiliate link, commit, or email:

```bash
set -a; source .env; set +a
python scripts/fetch_deals_serpapi.py --dry-run \\
    --max-queries 1 --max-products 3 \\
    --report-out Media/brightdata-search-pdp-dry-run.json
```

   Or run **Bright Data Search and PDP US deal-intake dry run** from the Actions
   tab and download its report artifact.

2. If the report looks sensible, intentionally create local review drafts:

```bash
set -a; source .env; set +a
python scripts/fetch_deals_serpapi.py --write-review-drafts \\
  --max-queries 2 --max-products 6 \\
  --report-out Media/brightdata-search-pdp-review-drafts.json
python scripts/sync_review_preview.py
```

   To continue with later configured categories instead of repeating the first
   keyword, add `--query-offset 2` (or another zero-based offset).

   Drafts live only in `review-queue/deals/`; generated preview pages are
   drafts and cannot deploy. Intake will never overwrite a pending draft and
   will skip ASINs already pending, rejected, or live.

3. Run the local static review page:

```bash
hugo server -D
```

   Open [`http://localhost:1313/deals-review/`](http://localhost:1313/deals-review/).
   Check the product page yourself, including the current price, buy-box seller,
   availability, and whether the price applies to everyone.

4. For a genuine public deal, create a US Amazon Associates SiteStripe link
   yourself and promote the exact ASIN. You must supply the current public
   price—not a Prime/member/coupon-only price—and a public reference price:

```bash
python scripts/promote_deals.py --asin B0XXXXXXXX \\
  --affiliate-url 'https://www.amazon.com/dp/B0XXXXXXXX?tag=yourtag-20' \\
  --public-price 59.99 --public-reference-price 99.99 \\
  --confirm-public-price
```

   A valid `https://amzn.to/...` SiteStripe short link is also accepted. The
   promotion command writes a complete `content/deals/<ASIN>.md`, supplies the
   required provider-backed `listing_*` metadata, and runs the repository's
   metadata sync check. It refuses an untagged Amazon URL, an unchecked price,
   an invalid price reduction, an existing live ASIN, or a non-pending draft.

5. Reject unsuitable candidates rather than letting them reappear:

```bash
python scripts/reject_deals.py --asin B0XXXXXXXX --reason 'Prime-only price'
```

   This archives the draft under `review-queue/rejected/`, records the reason,
   and suppresses that ASIN on future intake runs. Run
   `python scripts/sync_review_preview.py` after either promotion or rejection
   to refresh the static page.

### What each price means

- Bright Data's `initial_price` is a current comparison/reference price, not
  product price history. It is useful as an initial deal filter, not proof that
  a product is historically cheap.
- Bright Data can surface a Prime, coupon, or ZIP-specific offer. Every draft
  is therefore marked `price_access = "unknown"` and cannot be promoted until
  you confirm a public price.
- A published price is a manually confirmed snapshot. It can change after
  publishing, so review active deals periodically before promoting them in
  alerts or calling them time-sensitive.

### GitHub Actions

- **Bright Data Search and PDP US deal-intake dry run** is manual only and uploads
  a report. It does not write content or publish deals.
- Deployment no longer runs PA-API, direct Amazon page fetches, or automatic
  price refreshes. It verifies metadata on newly added live deal files before
  building the static site.

### 5b) Review tag relevance (title/category/url based)
Suggest tags that match each item based on product signals (without using description text):
```bash
python scripts/review_tags.py
```

Apply suggested tags:
```bash
python scripts/review_tags.py --apply
```

### 6) Parse Discord alert submissions
If Formspree is connected to a Discord webhook channel, parse incoming messages into a clean queue:
```bash
DISCORD_BOT_TOKEN=xxx DISCORD_CHANNEL_ID=123 python scripts/parse_discord_alerts.py --output review-queue/alerts.json
```

CSV output:
```bash
DISCORD_BOT_TOKEN=xxx DISCORD_CHANNEL_ID=123 python scripts/parse_discord_alerts.py --format csv --output review-queue/alerts.csv
```

Incremental mode (only fetch messages after the last processed message ID):
```bash
DISCORD_BOT_TOKEN=xxx DISCORD_CHANNEL_ID=123 python scripts/parse_discord_alerts.py --incremental --output review-queue/alerts.json
```

### 7) Exact-item instant email alerts
Send email alerts when deals matching `exact_items` requests are discounted:
```bash
SMTP_HOST=smtp.example.com SMTP_PORT=587 SMTP_USERNAME=user SMTP_PASSWORD=pass SMTP_FROM=alerts@dealledger.eu python scripts/send_exact_item_alerts.py
```

Dry run:
```bash
python scripts/send_exact_item_alerts.py --dry-run
```

### 7b) Send sample emails locally (no GitHub Actions)
Use one helper script to send sample alert emails directly:
```bash
python scripts/send_sample_email.py --to you@example.com --type exact
python scripts/send_sample_email.py --to you@example.com --type category --query audio
python scripts/send_sample_email.py --to you@example.com --type keyword --query headphones
python scripts/send_sample_email.py --to you@example.com --type weekly_digest
```

Required env vars:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`

State files used:
- `.state/exact-item-subscriptions.json` (request registry)
- `.state/exact-item-alert-state.json` (dedupe / last sent discount)

Automation:
- `.github/workflows/exact-item-alerts.yml` runs every 30 minutes.
- It parses new Discord submissions, sends exact-item alert emails, and persists `.state` updates on the `state` branch (not `main`).
- `.github/workflows/sample-exact-item-email.yml` is a manual test workflow to send a branded sample email to any recipient.
- `.github/workflows/sample-signup-option-email.yml` is a manual test workflow for category, keyword, and weekly-digest sample emails.

## Search and alerts behavior
- Deals search uses local fuzzy matching (Fuse.js), synonym expansion, and fallback recommendations.
- Alerts form supports hidden inferred categories on submit:
  - `inferred_categories`
  - `effective_categories`
  - `exact_items`
  This is backend-facing only (no visible suggestion UI).
- Deal cards/single pages prefer `listing_*` fields when present, then fall back to manual front matter values.

## Market datasets (`data/stores`)
- Market membership is now driven by country files under `data/stores/` (for example `data/stores/ie.yaml`, `data/stores/us.yaml`).
- Each file defines a `market` code, a display `label`, and a `deals` list of canonical deal paths.
- Example:
  ```yaml
  market: ie
  label: IE
  deals:
    - /deals/example-deal-slug/
  ```
- Add a new country by creating `data/stores/<code>.yaml` and adding market-specific content pages under `content/<code>/...`.
- The market selector only enables countries whose home page exists (for example `/ca/`), so you can prepare datasets before launch.
- For non-English markets, localize user-facing deal metadata (`title`, `summary`, and `tags`) to the market language.

## Deploy
- `.github/workflows/hugo.yml` builds and deploys to `gh-pages`.
- GitHub Pages should serve from `gh-pages` root.

## Future additions (agreed)
- Add a `Country` field to the alerts signup form so requests are region-aware.
- Use selected country + inferred categories to shape alert sends (not exact-tag only matching).
- Start with Ireland-first operations, then add additional Amazon Associate programs by country in phases.
- Add country-aware retailer URL routing (same product intent, different locale/store links).
- Keep affiliate-first publishing as the long-term direction while still allowing selected placeholders when needed.
- Add queue hygiene automation (example: auto-expire or archive unapproved deal candidates after X days).
- Add URL-driven search entry points from home/category chips and keep refining fuzzy relevance.
- Keep current deal-detail subpage templates available and re-enable item subpages later if deeper product pages are needed again.
- Continue publishing evergreen, manually written posts for SEO and internal linking.
- Diversify affiliate stack beyond Amazon over time (for example Awin/Partnerize/CJ), while keeping Amazon as primary initially.
- Revisit repo privacy/deploy architecture later (private source repo + public build-output repo) if code visibility becomes a higher priority.
