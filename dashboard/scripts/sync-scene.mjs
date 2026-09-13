// Copy the simulator's MuJoCo scene and meshes into public/sim so the free-look view renders the
// same model the simulation runs. Source of truth stays in cognibot_ws/src/cognibot_sim.
import { copyFileSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const simDir = resolve(here, "../../cognibot_ws/src/cognibot_sim");
const robot = process.env.ROBOT ?? "so101";
const out = resolve(here, "../public/sim", robot);

const robotYaml = readFileSync(join(simDir, "robots", robot, "robot.yaml"), "utf8");
const scenePath = join(simDir, /^\s+scene:\s*(\S+)/m.exec(robotYaml)[1]);
const tintBlock = /tint_materials:\n((?:\s+- .+\n)+)/.exec(robotYaml);
const tintMaterials = tintBlock ? [...tintBlock[1].matchAll(/- (\S+)/g)].map((m) => m[1]) : [];

let xml = readFileSync(scenePath, "utf8");
const meshdir = /<compiler[^>]*meshdir="([^"]+)"/.exec(xml)?.[1] ?? ".";
const assetDir = resolve(dirname(scenePath), meshdir);
const files = [...new Set([...xml.matchAll(/\bfile="([^"]+)"/g)].map((m) => m[1]))];

rmSync(out, { recursive: true, force: true });
mkdirSync(join(out, "assets"), { recursive: true });
for (const file of files) copyFileSync(join(assetDir, file), join(out, "assets", file));
xml = xml.replace(/(<compiler[^>]*meshdir=")[^"]+(")/, "$1assets$2");
writeFileSync(join(out, "scene.xml"), xml);
writeFileSync(
  join(out, "manifest.json"),
  JSON.stringify({ robot, scene: "scene.xml", assets: files, tintMaterials }, null, 2),
);
console.log(`sync-scene: ${robot} scene + ${files.length} meshes -> public/sim/${robot}`);
