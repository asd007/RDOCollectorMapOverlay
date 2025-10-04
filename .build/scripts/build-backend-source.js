#!/usr/bin/env node
/**
 * Package backend as source code (not PyInstaller exe)
 * Creates a zip with Python source files that will run with downloaded Python runtime
 * This reduces backend from 58MB to ~1-2MB
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT_DIR = path.join(__dirname, '..', '..');
const BUILD_ARTIFACTS_DIR = path.join(ROOT_DIR, 'build', 'installer');
const BACKEND_SOURCE_DIR = path.join(BUILD_ARTIFACTS_DIR, 'backend-source');

console.log('============================================');
console.log('  RDO Overlay - Backend Source Package');
console.log('============================================\n');

// Clean previous build
if (fs.existsSync(BACKEND_SOURCE_DIR)) {
  fs.rmSync(BACKEND_SOURCE_DIR, { recursive: true });
}
fs.mkdirSync(BACKEND_SOURCE_DIR, { recursive: true });

console.log('[BUILD] Packaging Python source files...\n');

// Directories and files to include
const includes = [
  'api/',
  'config/',
  'core/',
  'matching/',
  'models/',
  'app.py',
  'requirements.txt'
];

// Copy Python source files
includes.forEach(item => {
  const src = path.join(ROOT_DIR, item);
  const dest = path.join(BACKEND_SOURCE_DIR, item);

  if (!fs.existsSync(src)) {
    console.warn(`[WARN] Skipping ${item} (not found)`);
    return;
  }

  if (fs.statSync(src).isDirectory()) {
    // Copy directory recursively
    copyDirectory(src, dest);
    console.log(`  [OK] ${item}`);
  } else {
    // Copy file
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
    console.log(`  [OK] ${item}`);
  }
});

// Create a launcher script
const launcherScript = `#!/usr/bin/env python3
"""
Backend Launcher
Starts the Flask backend server
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import and run app
from app import main

if __name__ == '__main__':
    main()
`;

fs.writeFileSync(path.join(BACKEND_SOURCE_DIR, 'run.py'), launcherScript);
console.log('  [OK] run.py (launcher)');

// Calculate total size
const totalSize = getFolderSize(BACKEND_SOURCE_DIR);
const sizeMB = (totalSize / 1024 / 1024).toFixed(1);

console.log(`\n[STATS] Total size: ${sizeMB} MB`);

// Create zip
console.log('\n[ZIP] Creating backend-source.zip...');
const zipPath = path.join(BUILD_ARTIFACTS_DIR, 'backend-source.zip');

execSync(
  `powershell Compress-Archive -Path "${BACKEND_SOURCE_DIR}\\*" -DestinationPath "${zipPath}" -CompressionLevel Optimal -Force`,
  { stdio: 'inherit' }
);

const zipSize = (fs.statSync(zipPath).size / 1024 / 1024).toFixed(1);

console.log('\n============================================');
console.log('  Backend Source Package Complete!');
console.log('============================================\n');

console.log(`[OUTPUT] Package: build/backend-source.zip (${zipSize} MB)`);
console.log(`\n[INFO] This replaces the 58MB PyInstaller exe!`);
console.log(`[INFO] Python runtime (30MB) + packages (50MB) download at install time\n`);

// Helper functions

function copyDirectory(src, dest) {
  fs.mkdirSync(dest, { recursive: true });

  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    // Skip __pycache__ and other unwanted directories
    if (entry.name === '__pycache__' || entry.name === '.pytest_cache' || entry.name.endsWith('.pyc')) {
      continue;
    }

    if (entry.isDirectory()) {
      copyDirectory(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function getFolderSize(folderPath) {
  let totalSize = 0;

  const files = fs.readdirSync(folderPath, { withFileTypes: true });

  for (const file of files) {
    const filePath = path.join(folderPath, file.name);

    if (file.isDirectory()) {
      totalSize += getFolderSize(filePath);
    } else {
      totalSize += fs.statSync(filePath).size;
    }
  }

  return totalSize;
}
