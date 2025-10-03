"""
Map Downloader - Downloads HQ map on first launch to reduce installer size
"""
import os
import sys
import requests
from pathlib import Path
from typing import Optional, Callable


def get_map_cache_dir() -> Path:
    """Get platform-specific cache directory for map data."""
    if sys.platform == 'win32':
        base = os.getenv('APPDATA')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.path.expanduser('~/.local/share')

    cache_dir = Path(base) / 'RDO-Map-Overlay' / 'data'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def download_map(url: str, progress_callback: Optional[Callable[[int, int], None]] = None) -> Path:
    """
    Download HQ map from URL with progress tracking.

    Args:
        url: URL to download map from
        progress_callback: Optional callback(bytes_downloaded, total_bytes)

    Returns:
        Path to downloaded map file

    Raises:
        RuntimeError: If download fails
    """
    cache_dir = get_map_cache_dir()
    map_path = cache_dir / 'rdr2_map_hq.png'

    # Skip if already exists
    if map_path.exists():
        print(f"Map already cached at: {map_path}")
        return map_path

    print(f"Downloading map from: {url}")
    print(f"Saving to: {map_path}")

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(map_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback and total_size:
                        progress_callback(downloaded, total_size)

        print(f"✓ Map downloaded successfully: {downloaded / 1024 / 1024:.1f} MB")
        return map_path

    except Exception as e:
        # Clean up partial download
        if map_path.exists():
            map_path.unlink()
        raise RuntimeError(f"Failed to download map: {e}")


def ensure_map_available(url: str) -> Path:
    """
    Ensure map is available, downloading if necessary.

    Args:
        url: URL to download map from if not cached

    Returns:
        Path to map file (either cached or freshly downloaded)
    """
    cache_dir = get_map_cache_dir()
    map_path = cache_dir / 'rdr2_map_hq.png'

    if map_path.exists():
        return map_path

    print("\n" + "="*60)
    print("FIRST LAUNCH: Downloading map assets...")
    print("="*60)

    def progress(downloaded, total):
        if total > 0:
            percent = (downloaded / total) * 100
            mb_downloaded = downloaded / 1024 / 1024
            mb_total = total / 1024 / 1024

            # Progress bar
            bar_length = 40
            filled = int(bar_length * downloaded / total)
            bar = '█' * filled + '░' * (bar_length - filled)

            print(f"\r[{bar}] {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end='', flush=True)

    map_path = download_map(url, progress_callback=progress)
    print("\n" + "="*60)
    print("✓ Map download complete!")
    print("="*60 + "\n")

    return map_path
