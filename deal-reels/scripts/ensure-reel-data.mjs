import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const reelRoot = resolve(here, "..");
const generatedDataPath = join(reelRoot, "src", "data", "reel.json");
const fixturePath = join(reelRoot, "data", "reel.fixture.json");

if (!existsSync(generatedDataPath)) {
  mkdirSync(dirname(generatedDataPath), { recursive: true });
  copyFileSync(fixturePath, generatedDataPath);
  console.log("Created a local reel-data fixture for static checks.");
}
