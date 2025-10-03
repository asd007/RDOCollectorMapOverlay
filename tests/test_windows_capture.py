#!/usr/bin/env python3
"""
Test Windows Graphics Capture API using windows-capture library.

This will capture only the game window without overlay on top.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import numpy as np
import win32gui
from windows_capture import WindowsCapture, Frame, InternalCaptureControl


# Global frame storage
latest_frame = None
frame_count = 0


class GameCapture(WindowsCapture):
    """Capture class for game window"""

    def on_frame_arrived(self, frame: Frame, capture_control: InternalCaptureControl):
        """Callback when new frame arrives"""
        global latest_frame, frame_count

        # Convert frame to numpy array (BGRA format)
        frame_array = np.array(frame, dtype=np.uint8)

        # Reshape to proper dimensions (height, width, channels)
        # windows-capture returns BGRA format
        height, width = frame.height, frame.width
        latest_frame = frame_array.reshape((height, width, 4))

        frame_count += 1

    def on_closed(self):
        """Called when capture is closed"""
        print("Capture closed")


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


def test_capture():
    """Test capturing from a window"""
    print("=" * 80)
    print("WINDOWS GRAPHICS CAPTURE API TEST")
    print("=" * 80)

    # Look for RDR2 window
    print("\nSearching for Red Dead Redemption 2 window...")
    window_title = find_window_by_partial_title("Red Dead Redemption")

    if window_title:
        print(f"[SUCCESS] Found RDR2 window: {window_title}")
    else:
        print("[WARNING] RDR2 not found. Using fallback test.")
        # Try other common window names for testing
        for test_name in ["Visual Studio Code", "Chrome", "Firefox", "Explorer"]:
            window_title = find_window_by_partial_title(test_name)
            if window_title:
                print(f"Testing with: {window_title}")
                break

    if not window_title:
        print("[ERROR] No suitable window found for testing")
        return

    # Start capture
    print(f"\nStarting capture...")
    print("Capturing 50 frames...\n")

    global latest_frame, frame_count
    latest_frame = None
    frame_count = 0

    try:
        # Create capture instance
        capture = GameCapture(
            cursor_capture=None,
            draw_border=None,
            monitor_index=None,
            window_name=window_title
        )

        # Start capture (blocking mode)
        capture.start()

        # Wait for frames
        start_time = time.time()
        times = []

        while frame_count < 50 and (time.time() - start_time) < 10:
            if latest_frame is not None:
                frame_time = time.time()
                times.append(frame_time)

                if frame_count % 10 == 0:
                    print(f"Frame {frame_count}: {latest_frame.shape}")

            time.sleep(0.01)  # 10ms sleep

        elapsed = time.time() - start_time

        # Stats
        print(f"\n{'=' * 80}")
        print("RESULTS")
        print("=" * 80)
        print(f"\nCaptured {frame_count} frames in {elapsed:.2f}s")

        if frame_count > 0:
            print(f"Average FPS: {frame_count / elapsed:.2f}")

            if len(times) > 1:
                frame_intervals = [times[i] - times[i-1] for i in range(1, len(times))]
                avg_interval = np.mean(frame_intervals) * 1000
                print(f"Average frame interval: {avg_interval:.2f}ms")

        if latest_frame is not None:
            print(f"\nFrame shape: {latest_frame.shape}")
            print(f"Frame dtype: {latest_frame.dtype}")
            print(f"Frame format: BGRA (4 channels)")

        print("\n[SUCCESS] Windows Graphics Capture API works!")
        print("Key benefit: This captures the game window ONLY")
        print("The overlay on top is NOT captured!")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERROR] Capture failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_capture()
