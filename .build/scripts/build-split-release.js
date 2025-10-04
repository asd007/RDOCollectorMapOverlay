#!/usr/bin/env node
/**
 * Build split release packages for bootstrap installer
 * Creates:
 * 1. runtime.zip (~120MB) - Electron + dependencies (uploaded once)
 * 2. code.zip (~5-10MB) - Your app code (updated frequently)
 * 3. bootstrap-installer.exe (~2-5MB) - Downloads and installs both
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT_DIR = path.join(__dirname, '..');
const BUILD_DIR = path.join(ROOT_DIR, 'build');
const UNPACKED_DIR = path.join(BUILD_DIR, 'frontend', 'win-unpacked');
const SPLIT_DIR = path.join(BUILD_DIR, 'split-release');

console.log('============================================');
console.log('    RDO Map Overlay - Split Release        ');
console.log('============================================\n');

// Step 1: Ensure we have a build
if (!fs.existsSync(UNPACKED_DIR)) {
  console.log('[ERROR] No unpacked build found. Run: node .build/build-release.js first');
  process.exit(1);
}

// Clean split directory
if (fs.existsSync(SPLIT_DIR)) {
  fs.rmSync(SPLIT_DIR, { recursive: true });
}
fs.mkdirSync(SPLIT_DIR, { recursive: true });

// Step 2: Create runtime package (Electron + system DLLs)
console.log('📦 Step 1/3: Creating runtime package...');
console.log('--------------------------------------------'.repeat(50));

const runtimeDir = path.join(SPLIT_DIR, 'runtime-temp');
fs.mkdirSync(runtimeDir, { recursive: true });

// Copy Electron runtime files (everything except app code and backend)
const runtimeFiles = [
  'chrome_100_percent.pak',
  'chrome_200_percent.pak',
  'd3dcompiler_47.dll',
  'ffmpeg.dll',
  'icudtl.dat',
  'libEGL.dll',
  'libGLESv2.dll',
  'resources.pak',
  'snapshot_blob.bin',
  'v8_context_snapshot.bin',
  'vk_swiftshader.dll',
  'vk_swiftshader_icd.json',
  'vulkan-1.dll',
  'RDO Map Overlay.exe',
  'locales/',
  'resources/elevate.exe'  // Keep elevate.exe
];

runtimeFiles.forEach(file => {
  const src = path.join(UNPACKED_DIR, file);
  const dest = path.join(runtimeDir, file);

  if (fs.existsSync(src)) {
    if (fs.statSync(src).isDirectory()) {
      fs.mkdirSync(dest, { recursive: true });
      fs.readdirSync(src).forEach(subfile => {
        fs.copyFileSync(path.join(src, subfile), path.join(dest, subfile));
      });
    } else {
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.copyFileSync(src, dest);
    }
    console.log(`  [OK] ${file}`);
  }
});

// Zip runtime
console.log('\n🗜️  Compressing runtime...');
const runtimeZip = path.join(SPLIT_DIR, 'runtime.zip');
execSync(
  `powershell Compress-Archive -Path "${runtimeDir}\\*" -DestinationPath "${runtimeZip}" -CompressionLevel Optimal -Force`,
  { stdio: 'inherit' }
);

const runtimeSize = (fs.statSync(runtimeZip).size / 1024 / 1024).toFixed(1);
console.log(`[SUCCESS] Runtime package: ${runtimeSize} MB`);

// Step 3: Create code package (app.asar + backend)
console.log('\n📦 Step 2/3: Creating code package...');
console.log('--------------------------------------------'.repeat(50));

const codeDir = path.join(SPLIT_DIR, 'code-temp');
fs.mkdirSync(path.join(codeDir, 'resources'), { recursive: true });

// Copy app.asar
const appAsarSrc = path.join(UNPACKED_DIR, 'resources', 'app.asar');
const appAsarDest = path.join(codeDir, 'resources', 'app.asar');
fs.copyFileSync(appAsarSrc, appAsarDest);
console.log('  [OK] app.asar');

// Copy backend
const backendSrcDir = path.join(UNPACKED_DIR, 'resources', 'backend');
const backendDestDir = path.join(codeDir, 'resources', 'backend');
if (fs.existsSync(backendSrcDir)) {
  fs.mkdirSync(backendDestDir, { recursive: true});
  fs.readdirSync(backendSrcDir).forEach(file => {
    fs.copyFileSync(
      path.join(backendSrcDir, file),
      path.join(backendDestDir, file)
    );
  });
  console.log('  [OK] backend/');
}

// Zip code
console.log('\n🗜️  Compressing code...');
const codeZip = path.join(SPLIT_DIR, 'code.zip');
execSync(
  `powershell Compress-Archive -Path "${codeDir}\\*" -DestinationPath "${codeZip}" -CompressionLevel Optimal -Force`,
  { stdio: 'inherit' }
);

const codeSize = (fs.statSync(codeZip).size / 1024 / 1024).toFixed(1);
console.log(`[SUCCESS] Code package: ${codeSize} MB`);

// Step 4: Build bootstrap installer
console.log('\n📦 Step 3/3: Building bootstrap installer...');
console.log('--------------------------------------------'.repeat(50));

const bootstrapDir = path.join(__dirname, 'bootstrap');

// Check if bootstrap dependencies are installed
if (!fs.existsSync(path.join(bootstrapDir, 'node_modules'))) {
  console.log('📥 Installing bootstrap dependencies...');
  execSync('npm install', { cwd: bootstrapDir, stdio: 'inherit' });
}

// Build bootstrap
console.log('🔨 Building bootstrap installer...');
execSync('npm run build', { cwd: bootstrapDir, stdio: 'inherit' });

const bootstrapExe = fs.readdirSync(path.join(BUILD_DIR, 'bootstrap')).find(f => f.endsWith('.exe'));
if (bootstrapExe) {
  const bootstrapSize = (fs.statSync(path.join(BUILD_DIR, 'bootstrap', bootstrapExe)).size / 1024 / 1024).toFixed(1);
  console.log(`[SUCCESS] Bootstrap installer: ${bootstrapSize} MB`);
}

// Cleanup temp directories
fs.rmSync(runtimeDir, { recursive: true });
fs.rmSync(codeDir, { recursive: true });

// Summary
console.log('\n============================================');
console.log('    [SUCCESS] Split Release Complete!             ');
console.log('============================================\n');

console.log('📦 Packages created:');
console.log(`  1. runtime.zip (${runtimeSize} MB) - Upload once to GitHub Releases`);
console.log(`  2. code.zip (${codeSize} MB) - Upload for each version`);
if (bootstrapExe) {
  const bootstrapSize = (fs.statSync(path.join(BUILD_DIR, 'bootstrap', bootstrapExe)).size / 1024 / 1024).toFixed(1);
  console.log(`  3. ${bootstrapExe} (${bootstrapSize} MB) - Distribute to users\n`);
}

console.log('📍 Location: build/split-release/\n');

console.log('🚀 Next steps:');
console.log('  1. Upload runtime.zip to GitHub Release as "runtime-v1.0.0"');
console.log('  2. Upload code.zip to GitHub Release as "v1.0.0"');
console.log('  3. Distribute bootstrap installer to users');
console.log('  4. For updates: Only rebuild and upload new code.zip\n');
