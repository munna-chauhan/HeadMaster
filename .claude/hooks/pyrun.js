#!/usr/bin/env node
// Cross-platform Python resolver: python → python → py (Windows)
const { spawnSync } = require('child_process');
const args = process.argv.slice(2);
for (const cmd of ['python', 'python', 'py']) {
  const r = spawnSync(cmd, args, { stdio: 'inherit' });
  if (!r.error) process.exit(r.status ?? 0);
}
console.error('Python interpreter not found. Install python.');
process.exit(1);
