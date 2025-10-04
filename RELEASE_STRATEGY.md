# RDO Map Overlay - Online Installer Release Strategy

## Overview

This document explains the new lightweight release strategy that reduces download sizes from 123MB to 2-3MB for quick iteration.

## Architecture

### Components

1. **Web Installer** (2-3MB)
   - Lightweight NSIS web installer
   - Downloads components during installation
   - Entry point for new users

2. **Electron App** (~6MB ASAR)
   - Main application code
   - Auto-updates via electron-updater
   - Delta updates for existing users

3. **Python Backend** (~58MB)
   - PyInstaller bundle with OpenCV
   - Downloaded once, rarely changes
   - Cached in `%APPDATA%/RDO-Map-Overlay/components/`

4. **Map Data** (167MB)
   - Downloaded on first use
   - Already implemented in `core/map_downloader.py`
   - Cached in `%APPDATA%/RDO-Map-Overlay/data/`

## Release Types

### 1. Backend Release (`backend-v*`)
- **Frequency**: Rare (only when Python deps change)
- **Size**: ~58MB
- **Command**: `git tag backend-v1.0.0 && git push origin backend-v1.0.0`
- **Artifact**: `rdo-overlay-backend.exe`

### 2. App Release (`v*`)
- **Frequency**: Common (feature updates)
- **Size**: 2-3MB installer, 5-10MB updates
- **Command**: `git tag v1.0.1 && git push origin v1.0.1`
- **Artifacts**:
  - `RDO-Map-Overlay-Setup-Web.exe` (new users)
  - `latest.yml` (auto-updater)

### 3. Asset Release (`assets-v*`)
- **Frequency**: Very rare
- **Size**: 167MB
- **Command**: `git tag assets-v1.0.0 && git push origin assets-v1.0.0`
- **Artifact**: `rdr2_map_hq.png`

## Build Process

### Local Development

```bash
# Build everything with updated hashes
node .build/build-web-installer.js --with-backend --update-hashes

# Build just the web installer (for app-only updates)
node .build/build-web-installer.js

# Test installer locally
dist/RDO-Map-Overlay-Setup-Web.exe
```

### GitHub Actions (Automated)

1. Push a tag → GitHub Actions builds and releases automatically
2. Different tags trigger different workflows:
   - `v*` → Build web installer + auto-update files
   - `backend-v*` → Build Python backend
   - `assets-v*` → Upload map assets

## Version Management

### Version Locations

1. **App Version**: `frontend/package.json` → `version`
2. **Backend Version**: `components-manifest.json` → `components[0].version`
3. **Manifest Version**: `components-manifest.json` → `version`

### Version Strategy

```
v1.0.0 - Major app release
v1.0.1 - Minor app update (5-10MB delta)
v1.1.0 - Feature release

backend-v1.0.0 - Backend changes
backend-v1.0.1 - Backend fixes

assets-v1.0.0 - Map updates
```

## Component Manifest

The `components-manifest.json` file controls what gets downloaded:

```json
{
  "version": "1.0.0",
  "components": [
    {
      "name": "Python Backend",
      "filename": "rdo-overlay-backend.exe",
      "version": "1.0.0",
      "url": "https://github.com/USER/REPO/releases/download/backend-v1.0.0/rdo-overlay-backend.exe",
      "sha256": "HASH",
      "size": 60000000,
      "required": true
    }
  ]
}
```

**Important**: Update URLs and hashes after building!

## User Experience

### New User Flow

1. Download `RDO-Map-Overlay-Setup-Web.exe` (2-3MB)
2. Run installer
3. Installer downloads:
   - Electron runtime (~65MB)
   - Python backend (~58MB)
   - Shows progress in installer UI
4. Launch app
5. App downloads map on first use (167MB)

### Existing User Flow

1. Launch app
2. App checks for updates
3. Downloads only changed files (5-10MB)
4. Prompts to restart
5. Updates applied

## File Structure

```
dist/
├── RDO-Map-Overlay-Setup-Web.exe  # Web installer (2-3MB)
├── latest.yml                      # Auto-updater manifest
└── *.blockmap                      # Delta update files

release/
├── backend/
│   └── rdo-overlay-backend.exe    # Backend for GitHub release
└── assets/
    └── rdr2_map_hq.png            # Map for GitHub release

%APPDATA%/RDO-Map-Overlay/          # User's machine
├── components/
│   └── rdo-overlay-backend.exe    # Downloaded backend
└── data/
    └── rdr2_map_hq.png            # Downloaded map
```

## Migration Guide

### From Old Build System

1. **Update package.json**:
   ```bash
   cd frontend
   npm install electron-updater
   ```

2. **Create electron-builder.yml**:
   - Move build config from package.json
   - Configure nsis-web target

3. **Update main.js**:
   - Add ComponentDownloader
   - Implement auto-updater
   - Add splash screen

4. **Setup GitHub**:
   - Create `.github/workflows/release.yml`
   - Set up GitHub Releases
   - Configure repository secrets if needed

5. **First Release**:
   ```bash
   # Build and upload backend
   node .build/build-web-installer.js --with-backend --update-hashes
   git tag backend-v1.0.0
   git push origin backend-v1.0.0

   # Wait for GitHub Actions to complete

   # Update manifest with backend URL from GitHub Release
   # Edit components-manifest.json with actual URLs

   # Create app release
   git tag v1.0.0
   git push origin v1.0.0
   ```

## Testing Checklist

- [ ] Web installer downloads components correctly
- [ ] Backend starts after download
- [ ] Map downloads on first use
- [ ] Auto-updater detects new versions
- [ ] Delta updates apply correctly
- [ ] Splash screen shows progress
- [ ] Components are cached properly
- [ ] SHA256 verification works
- [ ] Offline fallback (if cached)

## Troubleshooting

### Installer Issues

- **"Failed to download backend"**: Check internet, verify URL in manifest
- **"Hash mismatch"**: Rebuild with `--update-hashes`
- **"Backend not starting"**: Check Windows Defender, add exception

### Update Issues

- **Updates not detected**: Check `publish` config in electron-builder.yml
- **Update fails**: Clear cache in `%APPDATA%/RDO-Map-Overlay/`
- **Slow updates**: Normal for first update (downloads Electron framework)

### Build Issues

- **Web installer too large**: Check `extraResources` is empty
- **Backend not included**: Don't bundle in web installer
- **Missing files**: Update `files` pattern in electron-builder.yml

## Benefits

1. **Tiny Downloads**: 2-3MB vs 123MB
2. **Fast Iteration**: 5-10MB updates vs full 123MB
3. **Component Versioning**: Update only what changed
4. **CDN Distribution**: Components from GitHub's CDN
5. **Automatic Updates**: Users always on latest version
6. **Bandwidth Savings**: 95% reduction in download size

## Next Steps

1. Test the build locally
2. Update GitHub repository settings
3. Create initial component releases
4. Update manifest with real URLs
5. Test end-to-end flow
6. Document for users