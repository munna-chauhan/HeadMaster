#!/usr/bin/env node
// Cross-platform Python resolver with cached lookup.
// Cache file: .claude/cache/python-interpreter (gitignored).
// On cache hit + executable still present → spawn it.
// On miss/stale → probe python3 → py3 → python → py, write cache, spawn.
// Strips the project bin/ shim directory from PATH to prevent recursion.
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const shimDir = path.resolve(__dirname, '..', '..', 'bin');
const hmRoot = path.resolve(__dirname, '..', '..');
const cacheDir = path.join(hmRoot, '.claude', 'cache');
const cacheFile = path.join(cacheDir, 'python-interpreter');

const sep = process.platform === 'win32' ? ';' : ':';
const origPath = process.env.PATH || '';
const cleanPath = origPath.split(sep).filter(p => {
  try { return path.resolve(p) !== shimDir; } catch { return true; }
}).join(sep);
const env = {
  ...process.env,
  PATH: cleanPath,
  HEADMASTER_ORIG_PATH: process.env.HEADMASTER_ORIG_PATH || origPath,
};

function runAndExit(absPath) {
  const r = spawnSync(absPath, args, { stdio: 'inherit', env });
  if (r.error) return false;
  process.exit(r.status ?? 0);
}

try {
  if (fs.existsSync(cacheFile)) {
    const cached = fs.readFileSync(cacheFile, 'utf8').trim();
    if (cached && fs.existsSync(cached)) {
      runAndExit(cached);
    }
  }
} catch {}

const whichCmd = process.platform === 'win32' ? 'where' : 'which';
for (const cmd of ['python3', 'py3', 'python', 'py']) {
  const which = spawnSync(whichCmd, [cmd], { env, encoding: 'utf8' });
  if (which.status === 0 && which.stdout) {
    const abs = which.stdout.split(/\r?\n/)[0].trim();
    if (abs) {
      try {
        fs.mkdirSync(cacheDir, { recursive: true });
        fs.writeFileSync(cacheFile, abs + '\n');
      } catch {}
      runAndExit(abs);
    }
  }
}
console.error('Python interpreter not found. Install python3, py3, python, or py.');
process.exit(1);
