import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const reelRoot = resolve(here, "..");
const historyPath = join(reelRoot, "data", "reel-history.json");

const emptyHistory = () => ({ version: 1, reels: [] });

const normalizedTextKey = (value) => String(value ?? "").normalize("NFKC").trim().toLowerCase().replace(/\s+/g, " ");
const normalizedAsin = (value) => normalizedTextKey(value).toUpperCase();

const normalizedValues = (values, normalize) => [
  ...new Set((Array.isArray(values) ? values : []).map(normalize).filter(Boolean)),
];

const canonicalizeRecord = (record) => ({
  ...record,
  asins: normalizedValues(record.asins, normalizedAsin),
  families: normalizedValues(record.families, normalizedTextKey),
  categories: normalizedValues(record.categories, normalizedTextKey),
});

const stableJson = (value) => {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
};

class NormalizedKeySet extends Set {
  constructor(normalize) {
    super();
    this.normalize = normalize;
  }

  add(value) {
    return super.add(this.normalize(value));
  }

  has(value) {
    return super.has(this.normalize(value));
  }
}

const loadHistory = (filePath = historyPath) => {
  if (!existsSync(filePath)) return emptyHistory();
  try {
    const history = JSON.parse(readFileSync(filePath, "utf8"));
    return Array.isArray(history.reels) ? history : emptyHistory();
  } catch {
    return emptyHistory();
  }
};

export const mergeReelHistories = (currentHistory, generatedHistory) => {
  const records = [...(currentHistory?.reels ?? []), ...(generatedHistory?.reels ?? [])]
    .filter((record) => record && typeof record === "object" && !Array.isArray(record))
    .map(canonicalizeRecord);
  const uniqueRecords = new Map(records.map((record) => [stableJson(record), record]));
  const reels = [...uniqueRecords.entries()]
    .sort(([leftKey, left], [rightKey, right]) => {
      const leftTime = Date.parse(left.renderedAt) || 0;
      const rightTime = Date.parse(right.renderedAt) || 0;
      return leftTime - rightTime || leftKey.localeCompare(rightKey);
    })
    .map(([, record]) => record)
    .slice(-100);
  return { version: 1, reels };
};

export const mergeReelHistoryFiles = (targetHistoryFile, generatedHistoryFile) => {
  const mergedHistory = mergeReelHistories(loadHistory(targetHistoryFile), loadHistory(generatedHistoryFile));
  mkdirSync(dirname(targetHistoryFile), { recursive: true });
  writeFileSync(targetHistoryFile, `${JSON.stringify(mergedHistory, null, 2)}\n`);
  return mergedHistory;
};

const isWithinDays = (value, days, now = Date.now()) => {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) && timestamp >= now - days * 24 * 60 * 60 * 1000;
};

export const recentReelUsage = ({ asinDays = 30, historyFile = historyPath, now = Date.now() } = {}) => {
  const history = loadHistory(historyFile);
  // This is intentionally ASIN-only. Categories and product types can recur;
  // only the exact product is kept out of the recent rotation.
  const asins = new NormalizedKeySet(normalizedAsin);

  for (const reel of history.reels) {
    if (isWithinDays(reel.renderedAt, asinDays, now)) {
      for (const asin of reel.asins ?? []) {
        if (normalizedAsin(asin)) asins.add(asin);
      }
    }
  }
  return { asins };
};

export const recordRenderedReel = (reel, { videoPath, coverPath, instagramCoverPath, historyFile = historyPath, now = new Date() }) => {
  const history = loadHistory(historyFile);
  const record = {
    renderedAt: new Date(now).toISOString(),
    status: "rendered",
    asins: [...new Set(reel.deals.map((deal) => normalizedAsin(deal.asin)).filter(Boolean))],
    videoPath,
    coverPath,
    instagramCoverPath,
  };
  mkdirSync(dirname(historyFile), { recursive: true });
  writeFileSync(historyFile, `${JSON.stringify({ version: 1, reels: [...history.reels, record].slice(-100) }, null, 2)}\n`);
  return record;
};

if (resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) {
  const [command, targetHistoryFile, generatedHistoryFile] = process.argv.slice(2);
  if (command !== "--merge" || !targetHistoryFile || !generatedHistoryFile) {
    throw new Error("Usage: node reel-history.mjs --merge <target-history-file> <generated-history-file>");
  }
  mergeReelHistoryFiles(targetHistoryFile, generatedHistoryFile);
}
