# Installer Tests

Tests for the NSIS installer build system, dependency management, and installation process.

## Test Categories

### Dependency Detection Tests
- Test that installer correctly detects existing Python installations
- Test that subsequent installs skip already-downloaded dependencies
- Test version checking logic

### Installer Build Tests
- Test that `build-web-installer.ps1` completes successfully
- Test that generated `.exe` has correct metadata
- Test that installer size is reasonable (dependencies are not embedded)
- Test that NSIS compilation produces no errors

### Installation Workflow Tests
- Test fresh install on clean system (VM/container)
- Test upgrade install over existing installation
- Test dependency download and extraction
- Test that launcher batch file is created correctly
- Test that Start Menu shortcuts are created

### Uninstall Tests
- Test that uninstaller removes application files
- Test that uninstaller preserves or removes dependencies based on user choice
- Test that registry keys are cleaned up
- Test that Start Menu shortcuts are removed

## Running Installer Tests

```bash
# Run dependency detection tests
python tests/installer/test_dependency_detection.py

# Run installer build tests
python tests/installer/test_installer_build.py

# Run full installation test (requires VM/container or clean system)
python tests/installer/test_full_install.py --vm-snapshot "clean-windows-10"

# Test upgrade scenario
python tests/installer/test_upgrade_install.py
```

## Test Infrastructure

### VM/Container Setup
For full installation testing, we use:
- Windows 10 VM with clean snapshot
- No Python or other dependencies pre-installed
- Snapshot can be reset between tests

### Dependency Cache Testing
Tests verify:
- Dependencies are downloaded to `$TEMP\RDOOverlayDeps\`
- MD5 checksums are validated
- Existing valid dependencies are reused
- Corrupted downloads are re-downloaded

### Mock Installer Testing
For faster iteration:
- Mock NSIS compiler for syntax validation
- Mock dependency downloads using local test files
- Dry-run mode that simulates install without actually writing files

## Test Data

### Sample Dependencies
- `tests/installer/testdata/python-3.11.0-embed-amd64.zip` (small mock file)

### Expected Install Structure
```
C:\Program Files\RDO Overlay\
├── app_qml.py
├── config/
├── core/
├── api/
├── matching/
├── qml/
├── data/
├── dependencies/
│   └── python/
├── RDO Overlay Launcher.bat
└── Uninstall.exe
```

## CI/CD Integration

GitHub Actions workflow runs:
1. Dependency detection tests (fast, runs on every PR)
2. Installer build tests (medium, runs on every PR)
3. VM installation tests (slow, runs on main branch only)

## Notes

- Full installation tests require Windows VM access
- Some tests require Administrator privileges
- Mock tests are fast and run in CI
- Real installation tests are manual or VM-automated
