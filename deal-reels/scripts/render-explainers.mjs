import { existsSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const reelRoot = resolve(here, "..");
const siteRoot = resolve(reelRoot, "..");
const outputRoot = join(siteRoot, "Media", "videos", "intro");
const publicAudio = join(reelRoot, "public", "audio");
const localPythonPackages = join(reelRoot, ".tools");
const separator = process.platform === "win32" ? ";" : ":";
const today = new Date();
const datePrefix = `${String(today.getUTCDate()).padStart(2, "0")}${String(today.getUTCMonth() + 1).padStart(2, "0")}${String(today.getUTCFullYear()).slice(-2)}`;
const variants = [
  { id: "DealLedgerExplainerSaveTime", slug: "save-time", text: "Want to spend less without hunting for deals? Deal Ledger puts worthwhile Amazon deals in one simple place. Each card shows the current price, the reference price, and the saving. Browse today’s deals for free, then request alerts for the categories or exact products you care about. Spend less. Search less. Deal Ledger." },
  { id: "DealLedgerExplainerClearPrice", slug: "clear-price", text: "Too many Amazon tabs and still no idea if the price is good? Deal Ledger makes it simple. We bring current deals together with the price and saving visible at a glance. Browse free, skip the endless search, and find the products worth a closer look. Deal Ledger: clear price context, without the noise." },
  { id: "DealLedgerExplainerPersonalAlerts", slug: "personal-alerts", text: "Why watch every deal when you only care about a few things? Deal Ledger lets you choose the categories you want to track, or request an alert for an exact product. Browse current Amazon deals for free, then make the watchlist yours. Your categories. Your timing. Deal Ledger." },
];
const onlyIndex = process.argv.indexOf("--only");
const requestedSlug = onlyIndex === -1 ? null : process.argv[onlyIndex + 1];
const selectedVariants = requestedSlug ? variants.filter((variant) => variant.slug === requestedSlug) : variants;
if (requestedSlug && selectedVariants.length !== 1) throw new Error(`Unknown explainer variant: ${requestedSlug}`);

if (!existsSync(join(reelRoot, "src", "data", "reel.json"))) throw new Error("Prepare a normal reel once before rendering explainers so live deal imagery is available.");
mkdirSync(publicAudio, { recursive: true });
mkdirSync(outputRoot, { recursive: true });
const extension = "mp3";
for (const variant of selectedVariants) {
  const audioPath = join(publicAudio, `explainer-${variant.slug}.${extension}`);
  execFileSync("python3", ["-m", "edge_tts", "--voice", "en-US-AndrewMultilingualNeural", "--rate=+12%", "--text", variant.text, "--write-media", audioPath], {
    cwd: reelRoot,
    stdio: "inherit",
    env: { ...process.env, PYTHONPATH: [localPythonPackages, process.env.PYTHONPATH].filter(Boolean).join(separator) },
  });
  const directory = join(outputRoot, `${datePrefix}-${variant.slug}`);
  const outputPath = join(directory, "deal-ledger-intro.mp4");
  mkdirSync(directory, { recursive: true });
  execFileSync("npx", ["remotion", "render", variant.id, outputPath, "--codec=h264", "--crf=18", "--log=error"], { cwd: reelRoot, stdio: "inherit" });
  console.log(`Rendered: ${outputPath}`);
}
