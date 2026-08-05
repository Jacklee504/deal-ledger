import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { mergeReelHistories, recentReelUsage, recordRenderedReel } from "../scripts/reel-history.mjs";

const fixedNow = Date.parse("2026-08-03T12:00:00.000Z");

const temporaryHistory = (t, source = { version: 1, reels: [] }) => {
  const directory = mkdtempSync(join(tmpdir(), "deal-ledger-reel-history-"));
  const historyFile = join(directory, "reel-history.json");
  writeFileSync(historyFile, `${JSON.stringify(source)}\n`);
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  return historyFile;
};

test("reads legacy mixed-case history as normalized ASIN cooldown keys", (t) => {
  const historyFile = temporaryHistory(t, {
    version: 1,
    reels: [{
      renderedAt: "2026-08-02T12:00:00.000Z",
      asins: ["b0h2tznh4z"],
      families: ["Robot-Vacuum"],
      categories: ["home"],
    }],
  });

  const usage = recentReelUsage({ historyFile, now: fixedNow });
  assert.equal(usage.asins.has("B0H2TZNH4Z"), true);
  assert.deepEqual(Object.keys(usage), ["asins"]);
});

test("writes normalized ASIN cooldown keys", (t) => {
  const historyFile = temporaryHistory(t);
  const reel = {
    deals: [{ asin: "b0h2tznh4z", family: "Robot-Vacuum", category: "Home" }],
  };

  const record = recordRenderedReel(reel, {
    historyFile,
    now: fixedNow,
    videoPath: "Media/videos/archive/test/deal-ledger-reel.mp4",
    coverPath: "Media/videos/archive/test/deal-ledger-reel-cover.png",
    instagramCoverPath: "Media/videos/archive/test/deal-ledger-reel-instagram-cover.png",
  });

  assert.deepEqual(record.asins, ["B0H2TZNH4Z"]);
  assert.equal("families" in record, false);
  assert.equal("categories" in record, false);
  assert.equal(recentReelUsage({ historyFile, now: fixedNow }).asins.has("b0h2tznh4z"), true);
  assert.equal("categories" in JSON.parse(readFileSync(historyFile, "utf8")).reels[0], false);
});

test("merges concurrent cooldown histories deterministically without dropping either render", () => {
  const commonRecord = {
    renderedAt: "2026-08-01T12:00:00.000Z",
    asins: ["B000000001"],
    families: ["robot-vacuum"],
    categories: ["home"],
  };
  const currentHistory = {
    version: 1,
    reels: [commonRecord, {
      renderedAt: "2026-08-03T11:00:00.000Z",
      asins: ["B000000002"],
      families: ["headphones"],
      categories: ["Audio"],
    }],
  };
  const generatedHistory = {
    version: 1,
    reels: [{ ...commonRecord, categories: ["Home"] }, {
      renderedAt: "2026-08-03T12:00:00.000Z",
      asins: ["b000000003"],
      families: ["Air-Fryer"],
      categories: ["Kitchen"],
    }],
  };

  const merged = mergeReelHistories(currentHistory, generatedHistory);
  assert.deepEqual(merged, mergeReelHistories(generatedHistory, currentHistory));
  assert.deepEqual(merged.reels.map((record) => record.asins[0]), ["B000000001", "B000000002", "B000000003"]);
  assert.deepEqual(merged.reels.map((record) => record.categories[0]), ["home", "audio", "kitchen"]);
});
