#!/usr/bin/env node
/**
 * Build script for web installer
 * Creates a lightweight installer that downloads components on demand
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const ROOT_DIR = path.join(__dirname, '..');

console.log('');
console.log('============================================');
console.log('    RDO Map Overlay - Web Installer Build   ');
console.log('============================================');
console.log('');

function run(command, options = {}) {
  try {
    execSync(command, {
      cwd: options.cwd || ROOT_DIR,
      stdio: 'inherit',
      ...options
    });
  } catch (e) {
    console.error(`\n[ERROR] Command failed: ${command}`);
    process.exit(1);
  }
}

function calculateHash(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex').toUpperCase();
}

function updateManifest(backendPath, mapPath) {
  const manifestPath = path.join(ROOT_DIR, 'components-manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

  // Update backend hash if it exists
  if (backendPath && fs.existsSync(backendPath)) {
    const backendHash = calculateHash(backendPath);
    const backendSize = fs.statSync(backendPath).size;

    const backendComponent = manifest.components.find(c => c.filename === 'rdo-overlay-backend.exe');
    if (backendComponent) {
      backendComponent.sha256 = backendHash;
      backendComponent.size = backendSize;
      console.log(`[OK] Backend hash: ${backendHash}`);
      console.log(`[OK] Backend size: ${(backendSize / 1024 / 1024).toFixed(2)} MB`);
    }
  }

  // Update map hash if it exists
  if (mapPath && fs.existsSync(mapPath)) {
    const mapHash = calculateHash(mapPath);
    const mapSize = fs.statSync(mapPath).size;

    const mapComponent = manifest.components.find(c => c.filename === 'rdr2_map_hq.png');
    if (mapComponent) {
      mapComponent.sha256 = mapHash;
      mapComponent.size = mapSize;
      console.log(`[OK] Map hash: ${mapHash}`);
      console.log(`[OK] Map size: ${(mapSize / 1024 / 1024).toFixed(2)} MB`);
    }
  }

  // Save updated manifest
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  console.log('[OK] Updated components manifest');
}

async function main() {
  const buildBackend = process.argv.includes('--with-backend');
  const updateHashes = process.argv.includes('--update-hashes');

  // Step 1: Build backend (optional)
  if (buildBackend) {
    console.log('📦 Step 1/4: Building Backend');
    console.log('--------------------------------------------');
    run('pyinstaller app.spec');

    const backendPath = path.join(ROOT_DIR, 'dist', 'rdo-overlay-backend.exe');
    if (!fs.existsSync(backendPath)) {
      console.error('[ERROR] Backend build failed - executable not found');
      process.exit(1);
    }

    // Move backend to a separate directory for GitHub release
    const backendReleaseDir = path.join(ROOT_DIR, 'release', 'backend');
    if (!fs.existsSync(backendReleaseDir)) {
      fs.mkdirSync(backendReleaseDir, { recursive: true });
    }
    fs.copyFileSync(backendPath, path.join(backendReleaseDir, 'rdo-overlay-backend.exe'));
    console.log('[OK] Backend built successfully');
    console.log('');
  }

  // Step 2: Update component hashes
  if (updateHashes) {
    console.log('📦 Step 2/4: Updating Component Hashes');
    console.log('--------------------------------------------');

    const backendPath = path.join(ROOT_DIR, 'release', 'backend', 'rdo-overlay-backend.exe');
    const mapPath = path.join(ROOT_DIR, 'data', 'rdr2_map_hq.png');

    updateManifest(backendPath, mapPath);
    console.log('');
  }

  // Step 3: Install frontend dependencies
  console.log('📦 Step 3/4: Preparing Frontend');
  console.log('--------------------------------------------');
  run('npm ci', { cwd: path.join(ROOT_DIR, 'frontend') });
  console.log('');

  // Step 4: Build web installer
  console.log('📦 Step 4/4: Building Web Installer');
  console.log('--------------------------------------------');

  // Clean dist directory
  const distDir = path.join(ROOT_DIR, 'dist');
  if (fs.existsSync(distDir)) {
    fs.rmSync(distDir, { recursive: true, force: true });
  }

  // Build only the web installer
  run('npm run build -- --win nsis-web', { cwd: path.join(ROOT_DIR, 'frontend') });

  // Check output
  const webInstallerPath = path.join(ROOT_DIR, 'dist', 'RDO-Map-Overlay-Setup-Web.exe');
  if (!fs.existsSync(webInstallerPath)) {
    console.error('[ERROR] Web installer not found at expected location');
    process.exit(1);
  }

  const installerSize = fs.statSync(webInstallerPath).size;
  const installerHash = calculateHash(webInstallerPath);

  console.log('');
  console.log('============================================');
  console.log('    [SUCCESS] Web Installer Build Complete!       ');
  console.log('============================================');
  console.log('');
  console.log('📊 Build Statistics:');
  console.log('--------------------------------------------');
  console.log(`📦 Web Installer: ${(installerSize / 1024 / 1024).toFixed(2)} MB`);
  console.log(`🔒 SHA256: ${installerHash}`);
  console.log(`📍 Location: ${webInstallerPath}`);
  console.log('');
  console.log('📋 Next Steps:');
  console.log('--------------------------------------------');
  console.log('1. Test the web installer locally');
  console.log('2. Upload backend to GitHub Release (if built)');
  console.log('3. Update components-manifest.json with correct URLs');
  console.log('4. Create GitHub Release with web installer');
  console.log('5. Test auto-update functionality');
  console.log('');

  // Generate release commands
  console.log('📝 GitHub Release Commands:');
  console.log('--------------------------------------------');
  console.log('# Create backend release (if needed):');
  console.log('git tag backend-v1.0.0');
  console.log('git push origin backend-v1.0.0');
  console.log('');
  console.log('# Create app release:');
  console.log('git tag v1.0.0');
  console.log('git push origin v1.0.0');
  console.log('');
}

main().catch(err => {
  console.error('\n[ERROR] Build failed:', err);
  process.exit(1);
});