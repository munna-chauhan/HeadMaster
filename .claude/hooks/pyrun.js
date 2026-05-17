#!/usr/bin/env node
// Cross-platform Python resolver: python3 → python → py (Windows launcher).
// Strips the project bin/ shim directory from PATH so we resolve to a system
// interpreter (otherwise bin/python → pyrun.js → bin/python recurses).
const { spawnSync } = require('child_process');
const path = require('path');
const args = process.argv.slice(2);

const shimDir = path.resolve(__dirname, '..', '..', 'bin');
const sep = process.platform === 'win32' ? ';' : ':';
const origPath = process.env.PATH || '';
const cleanPath = origPath.split(sep).filter(p => path.resolve(p) !== shimDir).join(sep);
const env = {
  ...process.env,
  PATH: cleanPath,
  // Stash original PATH so callees can see how the shell was invoked.
  HEADMASTER_ORIG_PATH: process.env.HEADMASTER_ORIG_PATH || origPath,
};

for (const cmd of ['python3', 'python', 'py']) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', env });
  if (!r.error) process.exit(r.status ?? 0);
}
console.error('Python interpreter not found. Install python3, python, or py.');
process.exit(1);
