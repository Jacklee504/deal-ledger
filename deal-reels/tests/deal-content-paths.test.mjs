import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { dealContentFileForPath, dealFilesByLowercaseName } from "../scripts/deal-content-paths.mjs";

test("resolves lowercase Hugo URLs to uppercase ASIN Markdown files", (t) => {
  const directory = mkdtempSync(join(tmpdir(), "deal-ledger-reel-paths-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const contentDirectory = join(directory, "content", "deals");
  mkdirSync(contentDirectory, { recursive: true });
  const asinFile = join(contentDirectory, "B09H8CWFNK.md");
  writeFileSync(asinFile, "+++", "utf8");

  const dealFiles = dealFilesByLowercaseName(contentDirectory);
  assert.equal(dealContentFileForPath(dealFiles, "/deals/b09h8cwfnk/"), asinFile);
});
