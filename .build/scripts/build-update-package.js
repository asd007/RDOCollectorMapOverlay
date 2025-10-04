#!/usr/bin/env node
/**
 * Build lightweight update package containing only code changes
 * Creates a zip with just app.asar and backend files (5-10MB)
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT_DIR = path.join(__dirname, '..');
const BUILD_DIR = path.join(ROOT_DIR, 'build');
const UPDATE_DIR = path.join(BUILD_DIR, 'update-package');
const VERSION = require(path.join(ROOT_DIR, 'frontend', 'package.json')).version;

console.log('============================================');
console.log('    RDO Map Overlay - Update Package       ');
console.log('============================================\n');

// Clean update directory
if (fs.existsSync(UPDATE_DIR)) {
  fs.rmSync(UPDATE_DIR, { recursive: true });
}
fs.mkdirSync(UPDATE_DIR, { recursive: true });

// Copy app.asar (frontend code)
console.log('📦 Packaging frontend code...');
const appAsarSrc = path.join(BUILD_DIR, 'frontend', 'win-unpacked', 'resources', 'app.asar');
const appAsarDest = path.join(UPDATE_DIR, 'resources', 'app.asar');
fs.mkdirSync(path.dirname(appAsarDest), { recursive: true });
fs.copyFileSync(appAsarSrc, appAsarDest);

const appAsarSize = (fs.statSync(appAsarSrc).size / 1024 / 1024).toFixed(1);
console.log(`  [OK] Frontend: ${appAsarSize} MB`);

// Copy backend (if exists)
const backendSrc = path.join(BUILD_DIR, 'backend', 'rdo-overlay-backend.exe');
if (fs.existsSync(backendSrc)) {
  console.log('📦 Packaging backend...');
  const backendDest = path.join(UPDATE_DIR, 'resources', 'backend', 'rdo-overlay-backend.exe');
  fs.mkdirSync(path.dirname(backendDest), { recursive: true });
  fs.copyFileSync(backendSrc, backendDest);

  const backendSize = (fs.statSync(backendSrc).size / 1024 / 1024).toFixed(1);
  console.log(`  [OK] Backend: ${backendSize} MB`);
}

// Create version info file
console.log('📝 Creating version info...');
const versionInfo = {
  version: VERSION,
  buildDate: new Date().toISOString(),
  changelog: 'See RELEASE_NOTES.md for details'
};
fs.writeFileSync(
  path.join(UPDATE_DIR, 'VERSION.json'),
  JSON.stringify(versionInfo, null, 2)
);

// Create installation instructions
const instructions = `RDO Map Overlay - Update Package v${VERSION}
${'='.repeat(50)}

INSTALLATION INSTRUCTIONS:
1. Close RDO Map Overlay if running
2. Navigate to your installation folder:
   - Default: C:\\Program Files\\RDO Map Overlay\\
   - Or wherever you installed it

3. Copy the contents of this update package into the installation folder
   - Overwrite existing files when prompted

4. Launch RDO Map Overlay

FILES INCLUDED:
- resources/app.asar (frontend code)
- resources/backend/rdo-overlay-backend.exe (backend, if updated)

TROUBLESHOOTING:
If the app doesn't start after updating:
1. Download the full installer instead
2. Or delete the installation and reinstall

For support, visit: https://github.com/YOUR_USERNAME/rdo_overlay/issues
`;

fs.writeFileSync(path.join(UPDATE_DIR, 'INSTALL.txt'), instructions);

// Create zip
console.log('🗜️  Creating update package...');
const zipName = `rdo-overlay-update-v${VERSION}.zip`;
const zipPath = path.join(BUILD_DIR, zipName);

try {
  // Use PowerShell to create zip
  execSync(
    `powershell Compress-Archive -Path "${UPDATE_DIR}\\*" -DestinationPath "${zipPath}" -Force`,
    { stdio: 'inherit' }
  );

  const zipSize = (fs.statSync(zipPath).size / 1024 / 1024).toFixed(1);

  console.log('\n============================================');
  console.log('    [SUCCESS] Update Package Created!             ');
  console.log('============================================\n');
  console.log(`📍 Update package: build/${zipName}`);
  console.log(`📊 Size: ${zipSize} MB (vs ${BUILD_DIR.includes('302') ? '302' : '123'} MB full installer)`);
  console.log(`\n💡 Users extract this into their installation folder to update`);

} catch (error) {
  console.error('[ERROR] Failed to create zip:', error.message);
  process.exit(1);
}
