# Deal Ledger reels

This local Remotion project creates a caption-free vertical video and branded covers for Instagram Reels and TikTok. It selects three fresh, category-diverse current US deals, downloads their images, generates a calm Andrew neural voiceover, and renders an H.264 MP4, a vertical video cover, and a 3:4 Instagram thumbnail.

From this directory:

```bash
npm run render:reel
```

To render a deliberate, category-led selection rather than the automatic fresh mix:

```bash
npm run render:reel -- --asins B0CQXMXJC5,B01MTB55WH,B0BRKPVZB4
```

Each run creates `../Media/videos/archive/DDMMYY-N/` containing the video and cover assets, and updates `../Media/videos/latest/`. Use `deal-ledger-reel-instagram-cover.png` as the Instagram thumbnail; its 3:4 layout exactly matches the 270.95 × 361.26 px Instagram cover frame. Media is ignored by Git. `data/reel-history.json` is tracked and prevents ASIN repeats for 30 days and product-family/category repeats for 60 days.

## Scheduled GitHub Actions reel handoff

**Scheduled Deal Ledger reel** runs at 14:00 UTC every Tuesday and Friday. It never publishes site changes or posts to social media. Each scheduled run uses the renderer's automatic selection, which reads the current live US store listing and selects three eligible, fresh, category-diverse deals. If fewer than three suitable deals exist, the render exits with the clear `Need three fresh, category-diverse live US deals` error and produces no media artifact.

A successful run verifies the video and covers, then retains a three-day Actions artifact named `deal-ledger-reel-<run id>`. Downloading it yields `Media/videos/` (including `archive/` and `latest/`) plus `render-report.json`.

After a verified scheduled render, the read-only render job transfers only `deal-reels/data/reel-history.json` through a one-day internal Actions artifact to a separate scheduled-only persistence job. That job alone has repository write permission and commits only that history file to the default branch, making the renderer's ASIN, product-family, and category cooldowns survive between GitHub runners. If the default branch changes concurrently, it retries up to three times from a fresh checkout, merging both cooldown histories before committing. The history write is skipped for failed renders and manual controlled runs; manual runs receive no write-capable job. This cannot change deal content, publish the site, or post socially.

The same workflow can also be run manually. Leave **Optional: exactly three eligible, live US deal ASINs for a controlled render** blank to use the automatic selection, or supply three comma-separated ASINs to exercise a specific live US trio. R2 is never touched by scheduled runs. A manual run uploads only when **Explicitly upload the verified output to R2** is set to true; otherwise it works without R2 credentials. When requested, the upload verifies the credentials and writes to the isolated `social/scheduled-reels/<GitHub run id>/` prefix, without publishing or overwriting social assets.

## GitHub Actions render capability test

Run **Deal Ledger reel render capability test** manually from the repository's Actions tab. It performs a real 1080 × 1920 three-deal render on `ubuntu-24.04`, then verifies the following before keeping a three-day downloadable artifact:

- Node, Python, Edge TTS, FFmpeg, FFprobe, and Remotion are available;
- renderer source passes lint and TypeScript checks;
- the MP4 is H.264, 1080 × 1920, at least 15 seconds long, and has audio;
- the TikTok cover is 1080 × 1920 and the Instagram cover is 1080 × 1440.

`src/data/reel.json` is generated and deliberately ignored by Git. `npm run lint` creates a non-renderable local fixture only when that file is absent, so a fresh GitHub runner can type-check the renderer. The real preparation step always replaces it with current live deal data before rendering.

The workflow never publishes to social media. To also prove the R2 handoff, set **Upload the verified output to R2** to true and configure these repository settings first:

- Secrets: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` (the account-specific S3 endpoint);
- Variable: `R2_BUCKET`;
- Optional variable: `R2_PUBLIC_BASE_URL` (for example, `https://media.example.com`) to test that uploaded media can be fetched publicly.

R2 test uploads use the isolated `social/render-smoke/<GitHub run id>/` prefix and do not publish or overwrite social assets.

To preview and adjust the timeline before rendering:

```bash
npm run prepare-reel
npx remotion studio --no-open
```

Each part of the narration is generated and timed separately, so every deal remains onscreen for exactly its spoken segment. It uses the free Microsoft Edge neural `Andrew` voice at a clear, moderately brisk pace. If that service is unavailable, generation falls back to the local macOS `Samantha` voice.
# Pinned profile introductions

Render the three 20-second Deal Ledger introduction videos (three hooks/layouts intended to be posted a few days apart):

```bash
npm run render:explainers
```

They are saved outside the deployed site under `Media/videos/intro/<date>-<variant>/`. They use live deal imagery already prepared by the normal reel workflow.
