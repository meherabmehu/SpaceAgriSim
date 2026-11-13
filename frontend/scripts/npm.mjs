/**
 * The frontend's npm toolchain, without a JSON file in the repository.
 *
 * npm reads two files, `package.json` and `package-lock.json`, and there is no way to make it
 * read anything else. This repository may not hold a `.json` file, so the manifest lives in
 * `dependencies.toml` and the lock in `dependencies.lock.mjs`, and this script materialises both
 * into a temporary directory *outside* the checkout for exactly as long as npm needs them.
 *
 * What it does on every call:
 *
 *   1. writes the two manifests into `<tmp>/spaceagrisim-frontend/<hash>/`,
 *   2. runs `npm ci` there when that tree has no `node_modules` yet,
 *   3. deletes the manifests again, keeping only `node_modules`,
 *   4. points `frontend/node_modules` at `<hash>/node_modules`,
 *   5. runs the requested command with that directory's `.bin` first on PATH.
 *
 * So the JSON exists only while npm is reading it, only outside the repository, and it is gone
 * before the command that needed it returns. `--clean` removes the whole tree and the symlink.
 *
 *     node scripts/npm.mjs ci                 # materialise + npm ci
 *     node scripts/npm.mjs lint               # any script named in dependencies.toml
 *     node scripts/npm.mjs --audit            # npm audit --audit-level=high
 *     node scripts/npm.mjs --exec playwright install --with-deps chromium
 *     node scripts/npm.mjs --refresh-lock     # re-resolve and rewrite dependencies.lock.mjs
 *     node scripts/npm.mjs --where            # print the temporary directory in use
 *     node scripts/npm.mjs --clean            # delete the temporary directory and the symlink
 */
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { lockfile } from "../dependencies.lock.mjs";

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const NODE_MODULES = path.join(FRONTEND, "node_modules");
const LOCK_MODULE = path.join(FRONTEND, "dependencies.lock.mjs");
const MANIFEST_FILE = path.join(FRONTEND, "dependencies.toml");
const WORK_ROOT = process.env.SPACEAGRISIM_NPM_WORKDIR
  || path.join(os.tmpdir(), "spaceagrisim-frontend");

/**
 * A reader for the subset of TOML `dependencies.toml` uses.
 *
 * That file is hand-kept and deliberately simple: scalar strings, booleans, quoted keys for the
 * names TOML's bare-key rule forbids (`test:e2e`, `@eslint/js`), and one table per section. A
 * full TOML implementation would be a dependency; this is the grammar the file actually has.
 *
 * Two things keep it honest. `backend/tests/test_zero_json_policy.py` parses the same file with
 * Python's `tomllib` and pins the scripts, the dependency set and the version ranges, so a
 * manifest that lost an entry fails the backend suite. And `npm ci` refuses to install when the
 * generated manifest disagrees with the lock, so a reader that mis-read a line fails the
 * frontend job on its first command.
 */
function parseToml(text) {
  const result = {};
  let table = result;
  const unescape = (body) => body.replace(/\\(u[0-9a-fA-F]{4}|.)/g, (_, escaped) => {
    if (escaped[0] === "u") return String.fromCharCode(parseInt(escaped.slice(1), 16));
    return { '"': '"', "\\": "\\", n: "\n", t: "\t", r: "\r" }[escaped] ?? escaped;
  });
  text.split(/\r?\n/).forEach((raw, index) => {
    const line = raw.trim();
    if (!line || line.startsWith("#")) return;
    const section = /^\[([^\]]+)\]$/.exec(line);
    if (section) {
      table = result[section[1].trim()] ??= {};
      return;
    }
    const entry = /^(?:"((?:[^"\\]|\\.)*)"|([A-Za-z0-9_-]+))\s*=\s*(.+)$/.exec(line);
    if (!entry) throw new Error(`${MANIFEST_FILE}:${index + 1}: cannot parse ${line}`);
    const key = entry[1] === undefined ? entry[2] : unescape(entry[1]);
    const value = entry[3].trim();
    if (value.startsWith('"')) {
      const literal = /^"((?:[^"\\]|\\.)*)"$/.exec(value);
      if (!literal) throw new Error(`${MANIFEST_FILE}:${index + 1}: unterminated string`);
      table[key] = unescape(literal[1]);
    } else if (value === "true" || value === "false") {
      table[key] = value === "true";
    } else if (/^-?\d+$/.test(value)) {
      table[key] = Number(value);
    } else {
      throw new Error(`${MANIFEST_FILE}:${index + 1}: unsupported value ${value}`);
    }
  });
  return result;
}

/** `dependencies.toml` as the manifest object npm expects, in npm's own key order. */
function readManifest() {
  const toml = parseToml(fs.readFileSync(MANIFEST_FILE, "utf8"));
  const manifest = {
    name: toml.name,
    private: toml.private,
    version: toml.version,
    type: toml.type,
    description: toml.description,
  };
  for (const key of ["scripts", "dependencies", "devDependencies"]) {
    if (toml[key]) manifest[key] = toml[key];
  }
  return manifest;
}

const manifest = readManifest();

/** The two npm manifests, serialised the way npm writes them. */
const MANIFESTS = {
  "package.json": `${JSON.stringify(manifest, null, 2)}\n`,
  "package-lock.json": `${JSON.stringify(lockfile, null, 2)}\n`,
};

/** A directory name that changes when either manifest changes, so a stale install is not reused. */
function fingerprint() {
  const digest = createHash("sha256");
  for (const [name, body] of Object.entries(MANIFESTS)) {
    digest.update(name);
    digest.update(body);
  }
  return digest.digest("hex").slice(0, 16);
}

function workDir() {
  return path.join(WORK_ROOT, fingerprint());
}

/**
 * Refuse to write anywhere inside the checkout.
 *
 * The whole point of this script is that npm's JSON lives outside the repository. If an
 * environment variable or a future edit pointed it inside, the policy would be broken silently,
 * so it fails instead.
 */
function assertOutsideRepository(directory) {
  const relative = path.relative(FRONTEND, path.resolve(directory));
  if (!relative.startsWith("..") && !path.isAbsolute(relative)) {
    throw new Error(
      `refusing to materialise npm manifests inside the repository: ${directory} ` +
      `is inside ${FRONTEND}. Set SPACEAGRISIM_NPM_WORKDIR to a directory outside it.`,
    );
  }
}

function writeManifests(directory) {
  assertOutsideRepository(directory);
  fs.mkdirSync(directory, { recursive: true });
  for (const [name, body] of Object.entries(MANIFESTS)) {
    fs.writeFileSync(path.join(directory, name), body, "utf8");
  }
}

/** Delete the manifests once npm has finished with them; only node_modules stays behind. */
function deleteManifests(directory) {
  for (const name of Object.keys(MANIFESTS)) {
    fs.rmSync(path.join(directory, name), { force: true });
  }
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: "inherit", ...options });
  if (result.error) throw result.error;
  return result.status ?? 1;
}

/** The directory whose manifests are on disk right now, so a signal can still clean up. */
let materialised = null;

/** Run an npm subcommand in the temporary directory, with the manifests present. */
function npmInWorkDir(args, { directory = workDir() } = {}) {
  writeManifests(directory);
  materialised = directory;
  try {
    return run(process.env.NPM || "npm", args, { cwd: directory });
  } finally {
    deleteManifests(directory);
    materialised = null;
  }
}

// An interrupted install must not leave the manifests behind. npm runs in the same process
// group, so a Ctrl-C reaches both; the parent removes the files before it goes.
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => {
    if (materialised) deleteManifests(materialised);
    process.exit(128 + (signal === "SIGINT" ? 2 : signal === "SIGTERM" ? 15 : 1));
  });
}

/** Point `frontend/node_modules` at the installed tree, replacing whatever was there. */
function linkNodeModules(directory) {
  const installed = path.join(directory, "node_modules");
  if (!fs.existsSync(installed)) {
    throw new Error(`npm ci reported success but ${installed} is missing`);
  }
  const current = fs.lstatSync(NODE_MODULES, { throwIfNoEntry: false });
  if (current?.isSymbolicLink() && fs.readlinkSync(NODE_MODULES) === installed) return;
  fs.rmSync(NODE_MODULES, { recursive: true, force: true });
  fs.symlinkSync(installed, NODE_MODULES, "junction");
}

function binPath(directory) {
  const bin = path.join(directory, "node_modules", ".bin");
  return `${bin}${path.delimiter}${process.env.PATH ?? ""}`;
}

/** Install if this exact manifest has no tree yet, then make it resolvable from frontend/. */
function ensureInstalled() {
  const directory = workDir();
  if (!fs.existsSync(path.join(directory, "node_modules"))) {
    process.stdout.write(`installing ${Object.keys(manifest.dependencies ?? {}).length + Object.keys(manifest.devDependencies ?? {}).length} frontend dependencies into ${directory}\n`);
    const status = npmInWorkDir(["ci", "--no-audit", "--no-fund"], { directory });
    if (status !== 0) process.exit(status);
  }
  linkNodeModules(directory);
  return directory;
}

function runScript(name, extraArgs) {
  const script = manifest.scripts?.[name];
  if (!script) {
    const known = Object.keys(manifest.scripts ?? {}).join(", ");
    throw new Error(`no script named "${name}" in dependencies.toml (have: ${known})`);
  }
  const directory = ensureInstalled();
  const command = extraArgs.length ? `${script} ${extraArgs.join(" ")}` : script;
  const status = run(command, [], {
    cwd: FRONTEND,
    shell: true,
    env: { ...process.env, PATH: binPath(directory) },
  });
  // Vite, vitest and playwright all print to stdout; nothing else has to be rewritten.
  return status;
}

function refreshLock() {
  const directory = workDir();
  writeManifests(directory);
  const status = run(process.env.NPM || "npm",
    ["install", "--package-lock-only", "--no-audit", "--no-fund"], { cwd: directory });
  deleteManifests(directory);
  if (status !== 0) return status;
  const resolved = JSON.parse(fs.readFileSync(path.join(directory, "package-lock.json"), "utf8"));
  const header = fs.readFileSync(LOCK_MODULE, "utf8").split("export const lockfile =")[0];
  fs.writeFileSync(LOCK_MODULE, `${header}export const lockfile = ${JSON.stringify(resolved, null, 2)};\n`, "utf8");
  process.stdout.write(`rewrote ${path.relative(FRONTEND, LOCK_MODULE)} (${resolved.packages ? Object.keys(resolved.packages).length : 0} packages)\n`);
  return 0;
}

function clean() {
  const directory = workDir();
  const current = fs.lstatSync(NODE_MODULES, { throwIfNoEntry: false });
  if (current?.isSymbolicLink()) fs.unlinkSync(NODE_MODULES);
  fs.rmSync(WORK_ROOT, { recursive: true, force: true });
  process.stdout.write(`removed ${WORK_ROOT} and ${path.relative(FRONTEND, NODE_MODULES)}\n`);
  void directory;
  return 0;
}

const [first, ...rest] = process.argv.slice(2);

let status;
switch (first) {
  case undefined:
  case "--help":
  case "-h":
    process.stdout.write(fs.readFileSync(fileURLToPath(import.meta.url), "utf8")
      .split("*/")[0].replace(/^\/\*\*\n/, "").replace(/^ \* ?/gm, ""));
    status = 0;
    break;
  case "ci":
    status = ensureInstalled() ? 0 : 1;
    break;
  case "--audit":
    status = npmInWorkDir(["audit", "--audit-level=high"]);
    break;
  case "--refresh-lock":
    status = refreshLock();
    break;
  case "--where":
    process.stdout.write(`${ensureInstalled()}\n`);
    status = 0;
    break;
  case "--clean":
    status = clean();
    break;
  case "--exec": {
    if (!rest.length) throw new Error("--exec needs a command");
    const directory = ensureInstalled();
    const [command, ...args] = rest;
    status = run(path.join(directory, "node_modules", ".bin", command), args, {
      cwd: FRONTEND,
      env: { ...process.env, PATH: binPath(directory) },
    });
    break;
  }
  default:
    status = runScript(first, rest);
}

process.exit(status);
