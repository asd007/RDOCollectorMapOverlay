#!/usr/bin/env node
/**
 * Full release build script
 * Orchestrates: backend build → frontend build → installer creation
 */

const { execSync } = require('child_process');
const path = require('path');

const ROOT_DIR = path.join(__dirname, '..');

console.log('');
console.log('╔════════════════════════════════════════╗');
console.log('║  RDO Map Overlay - Release Build      ║');
console.log('╚════════════════════════════════════════╝');
console.log('');

async function run(command, options = {}) {
  try {
    execSync(command, {
      cwd: options.cwd || ROOT_DIR,
      stdio: 'inherit',
      ...options
    });
  } catch (e) {
    console.error(`\n❌ Command failed: ${command}`);
    process.exit(1);
  }
}

async function main() {
  // Step 1: Build backend
  console.log('📦 Step 1/3: Building Backend');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  await run('node scripts/build-backend.js');
  console.log('');

  // Step 2: Install frontend dependencies (if needed)
  console.log('📦 Step 2/3: Preparing Frontend');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  await run('npm install', { cwd: path.join(ROOT_DIR, 'frontend') });
  console.log('');

  // Step 3: Build Electron app with embedded backend
  console.log('📦 Step 3/3: Building Installer');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  await run('npm run build', { cwd: path.join(ROOT_DIR, 'frontend') });
  console.log('');

  console.log('╔════════════════════════════════════════╗');
  console.log('║  ✅ Release Build Complete!           ║');
  console.log('╚════════════════════════════════════════╝');
  console.log('');
  console.log('📍 Installer: frontend/dist/RDO-Map-Overlay-Setup.exe');
  console.log('');
}

main().catch(err => {
  console.error('\n❌ Build failed:', err);
  process.exit(1);
});
