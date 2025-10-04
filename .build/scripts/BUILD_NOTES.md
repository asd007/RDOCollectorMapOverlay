# Build Notes

## Symbolic Link Issue with electron-builder

### Problem

electron-builder downloads `winCodeSign` tools that contain macOS symbolic links, which fail to extract on Windows without special privileges:

```
ERROR: Cannot create symbolic link : A required privilege is not held by the client.
C:\Users\...\Cache\winCodeSign\...\darwin\10.12\lib\libcrypto.dylib
```

### Impact

- ✅ **Unpacked build works perfectly** (`build/frontend/win-unpacked/`)
- ❌ **Portable/Installer .exe creation fails** due to symlink extraction

### Solutions

#### Option 1: Enable Windows Developer Mode (Recommended)

1. Open **Settings** → **System** → **For developers**
2. Turn ON **Developer Mode**
3. Restart your terminal
4. Run build again: `node .build/build-release.js`

This allows symlink creation without admin privileges.

#### Option 2: Run Build as Administrator

1. Open **PowerShell** or **Command Prompt** as Administrator
2. Navigate to project: `cd G:\Work\RDO\rdo_overlay`
3. Run build: `node .build/build-release.js`

#### Option 3: Use Unpacked Build (No fix needed)

The unpacked build at `build/frontend/win-unpacked/` is fully functional:

```shell
# Run the application directly
build/frontend/win-unpacked/RDO Map Overlay.exe

# Or create a distribution zip
cd build/frontend
powershell Compress-Archive -Path win-unpacked -DestinationPath RDO-Map-Overlay-v1.0.0.zip
```

Users can extract the zip and run `RDO Map Overlay.exe`.

#### Option 4: Manually Extract winCodeSign (Advanced)

```powershell
# Download the archive manually
$url = "https://github.com/electron-userland/electron-builder-binaries/releases/download/winCodeSign-2.6.0/winCodeSign-2.6.0.7z"
$cache = "$env:LOCALAPPDATA\electron-builder\Cache\winCodeSign"
$archive = "$cache\winCodeSign-2.6.0.7z"

# Create directory
New-Item -ItemType Directory -Force -Path $cache

# Download
Invoke-WebRequest -Uri $url -OutFile $archive

# Extract with 7zip (ignoring symlink errors)
& "C:\Program Files\7-Zip\7z.exe" x -bd $archive "-o$cache" -y 2>$null

# Rename the extracted folder to what electron-builder expects
# (The exact folder name varies - check the error message for the expected name)
```

### Why This Happens

electron-builder always downloads signing tools even when:
- `"sign": null` is set
- `"forceCodeSigning": false` is set
- Environment variables like `WIN_CSC_IDENTITY_AUTO_DISCOVERY=false` are used

This is a known issue: https://github.com/electron-userland/electron-builder/issues/6855

### Current Configuration

**frontend/package.json**:
```json
{
  "build": {
    "win": {
      "target": [{"target": "portable", "arch": ["x64"]}],
      "sign": null
    },
    "forceCodeSigning": false
  }
}
```

## Build Status

✅ **Backend**: `build/backend/rdo-overlay-backend.exe` (223MB)
✅ **Frontend (unpacked)**: `build/frontend/win-unpacked/RDO Map Overlay.exe` (165MB)
❌ **Portable .exe**: Fails due to symlink issue (workaround: use unpacked build)

## Testing the Build

```shell
# Start the unpacked application
cd build/frontend/win-unpacked
./RDO\ Map\ Overlay.exe

# Or create a distributable zip
cd build/frontend
powershell Compress-Archive -Path win-unpacked -DestinationPath ../RDO-Map-Overlay-v1.0.0.zip
```
