import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, rmSync, readFileSync, writeFileSync } from "node:fs";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { recentReelUsage } from "./reel-history.mjs";
import { dealContentFileForPath, dealFilesByLowercaseName } from "./deal-content-paths.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(here, "..");
const siteRoot = resolve(projectRoot, "..");
const dataDirectory = join(projectRoot, "src", "data");
const publicDirectory = join(projectRoot, "public");
const imageDirectory = join(publicDirectory, "deals");
const audioDirectory = join(publicDirectory, "audio");
const localPythonPackages = join(projectRoot, ".tools");
const fps = 30;
const dealContentDirectory = join(siteRoot, "content", "deals");
// Hugo URLs are lowercase, while ASIN-named Markdown files retain Amazon's uppercase
// convention. macOS masks that mismatch; GitHub's Linux runner does not.
const dealFiles = dealFilesByLowercaseName(dealContentDirectory);
const requestedAsins = (() => {
  const optionIndex = process.argv.indexOf("--asins");
  if (optionIndex === -1) return null;
  const value = process.argv[optionIndex + 1] ?? "";
  const asins = value.split(",").map((asin) => asin.trim().toUpperCase()).filter(Boolean);
  if (asins.length !== 3 || new Set(asins).size !== 3 || asins.some((asin) => !/^[A-Z0-9]{10}$/.test(asin))) {
    throw new Error("--asins must contain exactly three distinct ASINs, separated by commas.");
  }
  return asins;
})();

const storePaths = readFileSync(join(siteRoot, "data", "stores", "us.yaml"), "utf8")
  .split("\n")
  .map((line) => line.match(/^\s+-\s+(\/deals\/[^\s/]+)\/?\s*$/)?.[1])
  .filter(Boolean);

const parseFrontmatter = (source) => {
  const frontmatter = source.match(/^\+\+\+\s*\n([\s\S]*?)\n\+\+\+/);
  if (!frontmatter) throw new Error("Missing TOML front matter");
  const values = {};
  for (const line of frontmatter[1].split("\n")) {
    const match = line.match(/^([\w_]+)\s*=\s*(.+)$/);
    if (!match) continue;
    const [, key, rawValue] = match;
    const value = rawValue.trim();
    if (value.startsWith("[") && value.endsWith("]")) {
      try {
        values[key] = JSON.parse(value);
      } catch {
        values[key] = [];
      }
    } else if (value.startsWith('"') && value.endsWith('"')) {
      try {
        values[key] = JSON.parse(value);
      } catch {
        values[key] = value.slice(1, -1);
      }
    }
    else if (value === "true" || value === "false") values[key] = value === "true";
    else if (!Number.isNaN(Number(value))) values[key] = Number(value);
  }
  return values;
};

const classifyDeal = (title, tags) => {
  const source = `${title} ${tags.join(" ")}`.toLowerCase();
  const rules = [
    [/robot vacuum|vacuum.*mop/, "robot-vacuum", "Home"],
    [/electric toothbrush/, "electric-toothbrush", "Personal care"],
    [/headphones?|headset/, "headphones", "Audio"],
    [/speaker/, "speaker", "Audio"],
    [/smartwatch|apple watch|watch series/, "smartwatch", "Wearables"],
    [/air fryer/, "air-fryer", "Kitchen"],
    [/monitor|display/, "monitor", "Tech"],
    [/television|\btv\b/, "television", "Home entertainment"],
    [/keyboard/, "keyboard", "Tech"],
    [/\bmouse\b/, "mouse", "Tech"],
    [/desktop|computer|laptop/, "computer", "Tech"],
    [/office chair/, "office-chair", "Home office"],
  ];
  const match = rules.find(([pattern]) => pattern.test(source));
  if (match) return { family: match[1], category: match[2] };
  const fallback = tags.find((tag) => !["amazon", "amazon-us", "deals", "electronics", "audio", "gaming"].includes(tag.toLowerCase())) ?? "general";
  return { family: fallback.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""), category: "General" };
};

const normalizeProductName = (title) =>
  title
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => String.fromCharCode(Number.parseInt(code, 16)))
    .normalize("NFC")
    .replace(/\s{2,}/g, " ")
    .trim();

const pronunciationConfig = JSON.parse(readFileSync(join(projectRoot, "data", "pronunciations.json"), "utf8"));
const productNameOverrides = (pronunciationConfig.products ?? []).map((entry) => ({
  ...entry,
  matches: new RegExp(String(entry.match), "i"),
}));

const productNameOverride = (title) => productNameOverrides.find((entry) => entry.matches.test(normalizeProductName(title)));

const compactTitle = (title) => {
  const override = productNameOverride(title);
  if (override) return override.display;
  const cleaned = normalizeProductName(title)
    .replace(/\b(Combo|Rechargeable|Wireless|Bluetooth|Gaming|Amazon|Compact)\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (cleaned.length <= 42) return cleaned;
  return cleaned.slice(0, 42).replace(/\s+\S*$/, "").trim();
};

const spokenTitle = (title) => {
  const override = productNameOverride(title);
  if (override) return override.spoken;
  const source = normalizeProductName(title).toLowerCase();
  const labels = [
    [/robot vacuum|vacuum.*mop/, "a robot vacuum and mop"],
    [/electric toothbrush/, "an electric toothbrush"],
    [/headphones?|headset/, "wireless noise-cancelling headphones"],
    [/speaker/, "a Bluetooth speaker"],
    [/smartwatch|apple watch|watch series/, "a GPS smartwatch"],
    [/air fryer/, "an air fryer"],
    [/monitor|display/, "a curved gaming monitor"],
    [/television|\btv\b/, "a smart TV"],
    [/keyboard/, "a mechanical keyboard"],
    [/\bmouse\b/, "a wireless mouse"],
    [/desktop|computer|laptop/, "a laptop"],
    [/office chair/, "an office chair"],
  ];
  return labels.find(([pattern]) => pattern.test(source))?.[1] ?? "a standout deal";
};

const candidates = storePaths
  .map((dealPath) => {
    const file = dealContentFileForPath(dealFiles, dealPath);
    if (!file || !existsSync(file)) return null;
    const data = parseFrontmatter(readFileSync(file, "utf8"));
    const salePrice = Number(data.listing_sale_price ?? data.sale_price);
    const listPrice = Number(data.listing_list_price ?? data.list_price);
    const discountPct = Number(data.listing_discount_pct ?? data.discount_pct);
    const image = data.listing_image ?? data.image;
    if (data.draft || !data.affiliate_ready || !image || !Number.isFinite(salePrice) || !Number.isFinite(listPrice)) return null;
    const tags = Array.isArray(data.tags) ? data.tags.map(String) : [];
    return {
      asin: String(data.asin),
      title: String(data.listing_title ?? data.title),
      shortTitle: compactTitle(String(data.listing_title ?? data.title)),
      salePrice,
      listPrice,
      discountPct,
      image,
      ...classifyDeal(String(data.listing_title ?? data.title), tags),
    };
  })
  .filter(Boolean)
  .filter((deal) => deal.discountPct >= 0.2 && deal.salePrice >= 20)
  .sort((a, b) => b.discountPct - a.discountPct || b.listPrice - a.listPrice);

const deals = (() => {
  if (requestedAsins) {
    const candidatesByAsin = new Map(candidates.map((candidate) => [candidate.asin, candidate]));
    const requestedDeals = requestedAsins.map((asin) => candidatesByAsin.get(asin));
    if (requestedDeals.some((deal) => !deal)) throw new Error("A requested ASIN is not an eligible live US deal.");
    return requestedDeals;
  }

  const recentUsage = recentReelUsage();
  const selectedFamilies = new Set();
  const selectedCategories = new Set();
  const freshDeals = [];
  for (const candidate of candidates) {
    if (recentUsage.asins.has(candidate.asin) || recentUsage.families.has(candidate.family) || recentUsage.categories.has(candidate.category)) continue;
    if (selectedFamilies.has(candidate.family) || selectedCategories.has(candidate.category)) continue;
    freshDeals.push(candidate);
    selectedFamilies.add(candidate.family);
    selectedCategories.add(candidate.category);
    if (freshDeals.length === 3) break;
  }
  return freshDeals;
})();

if (deals.length < 3) throw new Error("Need three fresh, category-diverse live US deals to generate a reel. Add more eligible deals or wait for the cooldown.");

mkdirSync(imageDirectory, { recursive: true });
mkdirSync(audioDirectory, { recursive: true });
mkdirSync(dataDirectory, { recursive: true });
for (const entry of deals) {
  const extension = new URL(entry.image).pathname.endsWith(".png") ? "png" : "jpg";
  entry.imagePath = `deals/${entry.asin}.${extension}`;
  const destination = join(publicDirectory, entry.imagePath);
  const response = await fetch(entry.image, { headers: { "User-Agent": "DealLedgerReel/1.0" } });
  if (!response.ok) throw new Error(`Could not download ${entry.asin} image (${response.status})`);
  writeFileSync(destination, Buffer.from(await response.arrayBuffer()));
}

const money = (amount) => `$${amount.toFixed(amount % 1 === 0 ? 0 : 2)}`;
const spokenDeals = deals.map((deal, index) => {
  const lead = ["First", "Next", "And finally"][index];
  return `${lead}: ${spokenTitle(deal.title)}, ${money(deal.salePrice)}, ${Math.round(deal.discountPct * 100)} percent off.`;
});
const voiceoverSegments = [
  "Today’s strongest deals, selected by Deal Ledger.",
  ...spokenDeals,
  "Deal Ledger brings the strongest Amazon discounts together, so you can find something worth buying without the endless scroll.",
  "Skip the search. Find your next deal at Deal Ledger.",
];

const audioDurationSeconds = (file) =>
  Number(
    execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file], {
      encoding: "utf8",
    }).trim(),
  );

const createVoiceSegment = (text, index) => {
  const name = `voice-${index + 1}.mp3`;
  const destination = join(audioDirectory, name);
  try {
    execFileSync(
      "python3",
      ["-m", "edge_tts", "--voice", "en-US-AndrewMultilingualNeural", "--rate=+15%", "--text", text, "--write-media", destination],
      {
        stdio: "inherit",
        env: { ...process.env, PYTHONPATH: [localPythonPackages, process.env.PYTHONPATH].filter(Boolean).join(delimiter) },
      },
    );
  } catch {
    // Keep local rendering possible if the free neural service is unavailable.
    const aiffPath = join(audioDirectory, `voice-${index + 1}.aiff`);
    execFileSync("say", ["-v", "Samantha", "-r", "185", "-o", aiffPath, text], { stdio: "inherit" });
    execFileSync("ffmpeg", ["-y", "-i", aiffPath, "-codec:a", "libmp3lame", "-q:a", "2", destination], { stdio: "inherit" });
    rmSync(aiffPath, { force: true });
  }
  return { path: `audio/${name}`, durationInFrames: Math.ceil(audioDurationSeconds(destination) * fps) };
};

const audioSegments = voiceoverSegments.map(createVoiceSegment);

const logoSource = join(siteRoot, "static", "images", "brand", "deal-ledger-logo.svg");
const logoTarget = join(publicDirectory, "brand", "deal-ledger-logo.svg");
const circularLogoSource = join(siteRoot, "static", "images", "brand", "deal-ledger-logo-circle.svg");
const circularLogoTarget = join(publicDirectory, "brand", "deal-ledger-logo-circle.svg");
mkdirSync(dirname(logoTarget), { recursive: true });
cpSync(logoSource, logoTarget);
cpSync(circularLogoSource, circularLogoTarget);

writeFileSync(
  join(dataDirectory, "reel.json"),
  `${JSON.stringify({ audioSegments, generatedAt: new Date().toISOString(), deals }, null, 2)}\n`,
);
console.log(`Prepared a ${deals.length}-deal reel: ${deals.map((deal) => deal.asin).join(", ")}`);
