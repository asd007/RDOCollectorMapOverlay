"""
Port management for backend server.
Finds available port and communicates it to frontend.
"""

import socket
import json
import os
from pathlib import Path


def find_available_port(start_port=5000, max_attempts=100):
    """
    Find an available port starting from start_port.

    Args:
        start_port: Port to start searching from
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', port))
            sock.close()
            return port
        except OSError:
            continue

    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts}")


def write_port_file(port, app_dir=None):
    """
    Write port number to a file for frontend to read.

    Args:
        port: Port number to write
        app_dir: Application directory (defaults to temp dir)
    """
    if app_dir is None:
        app_dir = os.getenv('TEMP') or os.getenv('TMP') or '/tmp'

    port_file = Path(app_dir) / 'rdo_overlay_port.json'

    with open(port_file, 'w') as f:
        json.dump({'port': port, 'status': 'ready'}, f)

    return port_file


def read_port_file(app_dir=None):
    """
    Read port number from file.

    Args:
        app_dir: Application directory (defaults to temp dir)

    Returns:
        Port number or None if file doesn't exist
    """
    if app_dir is None:
        app_dir = os.getenv('TEMP') or os.getenv('TMP') or '/tmp'

    port_file = Path(app_dir) / 'rdo_overlay_port.json'

    if not port_file.exists():
        return None

    try:
        with open(port_file, 'r') as f:
            data = json.load(f)
            return data.get('port')
    except (json.JSONDecodeError, IOError):
        return None
