# Build script for RDO Map Overlay Web Installer with automatic dependency resolution
# This creates a minimal ~1-2MB installer that downloads everything during installation
#
# Usage:
#   .\build-web-installer.ps1         # Build the installer
#   .\build-web-installer.ps1 --clean # Clean all build artifacts and exit
#   .\build-web-installer.ps1 -c      # Same as --clean

$ErrorActionPreference = "Stop"

# Check if running in CI/CD environment
$isCI = $env:CI -or $env:TF_BUILD -or $env:GITHUB_ACTIONS -or $env:GITLAB_CI -or $env:JENKINS_HOME
if ($isCI) {
    Write-Host "Running in CI/CD environment" -ForegroundColor Cyan
}

# Function to clean up build artifacts
function Clean-BuildArtifacts {
    param([bool]$Verbose = $true)

    if ($Verbose) {
        Write-Host "Cleaning up build artifacts..." -ForegroundColor Yellow
    }

    # Remove all build artifacts (everything in build/installer/)
    Remove-Item "..\..\build\installer" -Recurse -Force -ErrorAction SilentlyContinue

    # Remove generated icon
    Remove-Item "..\..\frontend\icon.ico" -Force -ErrorAction SilentlyContinue

    if ($Verbose) {
        Write-Host "Cleanup complete" -ForegroundColor Green
    }
}

# Check for --clean flag
if ($args -contains "--clean" -or $args -contains "-c") {
    Clean-BuildArtifacts -Verbose $true
    Write-Host ""
    Write-Host "Cleanup complete. Exiting." -ForegroundColor Green
    exit 0
}

# Always do a quick cleanup before building
Clean-BuildArtifacts -Verbose $false

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Building RDO Map Overlay Web Installer" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Function to download file if not exists
function Download-IfNotExists {
    param(
        [string]$Url,
        [string]$OutputPath,
        [string]$Description
    )

    if (-not (Test-Path $OutputPath)) {
        Write-Host "Downloading $Description..." -ForegroundColor Yellow
        try {
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $Url -OutFile $OutputPath -UserAgent "Wget" -MaximumRedirection 10 -UseBasicParsing
            Write-Host "Downloaded: $Description" -ForegroundColor Green
        }
        catch {
            Write-Host "Failed to download $Description : $_" -ForegroundColor Red
            exit 1
        }
    }
}

# Create build directory structure
$buildDir = "..\..\build\installer"
if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
}

# Check for NSIS installation in build directory, download if not found
$nsisDir = Join-Path $buildDir "nsis"
$makensisPath = Join-Path $nsisDir "makensis.exe"

if (-not (Test-Path $makensisPath)) {
    Write-Host "NSIS not found. Downloading from SourceForge..." -ForegroundColor Yellow

    # Download NSIS zip file
    $nsisZipPath = Join-Path $buildDir "nsis-3.11.zip"
    $nsisUrl = "https://sourceforge.net/projects/nsis/files/NSIS%203/3.11/nsis-3.11.zip/download"

    Download-IfNotExists `
        -Url $nsisUrl `
        -OutputPath $nsisZipPath `
        -Description "NSIS 3.11"

    # Extract NSIS to build directory
    Write-Host "Extracting NSIS..." -ForegroundColor Yellow
    $tempDir = Join-Path $buildDir "temp_nsis"
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force
    }
    Expand-Archive -Path $nsisZipPath -DestinationPath $tempDir -Force

    # Find the extracted NSIS directory (should be nsis-3.11)
    $nsisExtracted = Get-ChildItem -Path $tempDir -Directory | Select-Object -First 1

    if ($nsisExtracted) {
        # Move to nsis directory
        if (Test-Path $nsisDir) {
            Remove-Item $nsisDir -Recurse -Force
        }
        Move-Item -Path $nsisExtracted.FullName -Destination $nsisDir -Force
        Write-Host "NSIS extracted to build directory" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Could not find NSIS directory in archive" -ForegroundColor Red
        exit 1
    }

    # Cleanup
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $nsisZipPath -Force -ErrorAction SilentlyContinue
}

# Verify NSIS is now available
if (-not (Test-Path $makensisPath)) {
    Write-Host "ERROR: NSIS makensis.exe not found at: $makensisPath" -ForegroundColor Red
    exit 1
}

Write-Host "NSIS found at: $nsisDir" -ForegroundColor Green
Write-Host "makensis.exe: $makensisPath" -ForegroundColor Gray

# Use Plugins directory in build folder
$pluginsBaseDir = Join-Path $buildDir "Plugins"
if (-not (Test-Path $pluginsBaseDir)) {
    New-Item -ItemType Directory -Path $pluginsBaseDir -Force | Out-Null
}

# Download required NSIS plugins
$plugins = @(
    @{
        Name = "INetC"
        Url = "https://nsis.sourceforge.io/mediawiki/images/c/c9/Inetc.zip"
    },
    @{
        Name = "nsisunz"
        Url = "https://nsis.sourceforge.io/mediawiki/images/1/1c/Nsisunz.zip"
    }
)

foreach ($plugin in $plugins) {
    # Check if plugin already installed
    $pluginMarker = Join-Path $pluginsBaseDir "$($plugin.Name).installed"
    if (Test-Path $pluginMarker) {
        Write-Host "$($plugin.Name) plugin already installed" -ForegroundColor Green
        continue
    }

    Write-Host "Downloading $($plugin.Name) plugin..." -ForegroundColor Yellow

    # Update plugin zip path to build directory
    $zipPath = Join-Path $buildDir "$($plugin.Name).zip"

    # Download plugin zip
    Download-IfNotExists `
        -Url $plugin.Url `
        -OutputPath $zipPath `
        -Description "$($plugin.Name) plugin"

    # Extract plugin to temp directory
    Write-Host "Extracting $($plugin.Name) plugin..." -ForegroundColor Yellow
    $tempDir = Join-Path $buildDir "temp_plugin_$($plugin.Name)"
    if (Test-Path $tempDir) {
        Remove-Item $tempDir -Recurse -Force
    }
    Expand-Archive -Path $zipPath -DestinationPath $tempDir -Force

    # Find the Plugins directory in the extracted archive
    $pluginsDir = Get-ChildItem -Path $tempDir -Directory -Filter "Plugins" -Recurse | Select-Object -First 1

    if ($pluginsDir) {
        Write-Host "Found Plugins directory: $($pluginsDir.FullName)" -ForegroundColor Gray

        # ONLY copy x86-unicode (32-bit) plugins for NSIS
        $x86UnicodeDir = Join-Path $pluginsDir.FullName "x86-unicode"

        if (Test-Path $x86UnicodeDir) {
            $targetDir = Join-Path $pluginsBaseDir "x86-unicode"
            Write-Host "  Copying x86-unicode (32-bit) plugins to $targetDir" -ForegroundColor Gray

            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }

            # Copy all DLL files from x86-unicode only
            Get-ChildItem -Path $x86UnicodeDir -Filter "*.dll" | ForEach-Object {
                Copy-Item -Path $_.FullName -Destination $targetDir -Force
                Write-Host "    Copied: $($_.Name)" -ForegroundColor Gray
            }

            # Create marker file to indicate successful installation
            New-Item -ItemType File -Path $pluginMarker -Force | Out-Null

            Write-Host "$($plugin.Name) plugin installed successfully" -ForegroundColor Green
        } else {
            Write-Host "ERROR: x86-unicode directory not found in $($plugin.Name) archive" -ForegroundColor Red
        }
    } else {
        # For nsisunz, which has a different structure
        Write-Host "Trying alternate structure for $($plugin.Name)..." -ForegroundColor Yellow

        # Look for DLL files directly
        $dllFiles = Get-ChildItem -Path $tempDir -Filter "*.dll" -Recurse

        if ($dllFiles.Count -gt 0) {
            $targetDir = Join-Path $pluginsBaseDir "x86-unicode"

            if (-not (Test-Path $targetDir)) {
                New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
            }

            foreach ($dll in $dllFiles) {
                # For nsisunz, the DLL might be in a Release folder or similar
                Copy-Item -Path $dll.FullName -Destination $targetDir -Force
                Write-Host "    Copied: $($dll.Name) from $($dll.Directory.Name)" -ForegroundColor Gray
            }

            # Create marker file to indicate successful installation
            New-Item -ItemType File -Path $pluginMarker -Force | Out-Null

            Write-Host "$($plugin.Name) plugin installed successfully" -ForegroundColor Green
        } else {
            Write-Host "ERROR: No DLL files found in $($plugin.Name) archive" -ForegroundColor Red
        }
    }

    # Cleanup
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
}

# Copy plugins to NSIS directory for proper loading
$systemPluginsDir = Join-Path $nsisDir "Plugins\x86-unicode"
if (-not (Test-Path $systemPluginsDir)) {
    New-Item -ItemType Directory -Path $systemPluginsDir -Force | Out-Null
}

Write-Host "Copying plugins to NSIS directory..." -ForegroundColor Yellow
$localPlugins = Join-Path $pluginsBaseDir "x86-unicode"
if (Test-Path $localPlugins) {
    Get-ChildItem -Path $localPlugins -Filter "*.dll" | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $systemPluginsDir -Force
        Write-Host "  Copied: $($_.Name)" -ForegroundColor Gray
    }
    Write-Host "Plugins copied to NSIS directory" -ForegroundColor Green
}

Write-Host ""
Write-Host "Plugins directory structure:" -ForegroundColor Cyan
if (Test-Path $pluginsBaseDir) {
    Get-ChildItem -Path $pluginsBaseDir -Recurse | ForEach-Object {
        if ($_.PSIsContainer) {
            Write-Host "  [DIR] $($_.Name)" -ForegroundColor Gray
        } else {
            $sizeKB = [math]::Round($_.Length / 1KB, 2)
            Write-Host "  [FILE] $($_.Name) ($sizeKB KB)" -ForegroundColor Gray
        }
    }
}

# Create icon and bitmaps if they don't exist
$iconPath = "..\..\frontend\icon.ico"
if (-not (Test-Path $iconPath)) {
    Write-Host "Creating icon..." -ForegroundColor Yellow
    powershell.exe -ExecutionPolicy Bypass -File "..\scripts\create-icon.ps1"
}

$headerBmpPath = Join-Path $buildDir "header.bmp"
$wizardBmpPath = Join-Path $buildDir "wizard.bmp"
if (-not (Test-Path $headerBmpPath) -or -not (Test-Path $wizardBmpPath)) {
    Write-Host "Creating installer bitmaps..." -ForegroundColor Yellow
    # Ensure directory exists and convert to absolute path
    if (-not (Test-Path $buildDir)) {
        New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
    }
    $buildDirAbsolute = (Resolve-Path $buildDir).Path
    powershell.exe -ExecutionPolicy Bypass -File "..\scripts\create-bitmaps.ps1" -OutputDir $buildDirAbsolute
}

# Note: Frontend dependencies (node_modules) will be installed at install time
# This keeps the installer small - npm install + electron-rebuild happens during installation
Write-Host ""
Write-Host "Frontend dependencies will be installed during installation (not bundled)" -ForegroundColor Cyan

# Bundle backend source files to build/backend-source
Write-Host ""
Write-Host "Bundling backend source files..." -ForegroundColor Yellow
$backendSourceDir = Join-Path $buildDir "backend-source"

# Clean and recreate backend source directory
if (Test-Path $backendSourceDir) {
    Remove-Item $backendSourceDir -Recurse -Force
}
New-Item -ItemType Directory -Path $backendSourceDir -Force | Out-Null

# Copy Python backend files
$sourceRoot = Resolve-Path "..\..\"
Copy-Item (Join-Path $sourceRoot "app.py") $backendSourceDir -Force
Copy-Item (Join-Path $sourceRoot "requirements.txt") $backendSourceDir -Force

# Copy backend modules (Python only - exclude node_modules, __pycache__, etc.)
$modules = @("config", "core", "matching", "api", "models")
foreach ($module in $modules) {
    $targetDir = Join-Path $backendSourceDir $module
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

    # Only copy .py files, skip __pycache__ and other artifacts
    Get-ChildItem (Join-Path $sourceRoot $module) -Filter "*.py" | ForEach-Object {
        Copy-Item $_.FullName $targetDir -Force
    }
}

# Copy data directory (JSON files only)
$dataDir = Join-Path $backendSourceDir "data"
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
Copy-Item (Join-Path $sourceRoot "data\*.json") $dataDir -Force -ErrorAction SilentlyContinue

Write-Host "Backend source bundled to: $backendSourceDir" -ForegroundColor Green

# Count files
$fileCount = (Get-ChildItem -Path $backendSourceDir -Recurse -File).Count
Write-Host "Total files: $fileCount" -ForegroundColor Gray

# Compile the installer
Write-Host ""
Write-Host "Compiling installer..." -ForegroundColor Cyan
Write-Host "Using makensis: $makensisPath" -ForegroundColor Gray

# Get version from package.json or Git tag
$version = "1.0.0"  # Default
if (Test-Path "..\..\frontend\package.json") {
    $packageJson = Get-Content "..\..\frontend\package.json" -Raw | ConvertFrom-Json
    if ($packageJson.version) {
        $version = $packageJson.version
        Write-Host "Using version from package.json: $version" -ForegroundColor Cyan
    }
} elseif (Get-Command git -ErrorAction SilentlyContinue) {
    try {
        $gitTag = git describe --tags --abbrev=0 2>$null
        if ($gitTag) {
            $version = $gitTag -replace '^v', ''
            Write-Host "Using version from git tag: $version" -ForegroundColor Cyan
        }
    } catch {
        # Ignore git errors
    }
}

# Ensure build output directory exists
if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
}

# Remove any existing installer files (they might be locked)
Write-Host "Removing old installer files..." -ForegroundColor Yellow
$lockedFiles = @()
Get-ChildItem -Path $buildDir -Filter "*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    $fileName = $_.Name
    try {
        Remove-Item $_.FullName -Force -ErrorAction Stop
        Write-Host "  Removed: $fileName" -ForegroundColor Gray
    }
    catch {
        $lockedFiles += $fileName
    }
}

if ($lockedFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "ERROR: The following installer files are locked and cannot be removed:" -ForegroundColor Red
    $lockedFiles | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "Please:" -ForegroundColor Yellow
    Write-Host "  1. Close File Explorer if you have the build folder open" -ForegroundColor Gray
    Write-Host "  2. Close any running installer processes" -ForegroundColor Gray
    Write-Host "  3. Wait for Windows Defender/antivirus scan to complete" -ForegroundColor Gray
    Write-Host "  4. Or manually delete the files from: $buildDir" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

$process = Start-Process -FilePath $makensisPath -ArgumentList "/V3", "/DPRODUCT_VERSION=$version", "installer-main.nsi" -Wait -NoNewWindow -PassThru -WorkingDirectory $PSScriptRoot

if ($process.ExitCode -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to compile installer (Exit code: $($process.ExitCode))" -ForegroundColor Red

    # Provide debugging information
    Write-Host ""
    Write-Host "Troubleshooting tips:" -ForegroundColor Yellow
    Write-Host "1. Check if output directory exists: $buildDir" -ForegroundColor Gray
    Write-Host "2. Check if you have write permissions to that directory" -ForegroundColor Gray
    Write-Host "3. Close any running installer files that might be locked" -ForegroundColor Gray
    Write-Host "4. Build directory contents:" -ForegroundColor Gray
    if (Test-Path $buildDir) {
        Get-ChildItem $buildDir | ForEach-Object { Write-Host "   - $($_.Name)" -ForegroundColor Gray }
    } else {
        Write-Host "   - Directory does not exist!" -ForegroundColor Red
    }

    exit $process.ExitCode
}

# Check output
$installer = Get-ChildItem -Path $buildDir -Filter "RDO-Map-Overlay-WebSetup-*.exe" | Select-Object -First 1

if ($installer) {
    $sizeMB = [math]::Round($installer.Length / 1MB, 2)

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "Build Complete!" -ForegroundColor Green
    Write-Host "Installer: $($installer.FullName)" -ForegroundColor White
    Write-Host "Size: $sizeMB MB" -ForegroundColor White
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "The web installer is ready for distribution." -ForegroundColor Cyan
    Write-Host "It will download ~205MB during installation." -ForegroundColor Cyan
    Write-Host "Final installation size will be ~400MB." -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Installer not found in output directory" -ForegroundColor Red
    exit 1
}