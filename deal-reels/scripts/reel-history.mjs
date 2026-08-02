import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const reelRoot = resolve(here, "..");
const historyPath = join(reelRoot, "data", "reel-history.json");

const emptyHistory = () => ({ version: 1, reels: [] });

const loadHistory = () => {
  if (!existsSync(historyPath)) return emptyHistory();
  try {
    const history = JSON.parse(readFileSync(historyPath, "utf8"));
    return Array.isArray(history.reels) ? history : emptyHistory();
  } catch {
    return emptyHistory();
  }
};

const isWithinDays = (value, days, now = Date.now()) => {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) && timestamp >= now - days * 24 * 60 * 60 * 1000;
};

export const recentReelUsage = ({ asinDays = 30, familyDays = 60 } = {}) => {
  const history = loadHistory();
  const asins = new Set();
  const families = new Set();
  const categories = new Set();

  for (const reel of history.reels) {
    if (isWithinDays(reel.renderedAt, asinDays)) for (const asin of reel.asins ?? []) asins.add(asin);
    if (isWithinDays(reel.renderedAt, familyDays)) {
      for (const family of reel.families ?? []) families.add(family);
      for (const category of reel.categories ?? []) categories.add(category);
    }
  }
  return { asins, families, categories };
};

export const recordRenderedReel = (reel, { videoPath, coverPath }) => {
  const history = loadHistory();
  const record = {
    renderedAt: new Date().toISOString(),
    status: "rendered",
    asins: reel.deals.map((deal) => deal.asin),
    families: [...new Set(reel.deals.map((deal) => deal.family).filter(Boolean))],
    categories: [...new Set(reel.deals.map((deal) => deal.category).filter(Boolean))],
    videoPath,
    coverPath,
  };
  mkdirSync(dirname(historyPath), { recursive: true });
  writeFileSync(historyPath, `${JSON.stringify({ version: 1, reels: [...history.reels, record].slice(-100) }, null, 2)}\n`);
  return record;
};
