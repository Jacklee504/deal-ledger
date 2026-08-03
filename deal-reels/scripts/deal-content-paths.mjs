import { readdirSync } from "node:fs";
import { join } from "node:path";

export const dealFilesByLowercaseName = (dealContentDirectory) =>
  new Map(
    readdirSync(dealContentDirectory, { withFileTypes: true })
      .filter((entry) => entry.isFile() && entry.name.endsWith(".md"))
      .map((entry) => [entry.name.toLowerCase(), join(dealContentDirectory, entry.name)]),
  );

export const dealContentFileForPath = (dealFiles, dealPath) => {
  const slug = dealPath.split("/").filter(Boolean).at(-1);
  return slug ? dealFiles.get(`${slug}.md`.toLowerCase()) : undefined;
};
