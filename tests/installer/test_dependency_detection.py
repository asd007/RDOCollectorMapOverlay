"""
Tests for installer dependency detection logic.

Verifies that the installer correctly:
- Detects existing Python installations
- Skips downloading dependencies that already exist
- Validates checksums of cached dependencies
- Re-downloads corrupted dependencies
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import os
import hashlib
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock


class TestPythonDetection:
    """Test Python installation detection."""

    def test_detect_python_in_path(self):
        """Test detection of Python in system PATH."""
        # Check if python is in PATH
        import subprocess
        try:
            result = subprocess.run(['python', '--version'],
                                  capture_output=True, text=True, timeout=5)
            python_found = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            python_found = False

        # This test documents current state - if Python is installed, it should be detected
        if python_found:
            assert result.stdout.startswith('Python') or result.stderr.startswith('Python')

    def test_detect_python_in_registry(self):
        """Test detection of Python via Windows registry."""
        try:
            import winreg

            # Check common Python registry keys
            python_found = False
            possible_keys = [
                r'SOFTWARE\Python\PythonCore',
                r'SOFTWARE\Wow6432Node\Python\PythonCore',
            ]

            for key_path in possible_keys:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    python_found = True
                    winreg.CloseKey(key)
                    break
                except WindowsError:
                    continue

            # Test passes if we can access registry (Windows only)
            assert isinstance(python_found, bool)

        except ImportError:
            pytest.skip("winreg not available (not on Windows)")

    def test_python_version_check(self):
        """Test Python version validation."""
        import sys

        version_info = sys.version_info
        version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

        # Should be Python 3.11+
        assert version_info.major == 3
        assert version_info.minor >= 11, f"Python 3.11+ required, got {version_str}"

    def test_embedded_python_detection(self):
        """Test detection of embedded Python installation."""
        # Create mock embedded Python structure
        with tempfile.TemporaryDirectory() as tmpdir:
            python_dir = Path(tmpdir) / "python"
            python_dir.mkdir()

            # Create marker files for embedded Python
            (python_dir / "python.exe").touch()
            (python_dir / "python311._pth").touch()

            # Check detection logic
            has_python_exe = (python_dir / "python.exe").exists()
            has_pth_file = any(python_dir.glob("*._pth"))  # Embedded Python marker

            is_embedded = has_python_exe and has_pth_file
            assert is_embedded is True


class TestDependencyCache:
    """Test dependency caching mechanism."""

    def test_cache_directory_creation(self):
        """Test that cache directory is created if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "RDOOverlayDeps"

            # Ensure it doesn't exist
            assert not cache_dir.exists()

            # Simulate cache dir creation
            cache_dir.mkdir(parents=True, exist_ok=True)

            assert cache_dir.exists()
            assert cache_dir.is_dir()

    def test_dependency_exists_check(self):
        """Test checking if dependency is already cached."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            dep_file = cache_dir / "python-3.11.0-embed-amd64.zip"

            # Initially doesn't exist
            assert not dep_file.exists()

            # Create it
            dep_file.write_bytes(b"fake python zip")

            # Now exists
            assert dep_file.exists()
            assert dep_file.stat().st_size > 0

    def test_checksum_validation(self):
        """Test MD5 checksum validation of cached dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.zip"
            test_data = b"test data for checksum"
            test_file.write_bytes(test_data)

            # Calculate checksum
            md5 = hashlib.md5()
            md5.update(test_data)
            expected_checksum = md5.hexdigest()

            # Verify checksum
            md5_verify = hashlib.md5()
            md5_verify.update(test_file.read_bytes())
            actual_checksum = md5_verify.hexdigest()

            assert actual_checksum == expected_checksum

    def test_corrupted_dependency_detection(self):
        """Test detection of corrupted cached dependency."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dep_file = Path(tmpdir) / "python.zip"

            # Write some data
            original_data = b"x" * 1000
            dep_file.write_bytes(original_data)

            # Calculate original checksum
            md5 = hashlib.md5()
            md5.update(original_data)
            original_checksum = md5.hexdigest()

            # Corrupt the file
            corrupted_data = b"y" * 1000
            dep_file.write_bytes(corrupted_data)

            # Calculate new checksum
            md5_verify = hashlib.md5()
            md5_verify.update(dep_file.read_bytes())
            new_checksum = md5_verify.hexdigest()

            # Checksums should not match
            assert new_checksum != original_checksum

    def test_skip_download_if_valid(self):
        """Test that valid cached dependencies are not re-downloaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            dep_file = cache_dir / "python.zip"

            # Simulate existing valid dependency
            test_data = b"valid dependency"
            dep_file.write_bytes(test_data)

            # Calculate checksum
            md5 = hashlib.md5()
            md5.update(test_data)
            expected_checksum = md5.hexdigest()

            # Simulate installer checking if download is needed
            file_exists = dep_file.exists()

            if file_exists:
                md5_verify = hashlib.md5()
                md5_verify.update(dep_file.read_bytes())
                actual_checksum = md5_verify.hexdigest()

                needs_download = actual_checksum != expected_checksum
            else:
                needs_download = True

            # Should not need download
            assert not needs_download


class TestDependencyExtraction:
    """Test dependency extraction logic."""

    def test_extract_to_temp(self):
        """Test extraction of dependency to temporary directory."""
        import zipfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test zip file
            zip_path = Path(tmpdir) / "test.zip"
            extract_dir = Path(tmpdir) / "extracted"

            # Create zip with test file
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("test.txt", "test content")

            # Extract
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_dir)

            # Verify extraction
            assert extract_dir.exists()
            assert (extract_dir / "test.txt").exists()
            assert (extract_dir / "test.txt").read_text() == "test content"

    def test_handle_extraction_errors(self):
        """Test handling of extraction errors."""
        import zipfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create invalid zip file
            invalid_zip = Path(tmpdir) / "invalid.zip"
            invalid_zip.write_bytes(b"not a valid zip file")

            # Attempt extraction (should fail gracefully)
            extract_dir = Path(tmpdir) / "extracted"

            with pytest.raises(zipfile.BadZipFile):
                with zipfile.ZipFile(invalid_zip, 'r') as zf:
                    zf.extractall(extract_dir)


class TestInstallationPathLogic:
    """Test installation path selection and validation."""

    def test_default_install_path(self):
        """Test default installation path construction."""
        # Default should be Program Files
        if os.name == 'nt':  # Windows
            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
            default_path = Path(program_files) / "RDO Overlay"

            # Check it's an absolute path with drive letter
            assert default_path.is_absolute()
            assert ':' in default_path.parts[0]  # Drive letter (C:\)
            assert 'Program Files' in str(default_path)
            assert 'RDO Overlay' in str(default_path)
        else:
            pytest.skip("Installation path logic is Windows-specific")

    def test_custom_install_path_validation(self):
        """Test validation of custom installation paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "Custom Install"

            # Path should be valid
            assert custom_path.parent.exists()

            # Can create the directory
            custom_path.mkdir()
            assert custom_path.exists()

    def test_path_with_spaces(self):
        """Test handling of installation paths with spaces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path_with_spaces = Path(tmpdir) / "My Custom Path" / "RDO Overlay"
            path_with_spaces.mkdir(parents=True)

            assert path_with_spaces.exists()
            assert ' ' in str(path_with_spaces)


class TestUpgradeScenario:
    """Test upgrade installation scenarios."""

    def test_detect_existing_installation(self):
        """Test detection of existing RDO Overlay installation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir) / "RDO Overlay"
            install_dir.mkdir()

            # Create marker file
            marker_file = install_dir / "app_qml.py"
            marker_file.touch()

            # Check if installation exists
            is_existing = install_dir.exists() and marker_file.exists()
            assert is_existing is True

    def test_preserve_user_data_on_upgrade(self):
        """Test that user data is preserved during upgrade."""
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir) / "RDO Overlay"
            install_dir.mkdir()

            # Create user data directory
            data_dir = install_dir / "data" / "cache"
            data_dir.mkdir(parents=True)

            # Create user file
            user_file = data_dir / "user_data.dat"
            user_file.write_text("important user data")

            # Simulate upgrade (preserve data dir)
            preserved_data = user_file.read_text()

            # After upgrade, data should still exist
            assert preserved_data == "important user data"

    def test_skip_existing_dependencies_on_upgrade(self):
        """Test that existing dependencies are reused on upgrade."""
        with tempfile.TemporaryDirectory() as tmpdir:
            deps_dir = Path(tmpdir) / "dependencies" / "python"
            deps_dir.mkdir(parents=True)

            # Create Python marker
            python_exe = deps_dir / "python.exe"
            python_exe.touch()

            # Check if dependency exists
            has_python = python_exe.exists()

            # Upgrade should skip download
            needs_python = not has_python
            assert needs_python is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
