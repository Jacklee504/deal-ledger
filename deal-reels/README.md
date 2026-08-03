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
