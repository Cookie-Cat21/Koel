#!/usr/bin/env node
/** Thin wrapper — canonical recorder lives in web/scripts. */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const r = spawnSync(process.execPath, ["scripts/record_ui_walkthrough.mjs"], {
  cwd: path.join(root, "web"),
  stdio: "inherit",
  env: process.env,
});
process.exit(r.status ?? 1);
