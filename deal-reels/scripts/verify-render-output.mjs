import { readFileSync, statSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { basename, join, resolve } from "node:path";

const [outputDirectoryArg, ...args] = process.argv.slice(2);
const reportIndex = args.indexOf("--report");
const reportPath = reportIndex === -1 ? null : args[reportIndex + 1];

if (!outputDirectoryArg) {
  throw new Error("Usage: node scripts/verify-render-output.mjs <render-directory> [--report <path>]");
}
if (reportIndex !== -1 && !reportPath) {
  throw new Error("--report requires a path.");
}

const outputDirectory = resolve(outputDirectoryArg);
const videoPath = join(outputDirectory, "deal-ledger-reel.mp4");
const coverPath = join(outputDirectory, "deal-ledger-reel-cover.png");
const instagramCoverPath = join(outputDirectory, "deal-ledger-reel-instagram-cover.png");

const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

const pngDimensions = (file) => {
  const header = readFileSync(file).subarray(0, 24);
  const signature = "89504e470d0a1a0a";
  assert(header.subarray(0, 8).toString("hex") === signature, `${basename(file)} is not a PNG file.`);
  assert(header.subarray(12, 16).toString("ascii") === "IHDR", `${basename(file)} is missing its PNG header.`);
  return { width: header.readUInt32BE(16), height: header.readUInt32BE(20) };
};

const ffprobe = (file) =>
  JSON.parse(
    execFileSync(
      "ffprobe",
      ["-v", "error", "-show_entries", "format=duration:stream=codec_name,codec_type,width,height", "-of", "json", file],
      { encoding: "utf8" },
    ),
  );

const checkPng = (file, expected) => {
  const dimensions = pngDimensions(file);
  assert(dimensions.width === expected.width && dimensions.height === expected.height, `${basename(file)} is ${dimensions.width}x${dimensions.height}; expected ${expected.width}x${expected.height}.`);
  return { ...dimensions, bytes: statSync(file).size };
};

for (const file of [videoPath, coverPath, instagramCoverPath]) {
  assert(statSync(file).size > 0, `${basename(file)} is empty.`);
}

const probe = ffprobe(videoPath);
const videoStream = probe.streams.find((stream) => stream.codec_type === "video");
const audioStream = probe.streams.find((stream) => stream.codec_type === "audio");
const durationSeconds = Number(probe.format.duration);
assert(videoStream?.codec_name === "h264", `Video codec is ${videoStream?.codec_name ?? "missing"}; expected h264.`);
assert(videoStream.width === 1080 && videoStream.height === 1920, `Video is ${videoStream?.width ?? "?"}x${videoStream?.height ?? "?"}; expected 1080x1920.`);
assert(Boolean(audioStream), "Rendered video has no audio stream.");
assert(Number.isFinite(durationSeconds) && durationSeconds >= 15, `Video duration is ${probe.format.duration ?? "missing"}; expected at least 15 seconds.`);

const report = {
  verifiedAt: new Date().toISOString(),
  outputDirectory,
  video: {
    path: videoPath,
    codec: videoStream.codec_name,
    width: videoStream.width,
    height: videoStream.height,
    durationSeconds: Number(durationSeconds.toFixed(2)),
    bytes: statSync(videoPath).size,
    hasAudio: true,
  },
  cover: checkPng(coverPath, { width: 1080, height: 1920 }),
  instagramCover: checkPng(instagramCoverPath, { width: 1080, height: 1440 }),
};

if (reportPath) writeFileSync(resolve(reportPath), `${JSON.stringify(report, null, 2)}\n`);
console.log(JSON.stringify(report, null, 2));
