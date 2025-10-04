# RDO Map Overlay - Web Installer Build Guide

## Overview

This build system creates a truly minimal web installer (~1-2MB) that downloads all dependencies during installation rather than packaging them. The installer downloads approximately 205MB of dependencies from official sources and creates a ~400MB installation.

## Components Downloaded During Installation

1. **Electron Runtime** (v27.0.0, ~95MB)
   - Source: GitHub Releases
   - Provides the desktop application framework

2. **Node.js Runtime** (v20.10.0, ~30MB)
   - Source: nodejs.org
   - Required for npm package management

3. **Python Embeddable** (v3.11.8, ~15MB)
   - Source: python.org
   - Runs the backend server

4. **NPM Dependencies** (~15MB)
   - Source: npm registry
   - Frontend JavaScript dependencies

5. **Python Packages** (~50MB)
   - Source: PyPI
   - Backend dependencies (OpenCV, Flask, etc.)

6. **Map Data** (Optional, ~167MB)
   - Source: GitHub Releases
   - Can be downloaded during install or on first launch

## Build Prerequisites

### Required Tools

1. **NSIS 3.x**
   - Download: https://nsis.sourceforge.io/
   - Add to PATH or use PowerShell script for automatic download

2. **NSIS Plugins**
   - INetC: For downloading with progress
   - nsisunz: For extracting ZIP files
   - The PowerShell build script will download these automatically

3. **Visual Studio** (Optional, for native launcher)
   - For building the C++ launcher executable
   - Community edition is sufficient

## Building the Installer

### Method 1: PowerShell (Recommended)

```powershell
cd .build\installer
.\build-web-installer.ps1
```

This script will:
- Automatically download NSIS if not found
- Download and install required plugins
- Compile the installer
- Report final size

### Method 2: Batch File

```batch
cd .build\installer
build-web-installer.bat
```

Requires NSIS and plugins to be pre-installed.

### Method 3: Direct NSIS Compilation

```batch
makensis installer-main.nsi
```

## Building the Native Launcher (Optional)

The native launcher provides better process management:

```batch
cd .build\launcher
build-launcher.bat
```

This creates a ~50KB launcher.exe that:
- Starts Python backend
- Waits for backend readiness
- Launches Electron frontend
- Manages process lifecycle

## Configuration

Edit `installer-config.nsh` to modify:
- Download URLs
- Version numbers
- Installation paths
- Component sizes (for progress display)

## How the Installer Works

1. **Minimal Stub**: Installer contains only:
   - NSIS runtime (~1MB compressed)
   - Application source files (~500KB)
   - Icons and metadata

2. **Download Phase**: During installation:
   - Creates temp directory
   - Downloads components with progress
   - Handles retry on failure
   - Verifies downloads

3. **Extraction Phase**:
   - Extracts Electron to `electron/`
   - Extracts Node.js to `runtime/node/`
   - Extracts Python to `runtime/python/`

4. **Configuration Phase**:
   - Configures Python for pip
   - Installs npm dependencies
   - Installs Python packages
   - Creates shortcuts

5. **First Launch**:
   - Launcher verifies installation
   - Downloads map data if needed
   - Starts backend and frontend

## Network Requirements

- Stable internet connection
- Access to:
  - github.com (Electron)
  - nodejs.org (Node.js)
  - python.org (Python)
  - pypi.org (Python packages)
  - npmjs.com (npm packages)

## Error Handling

The installer includes:
- Automatic retry on download failure
- User prompts for network issues
- Verification of extracted files
- Rollback on critical errors

## Testing the Installer

1. **Clean Test**: Remove any existing installation
2. **Offline Test**: Disconnect after installer download
3. **Retry Test**: Interrupt downloads to test retry
4. **Upgrade Test**: Install over existing version

## Distribution

The final installer can be distributed via:
- GitHub Releases
- Direct download links
- Software distribution platforms

File: `RDO-Map-Overlay-WebSetup-1.0.0.exe` (~1-2MB)

## Troubleshooting

### Common Issues

1. **"NSIS not found"**
   - Use PowerShell script for automatic download
   - Or install NSIS and add to PATH

2. **"Plugin not found"**
   - PowerShell script downloads automatically
   - Or manually download to NSIS\Plugins\

3. **Download failures**
   - Check firewall/proxy settings
   - Verify URLs are accessible
   - Check available disk space

4. **Python package installation fails**
   - Ensure pip is properly configured
   - Check for Visual C++ requirements
   - Verify Python environment setup

## Advanced Options

### Custom Download Server

To use your own CDN:

1. Host dependencies on your server
2. Update URLs in `installer-config.nsh`
3. Rebuild installer

### Silent Installation

Add to installer for silent mode support:

```nsis
!insertmacro MUI_PAGE_COMPONENTS
SilentInstall silent
SilentUnInstall silent
```

### Portable Mode

Modify installer to support portable installation:
- Skip registry writes
- Use relative paths
- Bundle all dependencies

## Security Considerations

- Downloads use HTTPS
- Consider signing the installer
- Verify checksums for downloads
- Use official sources only

## Future Enhancements

Potential improvements:
- Delta updates for existing installations
- Torrent/P2P for large downloads
- Mirror selection based on geography
- Offline installer generation post-download
- Automatic update checks