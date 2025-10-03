# Online Installer Architecture

This document explains the online installer system that reduces release sizes from 123MB to ~2-5MB by downloading dependencies at install time.

## Overview

**Traditional approach (what we had):**
- Full portable exe: 123MB
  - Electron runtime: 65MB (bundled)
  - PyInstaller backend exe: 58MB (bundled, includes Python + all packages)
  - App code: ~6MB (bundled)

**New online installer approach:**
- **Web installer: 2-3MB** (distributed via GitHub Releases)
- **Backend source code: ~1-2MB** (downloaded at install)
- **Dependencies downloaded at install time:**
  - Electron runtime: ~65MB (via nsis-web)
  - Python runtime: ~30MB (from python.org)
  - pip packages: ~50MB (from PyPI: OpenCV, Flask, numpy, etc.)
  - Map: 167MB (from GitHub raw, already implemented)

**Total first install: ~310MB download**, but **updates are only 5-10MB**!

## Architecture Components

### 1. NSIS Web Installer (Electron)

**File:** `frontend/electron-builder.yml`

```yaml
win:
  target:
    - target: nsis-web  # Downloads full Electron app during install
      arch: [x64]
```

**What it does:**
- Creates tiny ~2-3MB installer
- Downloads Electron runtime (~65MB) during installation
- Handles extraction and shortcuts automatically

### 2. Python Environment Manager

**File:** `frontend/python-environment-manager.js`

**What it does:**
1. Downloads Python 3.11 embeddable runtime (~30MB) from python.org
2. Installs pip
3. Installs packages from `requirements.txt` via PyPI:
   - opencv-python (~45MB)
   - Flask, SocketIO, etc. (~5MB)
   - numpy, Pillow, requests, etc. (~10MB)

**Usage:**
```javascript
const PythonEnvManager = require('./python-environment-manager');
const envManager = new PythonEnvManager();

// Setup environment (first launch only)
await envManager.setupEnvironment(
  path.join(backendDir, 'requirements.txt'),
  (progress) => {
    console.log(`Step ${progress.step}/3: ${progress.component} - ${progress.percent}%`);
  }
);

// Launch backend
const backendProcess = await envManager.launchBackend(
  path.join(backendDir, 'run.py')
);
```

### 3. Component Downloader

**File:** `frontend/component-downloader.js`

**What it does:**
- Downloads backend source code from GitHub
- Downloads map from GitHub
- Verifies SHA256 hashes
- Tracks progress
- Caches components in `%APPDATA%/RDO-Map-Overlay/components/`

### 4. Backend Source Package

**Build script:** `.build/build-backend-source.js`

**What it does:**
- Packages Python source files (not PyInstaller exe)
- Creates `backend-source.zip` (~1-2MB)
- Includes launcher script (`run.py`)

**Structure:**
```
backend-source/
├── api/
├── config/
├── core/
├── matching/
├── models/
├── app.py
├── requirements.txt
└── run.py  # Launcher
```

## Build Process

### Initial Setup (One-Time)

```bash
# 1. Install Node dependencies for Python environment manager
cd frontend
npm install

# 2. Build backend source package
cd ..
node .build/build-backend-source.js
# Output: build/backend-source.zip (~1-2MB)

# 3. Build web installer
cd frontend
npm run build
# Output: build/frontend/RDO-Map-Overlay-Setup.exe (~2-3MB)
```

### For Each Release (Quick Iteration)

```bash
# 1. Make code changes to Python or Electron code
# ... edit files ...

# 2. Build backend source (if backend changed)
node .build/build-backend-source.js

# 3. Build web installer
cd frontend
npm run build

# 4. Upload to GitHub Release
# - backend-source.zip (~1-2MB)
# - RDO-Map-Overlay-Setup.exe (~2-3MB)
```

**Total upload per release: ~3-5MB!**

## GitHub Releases Structure

### Initial Release (v1.0.0)

Create tags and releases:

```bash
# Tag and release map (one-time, or when map updates)
git tag assets-v1.0.0
git push origin assets-v1.0.0
# Upload: rdr2_map_hq.png (167MB)

# Tag and release app
git tag v1.0.0
git push origin v1.0.0
# Upload:
#   - RDO-Map-Overlay-Setup.exe (2-3MB)
#   - backend-source.zip (1-2MB)
```

### Subsequent Releases (v1.0.1, v1.0.2, etc.)

```bash
# Only upload changed components
git tag v1.0.1
git push origin v1.0.1
# Upload:
#   - RDO-Map-Overlay-Setup.exe (2-3MB) [if frontend changed]
#   - backend-source.zip (1-2MB) [if backend changed]

# Map only reuploaded if it changes (rare)
```

## Installation Flow

### First Launch

1. **User downloads web installer** (`RDO-Map-Overlay-Setup.exe`, 2-3MB)
2. **Installer runs:**
   - Shows NSIS install wizard
   - Downloads Electron runtime (~65MB) from CDN
   - Extracts to `C:\Program Files\RDO Map Overlay\`
   - Creates shortcuts
3. **App launches for first time:**
   - Shows splash screen: "Setting up environment..."
   - Downloads Python runtime (~30MB)
   - Installs pip packages from PyPI (~50MB)
   - Downloads backend source (~1-2MB)
   - Downloads map (~167MB)
   - Starts backend with downloaded Python
   - Ready to use!

**Total: ~310MB downloaded, but spread across multiple sources**

### Subsequent Launches

1. App starts immediately (everything cached)
2. Backend runs from cached Python environment
3. Map loaded from cache
4. Fast startup!

### Updates (electron-updater)

1. App checks for updates on startup
2. If new version available:
   - Downloads only changed files (~5-10MB typically)
   - Applies update automatically
   - Restarts
3. Python environment reused (no redownload)
4. Map reused (no redownload)

## Configuration Files

### components-manifest.json

```json
{
  "version": "1.0.0",
  "components": [
    {
      "name": "Backend Source",
      "filename": "backend-source.zip",
      "url": "https://github.com/YOUR_USER/rdo_overlay/releases/download/v1.0.0/backend-source.zip",
      "sha256": "HASH_HERE",
      "required": true,
      "size": 1500000
    },
    {
      "name": "HQ Map",
      "filename": "rdr2_map_hq.png",
      "url": "https://raw.githubusercontent.com/YOUR_USER/rdo_overlay/main/data/rdr2_map_hq.png",
      "sha256": "HASH_HERE",
      "required": true,
      "size": 175000000
    }
  ]
}
```

### electron-builder.yml

```yaml
appId: com.rdo.mapoverlay
productName: RDO Map Overlay
directories:
  output: ../build/frontend

win:
  target:
    - target: nsis-web  # Key: use web installer
      arch: [x64]
  icon: icon.ico

nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true
  createDesktopShortcut: true

publish:
  provider: github
  owner: YOUR_USERNAME
  repo: rdo_overlay
```

## Trade-offs

### Pros ✅
- **95% reduction in release size** (3-5MB vs 123MB)
- **Fast iteration** (minutes to build and upload)
- **No GitHub storage limits** (dependencies from official sources)
- **Professional auto-update** system
- **Users always get latest dependencies**

### Cons ⚠️
- **First install requires internet** (no offline installer)
- **First launch takes 3-5 minutes** (downloading dependencies)
- **Requires hosting** on GitHub Releases or CDN
- **More complex** than single exe
- **Potential issues:**
  - PyPI downtime (rare)
  - python.org downtime (rare)
  - Network errors during install

## Troubleshooting

### Python installation fails
- Check internet connection
- Try running installer as Administrator
- Manually download Python 3.11 embeddable and place in `%APPDATA%/RDO-Map-Overlay/components/python/`

### Package installation fails
- Check PyPI status (https://status.python.org)
- Retry installation
- Check firewall/antivirus

### Backend won't start
- Check logs in `%APPDATA%/RDO-Map-Overlay/logs/`
- Verify Python environment is complete
- Try deleting `components/` folder and reinstalling

## Future Enhancements

1. **Retry logic** for failed downloads
2. **Mirror URLs** for dependencies
3. **Offline installer option** (bundles dependencies)
4. **Progress persistence** (resume failed installs)
5. **Automatic cleanup** of old component versions

---

## Quick Reference

**Build web installer:**
```bash
node .build/build-backend-source.js
cd frontend && npm run build
```

**Test locally:**
```bash
# Install the web installer
build/frontend/RDO-Map-Overlay-Setup.exe

# Watch logs during first launch
# Components download to: %APPDATA%/RDO-Map-Overlay/
```

**Create release:**
```bash
git tag v1.0.0 && git push origin v1.0.0
# Upload build/frontend/RDO-Map-Overlay-Setup.exe
# Upload build/backend-source.zip
```
