# Deal Ledger reels

This local Remotion project creates a caption-free vertical video and branded cover for Instagram Reels and TikTok. It selects three fresh, category-diverse current US deals, downloads their images, generates a calm Andrew neural voiceover, and renders an H.264 MP4 plus PNG cover.

From this directory:

```bash
npm run render:reel
```

Each run creates `../Media/videos/archive/DDMMYY-N/` containing a video/cover pair and updates `../Media/videos/latest/` with the current pair. Media is ignored by Git. `data/reel-history.json` is tracked and prevents ASIN repeats for 30 days and product-family/category repeats for 60 days.

To preview and adjust the timeline before rendering:

```bash
npm run prepare-reel
npx remotion studio --no-open
```

Each part of the narration is generated and timed separately, so every deal remains onscreen for exactly its spoken segment. It uses the free Microsoft Edge neural `Andrew` voice at a clear, moderately brisk pace. If that service is unavailable, generation falls back to the local macOS `Samantha` voice.
