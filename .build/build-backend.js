#!/usr/bin/env node
/**
 * Build backend using PyInstaller
 * Creates standalone executable with all dependencies
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.join(__dirname, '..');
const BUILD_DIR = path.join(ROOT_DIR, 'build');
const BACKEND_BUILD = path.join(BUILD_DIR, 'backend');
const TEMP_DIR = path.join(BUILD_DIR, 'temp');

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
if (fs.existsSync(BUILD_DIR)) {
  fs.rmSync(BUILD_DIR, { recursive: true });
}

// Create build directories
fs.mkdirSync(BACKEND_BUILD, { recursive: true });
fs.mkdirSync(TEMP_DIR, { recursive: true });

// Run PyInstaller with custom output paths
console.log('📦 Running PyInstaller...');
try {
  execSync(
    `pyinstaller app.spec --clean --noconfirm --distpath "${BACKEND_BUILD}" --workpath "${TEMP_DIR}"`,
    {
      cwd: ROOT_DIR,
      stdio: 'inherit'
    }
  );
} catch (e) {
  console.error('❌ PyInstaller build failed!');
  process.exit(1);
}

// Get file size
console.log('📁 Build complete...');
const stats = fs.statSync(path.join(BACKEND_BUILD, 'rdo-overlay-backend.exe'));
const sizeMB = (stats.size / 1024 / 1024).toFixed(1);

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log(`✅ Backend built successfully!`);
console.log(`📍 Output: build/backend/rdo-overlay-backend.exe (${sizeMB} MB)`);
