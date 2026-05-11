#!/usr/bin/env node
// Cross-platform Python resolver: python3 → python → py (Windows)
const { spawnSync } = require('child_process');
const args = process.argv.slice(2);
for (const cmd of ['python3', 'python', 'py']) {
  const r = spawnSync(cmd, args, { stdio: 'inherit' });
  if (!r.error) process.exit(r.status ?? 0);
}
console.error('Python interpreter not found. Install python3.');
process.exit(1);
