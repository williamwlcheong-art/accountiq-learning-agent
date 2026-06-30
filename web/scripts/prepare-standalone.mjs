import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";

const standaloneDir = ".next/standalone";
const standaloneNextDir = `${standaloneDir}/.next`;

mkdirSync(standaloneNextDir, { recursive: true });
rmSync(`${standaloneNextDir}/static`, { force: true, recursive: true });
rmSync(`${standaloneDir}/public`, { force: true, recursive: true });

cpSync(".next/static", `${standaloneNextDir}/static`, { recursive: true });

if (existsSync("public")) {
  cpSync("public", `${standaloneDir}/public`, { recursive: true });
}
