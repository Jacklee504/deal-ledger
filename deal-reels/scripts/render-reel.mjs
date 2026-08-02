import { copyFileSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { recordRenderedReel } from "./reel-history.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const reelRoot = resolve(here, "..");
const siteRoot = resolve(reelRoot, "..");
const outputDirectory = join(siteRoot, "Media", "videos");
const archiveRoot = join(outputDirectory, "archive");
const latestDirectory = join(outputDirectory, "latest");
const prepareArgs = process.argv.slice(2);

execFileSync("npm", ["run", "prepare-reel", ...(prepareArgs.length > 0 ? ["--", ...prepareArgs] : [])], { cwd: reelRoot, stdio: "inherit" });
const reel = JSON.parse(readFileSync(join(reelRoot, "src", "data", "reel.json"), "utf8"));
const generatedAt = new Date(reel.generatedAt);
const datePrefix = `${String(generatedAt.getUTCDate()).padStart(2, "0")}${String(generatedAt.getUTCMonth() + 1).padStart(2, "0")}${String(generatedAt.getUTCFullYear()).slice(-2)}`;
mkdirSync(archiveRoot, { recursive: true });
const existingRunNumbers = readdirSync(archiveRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name.match(new RegExp(`^${datePrefix}-(\\d+)$`))?.[1])
  .filter(Boolean)
  .map(Number);
const runNumber = Math.max(0, ...existingRunNumbers) + 1;
const runName = `${datePrefix}-${runNumber}`;
const archiveDirectory = join(archiveRoot, runName);
const videoPath = join(archiveDirectory, "deal-ledger-reel.mp4");
const coverPath = join(archiveDirectory, "deal-ledger-reel-cover.png");
const instagramCoverPath = join(archiveDirectory, "deal-ledger-reel-instagram-cover.png");
const latestVideoPath = join(latestDirectory, "deal-ledger-reel.mp4");
const latestCoverPath = join(latestDirectory, "deal-ledger-reel-cover.png");
const latestInstagramCoverPath = join(latestDirectory, "deal-ledger-reel-instagram-cover.png");

mkdirSync(archiveDirectory, { recursive: true });
mkdirSync(latestDirectory, { recursive: true });
execFileSync("npx", ["remotion", "render", "DealLedgerReel", videoPath, "--codec=h264", "--crf=18", "--log=error"], { cwd: reelRoot, stdio: "inherit" });
execFileSync("npx", ["remotion", "still", "DealLedgerCover", coverPath, "--log=error"], { cwd: reelRoot, stdio: "inherit" });
execFileSync("npx", ["remotion", "still", "DealLedgerInstagramCover", instagramCoverPath, "--log=error"], { cwd: reelRoot, stdio: "inherit" });
copyFileSync(videoPath, latestVideoPath);
copyFileSync(coverPath, latestCoverPath);
copyFileSync(instagramCoverPath, latestInstagramCoverPath);

recordRenderedReel(reel, {
  videoPath: `Media/videos/archive/${runName}/deal-ledger-reel.mp4`,
  coverPath: `Media/videos/archive/${runName}/deal-ledger-reel-cover.png`,
  instagramCoverPath: `Media/videos/archive/${runName}/deal-ledger-reel-instagram-cover.png`,
});
console.log(`Rendered: ${videoPath}`);
console.log(`Cover: ${coverPath}`);
console.log(`Instagram cover: ${instagramCoverPath}`);
