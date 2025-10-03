#!/usr/bin/env node
/**
 * Build backend using PyInstaller
 * Creates standalone executable with all dependencies
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.join(__dirname, '..');
const DIST_DIR = path.join(ROOT_DIR, 'dist');
const BACKEND_DIST = path.join(DIST_DIR, 'backend');

console.log('🔨 Building RDO Overlay Backend...');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

// Check if PyInstaller is installed
try {
  execSync('pyinstaller --version', { stdio: 'ignore' });
} catch (e) {
  console.error('❌ PyInstaller not found!');
  console.error('Install with: pip install pyinstaller');
  process.exit(1);
}

// Clean previous builds
console.log('🧹 Cleaning previous builds...');
if (fs.existsSync(path.join(ROOT_DIR, 'build'))) {
  fs.rmSync(path.join(ROOT_DIR, 'build'), { recursive: true });
}
if (fs.existsSync(BACKEND_DIST)) {
  fs.rmSync(BACKEND_DIST, { recursive: true });
}

// Run PyInstaller
console.log('📦 Running PyInstaller...');
try {
  execSync('pyinstaller app.spec --clean --noconfirm', {
    cwd: ROOT_DIR,
    stdio: 'inherit'
  });
} catch (e) {
  console.error('❌ PyInstaller build failed!');
  process.exit(1);
}

// Move to dist/backend for Electron
console.log('📁 Organizing build output...');
const pyinstallerDist = path.join(ROOT_DIR, 'dist', 'rdo-overlay-backend.exe');
fs.mkdirSync(BACKEND_DIST, { recursive: true });
fs.copyFileSync(
  pyinstallerDist,
  path.join(BACKEND_DIST, 'rdo-overlay-backend.exe')
);

// Get file size
const stats = fs.statSync(path.join(BACKEND_DIST, 'rdo-overlay-backend.exe'));
const sizeMB = (stats.size / 1024 / 1024).toFixed(1);

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log(`✅ Backend built successfully!`);
console.log(`📍 Output: dist/backend/rdo-overlay-backend.exe (${sizeMB} MB)`);
