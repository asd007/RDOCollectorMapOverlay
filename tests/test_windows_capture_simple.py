#!/usr/bin/env python3
"""
Simple test of windows-capture library - synchronous capture approach.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import numpy as np
import win32gui
import cv2


def find_window_by_partial_title(partial_title):
    """Find window by partial title match"""
    windows = []

    def enum_handler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                windows.append({'hwnd': hwnd, 'title': title})

    win32gui.EnumWindows(enum_handler, None)

    # Look for matching window
    for window in windows:
        if partial_title.lower() in window['title'].lower():
            return window['title']

    return None


def test_windows_capture_sync():
    """Test synchronous window capture"""
    from windows_capture import WindowsCapture

    print("=" * 80)
    print("WINDOWS CAPTURE SYNCHRONOUS TEST")
    print("=" * 80)

    # Find RDR2
    print("\nSearching for Red Dead Redemption 2...")
    window_title = find_window_by_partial_title("Red Dead Redemption")

    if not window_title:
        print("RDR2 not found, using test window")
        for test_name in ["Visual Studio Code", "Chrome", "Firefox"]:
            window_title = find_window_by_partial_title(test_name)
            if window_title:
                print(f"Using: {window_title}")
                break

    if not window_title:
        print("No window found")
        return

    print(f"Capturing from: {window_title}")

    # Create capture
    frame_count = 0
    total_time = 0

    capture = WindowsCapture(window_name=window_title)

    @capture.event
    def on_frame_arrived(frame, capture_control):
        nonlocal frame_count, total_time
        start = time.time()

        # Get frame as numpy array (BGRA format)
        # The frame buffer is directly accessible as array-like
        img = frame.frame_buffer

        # Convert BGRA to BGR
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        elapsed = (time.time() - start) * 1000
        total_time += elapsed

        frame_count += 1
        if frame_count % 10 == 0:
            print(f"Frame {frame_count}: {img_bgr.shape}, process={elapsed:.2f}ms")

        if frame_count >= 50:
            capture_control.stop()

    @capture.event
    def on_closed():
        print("Capture stopped")

    try:
        print("\nStarting capture (will capture 50 frames)...\n")

        start_time = time.time()
        capture.start()  # Blocking
        duration = time.time() - start_time

        print(f"\n{'=' * 80}")
        print("RESULTS")
        print("=" * 80)
        print(f"Captured {frame_count} frames in {duration:.2f}s")
        print(f"FPS: {frame_count / duration:.1f}")
        print(f"Avg processing time: {total_time / frame_count:.2f}ms per frame")
        print("\n[SUCCESS] Windows Graphics Capture works!")
        print("This captures ONLY the game window, not overlays on top!")
        print("=" * 80)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_windows_capture_sync()
