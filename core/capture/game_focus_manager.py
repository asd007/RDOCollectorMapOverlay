"""Game Focus Manager - monitors RDR2 window focus state"""

import threading
from typing import Callable
import time

# Windows-specific imports for active window detection
try:
    import win32gui
    WINDOW_DETECTION_AVAILABLE = True
except ImportError:
    WINDOW_DETECTION_AVAILABLE = False


class GameFocusManager:
    """
    Manages RDR2 window focus detection.
    Broadcasts window state changes via WebSocket.
    """

    def __init__(self, emit_callback: Callable):
        """
        Args:
            emit_callback: Function to call with (event_name, data) for WebSocket emission
        """
        self.emit_callback = emit_callback
        self.running = False

        # Active window monitoring
        self.window_monitor_thread = None
        self.window_monitor_running = False
        self.last_rdr2_active = None  # Track state changes

    def _is_rdr2_active(self) -> bool:
        """Check if RDR2 is the active window (or our overlay when interacting)"""
        if not WINDOW_DETECTION_AVAILABLE:
            return True  # Assume active if we can't detect

        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)

            # Check if RDR2 is active (ignore everything else)
            is_rdr2 = title.lower() == 'red dead redemption 2'

            # Only log on state change or first check
            if self.last_rdr2_active is None or is_rdr2 != self.last_rdr2_active:
                if is_rdr2:
                    print(f"[Game Focus] [OK] RDR2 is now active")
                else:
                    print(f"[Game Focus] [ERROR] RDR2 is now inactive")

            return is_rdr2
        except Exception as e:
            print(f"[Game Focus] Exception: {e}, assuming RDR2 active")
            return True  # Assume active on error

    def get_rdr2_state(self) -> bool:
        """Get current RDR2 window state (for initial sync on connect)"""
        return self._is_rdr2_active()

    def _monitor_active_window(self):
        """Monitor active window in background thread - broadcasts every 100ms"""
        while self.window_monitor_running:
            try:
                is_active = self._is_rdr2_active()

                # Always broadcast current state (cheap operation, ensures sync)
                self.emit_callback('window-focus-changed', {
                    'is_rdr2_active': is_active
                })

                # Update tracked state
                self.last_rdr2_active = is_active

                # Broadcast every 100ms
                time.sleep(0.1)
            except Exception as e:
                print(f"[Game Focus] Window monitor error: {e}")
                time.sleep(1)

    def _debug_find_overlay_window(self):
        """Debug: Find and print overlay window title"""
        if not WINDOW_DETECTION_AVAILABLE:
            return

        try:
            def enum_handler(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and 'rdo' in title.lower():
                        results.append((hwnd, title))
                    elif title and 'overlay' in title.lower():
                        results.append((hwnd, title))

            windows = []
            win32gui.EnumWindows(enum_handler, windows)

            if windows:
                print(f"[Debug] Found overlay windows:")
                for hwnd, title in windows:
                    print(f"  - HWND: {hwnd}, Title: '{title}'")
            else:
                print(f"[Debug] No overlay windows found")

        except Exception as e:
            print(f"[Debug] Error finding overlay: {e}")

    def start(self):
        """Start window monitor"""
        if self.running:
            return

        self.running = True

        # Start window monitor
        if WINDOW_DETECTION_AVAILABLE:
            self.window_monitor_running = True
            self.window_monitor_thread = threading.Thread(
                target=self._monitor_active_window,
                daemon=True
            )
            self.window_monitor_thread.start()
            print("[OK] Game focus manager started (window monitoring)")

            # Debug: Find overlay window after a delay (frontend needs time to start)
            def delayed_debug():
                time.sleep(3)
                self._debug_find_overlay_window()

            threading.Thread(target=delayed_debug, daemon=True).start()
        else:
            print("[OK] Game focus manager started (window detection unavailable)")

    def stop(self):
        """Stop window monitor"""
        if not self.running:
            return

        self.running = False

        # Stop window monitor
        if self.window_monitor_thread:
            self.window_monitor_running = False
            self.window_monitor_thread.join(timeout=2)
            self.window_monitor_thread = None

        print("[OK] Game focus manager stopped")
