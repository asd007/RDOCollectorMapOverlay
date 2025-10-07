"""
Fixed Click-through management for Qt overlay windows.
This version properly handles coordinate conversion and window handle extraction.
"""

import sys
import ctypes
from PySide6.QtCore import QObject, QTimer, QRect, QPoint, Signal, Slot, Property, Qt
from PySide6.QtGui import QCursor, QRegion
from typing import List, Optional


class ClickThroughManager(QObject):
    """
    Manages selective click-through for overlay windows.
    FIXED VERSION: Properly handles QML window coordinates.
    """

    # Signals
    clickThroughChanged = Signal(bool)  # Emitted when click-through state changes

    def __init__(self, window=None, parent=None):
        super().__init__(parent)

        self._window = window
        self._click_through_enabled = True
        self._interactive_regions: List[QRect] = []
        self._last_cursor_pos = QPoint()
        self._platform = sys.platform
        self._hwnd = None

        # Platform-specific setup
        if self._platform == 'win32':
            self._setup_windows()

        # Cursor polling timer
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._check_cursor)
        self._poll_timer.setInterval(16)  # 60 FPS

    def _setup_windows(self):
        """Windows-specific initialization"""
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

        # Window style constants
        self.WS_EX_TRANSPARENT = 0x00000020
        self.WS_EX_LAYERED = 0x00080000
        self.GWL_EXSTYLE = -20

        # SetWindowLong functions
        if ctypes.sizeof(ctypes.c_void_p) == 8:  # 64-bit
            self.SetWindowLongPtr = self.user32.SetWindowLongPtrW
            self.GetWindowLongPtr = self.user32.GetWindowLongPtrW
        else:  # 32-bit
            self.SetWindowLongPtr = self.user32.SetWindowLongW
            self.GetWindowLongPtr = self.user32.GetWindowLongW

    @Slot('QVariant')
    def setWindow(self, window):
        """Set the window to manage"""
        self._window = window

        if window and self._platform == 'win32':
            try:
                # Extract native window handle
                if hasattr(window, 'winId'):
                    win_id = window.winId()
                    self._hwnd = int(win_id)

            except Exception as e:
                print(f"[ClickThroughManager] Error setting window: {e}")

    @Slot(int)
    def setWindowId(self, win_id):
        """Set the window by its native ID"""
        if self._platform == 'win32':
            self._hwnd = int(win_id)

    @Slot()
    def start(self):
        """Start monitoring cursor position"""
        if self._platform == 'win32' and not self._hwnd:
            print("[ClickThroughManager] ERROR: No window handle set")
            return

        # Enable click-through by default
        self._enable_click_through()
        self._poll_timer.start()

    @Slot()
    def stop(self):
        """Stop monitoring cursor position"""
        self._poll_timer.stop()

    @Slot('QVariantList')
    def setInteractiveRegions(self, regions):
        """
        Set regions that should be interactive (not click-through).
        Regions are in LOCAL window coordinates and will be converted to global.
        """
        self._interactive_regions = []

        if not regions:
            self._force_check_cursor()
            return

        # Get window position for coordinate conversion
        window_x = 0
        window_y = 0

        if self._window:
            try:
                # Try to get window position
                if hasattr(self._window, 'x') and hasattr(self._window, 'y'):
                    # QML Window properties
                    window_x = self._window.x() or 0
                    window_y = self._window.y() or 0
                elif hasattr(self._window, 'pos'):
                    # Qt Widget
                    pos = self._window.pos()
                    window_x = pos.x()
                    window_y = pos.y()
            except:
                # Fullscreen windows are typically at (0, 0)
                pass

        # Convert local regions to global coordinates
        for i, variant_rect in enumerate(regions):
            # Convert QVariant to QRect (from QML Qt.rect())
            # QML passes as dictionary with x, y, width, height
            if isinstance(variant_rect, dict):
                local_rect = QRect(
                    int(variant_rect.get('x', 0)),
                    int(variant_rect.get('y', 0)),
                    int(variant_rect.get('width', 0)),
                    int(variant_rect.get('height', 0))
                )
            else:
                # Fallback: assume it's already a QRect
                local_rect = variant_rect

            # Create global rectangle
            global_rect = QRect(
                local_rect.x() + window_x,
                local_rect.y() + window_y,
                local_rect.width(),
                local_rect.height()
            )
            self._interactive_regions.append(global_rect)

        # Check cursor immediately after updating regions
        self._force_check_cursor()

    def _check_cursor(self):
        """Check cursor position and update click-through state"""
        cursor_pos = QCursor.pos()

        # Only process if cursor moved significantly (reduces CPU usage)
        dx = abs(cursor_pos.x() - self._last_cursor_pos.x())
        dy = abs(cursor_pos.y() - self._last_cursor_pos.y())

        if dx < 2 and dy < 2:
            return

        self._last_cursor_pos = cursor_pos
        self._update_state_for_cursor(cursor_pos)

    def _force_check_cursor(self):
        """Force immediate cursor check (used after region updates)"""
        cursor_pos = QCursor.pos()
        self._last_cursor_pos = cursor_pos
        self._update_state_for_cursor(cursor_pos)

    def _update_state_for_cursor(self, cursor_pos):
        """Update click-through state based on cursor position"""
        # Check if cursor is in any interactive region
        cursor_in_region = False

        for i, region in enumerate(self._interactive_regions):
            if region.contains(cursor_pos):
                cursor_in_region = True
                break

        # Update state if needed
        if cursor_in_region and self._click_through_enabled:
            self._disable_click_through()

        elif not cursor_in_region and not self._click_through_enabled:
            self._enable_click_through()

    def _enable_click_through(self):
        """Make window click-through"""
        if self._platform == 'win32':
            self._enable_click_through_windows()

        self._click_through_enabled = True
        self.clickThroughChanged.emit(True)

    def _disable_click_through(self):
        """Make window interactive"""
        if self._platform == 'win32':
            self._disable_click_through_windows()

        self._click_through_enabled = False
        self.clickThroughChanged.emit(False)

    def _enable_click_through_windows(self):
        """Windows: Add WS_EX_TRANSPARENT style"""
        if not self._hwnd:
            print("[ClickThroughManager] ERROR: No window handle")
            return

        try:
            # Get current extended style
            ex_style = self.GetWindowLongPtr(self._hwnd, self.GWL_EXSTYLE)

            # Add transparent flag
            new_style = ex_style | self.WS_EX_TRANSPARENT | self.WS_EX_LAYERED

            # Apply new style
            result = self.SetWindowLongPtr(self._hwnd, self.GWL_EXSTYLE, new_style)

            if result == 0:
                error = self.kernel32.GetLastError()
                print(f"[ClickThroughManager] Warning: SetWindowLongPtr returned 0, error: {error}")

        except Exception as e:
            print(f"[ClickThroughManager] Error enabling click-through: {e}")

    def _disable_click_through_windows(self):
        """Windows: Remove WS_EX_TRANSPARENT style"""
        if not self._hwnd:
            print("[ClickThroughManager] ERROR: No window handle")
            return

        try:
            # Get current extended style
            ex_style = self.GetWindowLongPtr(self._hwnd, self.GWL_EXSTYLE)

            # Remove transparent flag but keep layered for transparency
            new_style = (ex_style & ~self.WS_EX_TRANSPARENT) | self.WS_EX_LAYERED

            # Apply new style
            result = self.SetWindowLongPtr(self._hwnd, self.GWL_EXSTYLE, new_style)

            if result == 0:
                error = self.kernel32.GetLastError()
                print(f"[ClickThroughManager] Warning: SetWindowLongPtr returned 0, error: {error}")

        except Exception as e:
            print(f"[ClickThroughManager] Error disabling click-through: {e}")

    # Properties for QML
    @Property(bool, notify=clickThroughChanged)
    def isClickThrough(self):
        """Whether click-through is currently enabled"""
        return self._click_through_enabled


# Keep the GlobalHotkeyManager from original file
class GlobalHotkeyManager(QObject):
    """
    Manages global hotkeys that work even when window is click-through.
    """

    # Signals for each hotkey
    f5Pressed = Signal()
    f6Pressed = Signal()
    f7Pressed = Signal()
    f8Pressed = Signal()
    f9Pressed = Signal()
    ctrlQPressed = Signal()
    ctrlShiftCPressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._platform = sys.platform
        self._registered_hotkeys = {}

        if self._platform == 'win32':
            self._setup_windows_hotkeys()

    def _setup_windows_hotkeys(self):
        """Setup Windows global hotkeys using RegisterHotKey"""
        import threading
        import ctypes
        from ctypes import wintypes

        self.user32 = ctypes.windll.user32

        # Virtual key codes
        self.VK_F5 = 0x74
        self.VK_F6 = 0x75
        self.VK_F7 = 0x76
        self.VK_F8 = 0x77
        self.VK_F9 = 0x78
        self.VK_Q = 0x51
        self.VK_C = 0x43

        # Modifiers
        self.MOD_CONTROL = 0x0002
        self.MOD_SHIFT = 0x0004

        # Start hotkey thread
        self._hotkey_thread = threading.Thread(target=self._hotkey_loop, daemon=True)
        self._hotkey_thread.start()

    def _hotkey_loop(self):
        """Windows message loop for global hotkeys"""
        import ctypes
        from ctypes import wintypes

        # Register hotkeys
        hotkeys = [
            (1, 0, self.VK_F5, self.f5Pressed),
            (2, 0, self.VK_F6, self.f6Pressed),
            (3, 0, self.VK_F7, self.f7Pressed),
            (4, 0, self.VK_F8, self.f8Pressed),
            (5, 0, self.VK_F9, self.f9Pressed),
            (6, self.MOD_CONTROL, self.VK_Q, self.ctrlQPressed),
            (7, self.MOD_CONTROL | self.MOD_SHIFT, self.VK_C, self.ctrlShiftCPressed)
        ]

        for id, modifiers, vk, signal in hotkeys:
            if self.user32.RegisterHotKey(None, id, modifiers, vk):
                self._registered_hotkeys[id] = signal
                key_name = f"F{vk - 0x6F}" if 0x70 <= vk <= 0x87 else chr(vk)
                mod_str = ""
                if modifiers & self.MOD_CONTROL:
                    mod_str += "Ctrl+"
                if modifiers & self.MOD_SHIFT:
                    mod_str += "Shift+"
                print(f"[GlobalHotkeyManager] Registered: {mod_str}{key_name}")

        # Message loop
        msg = wintypes.MSG()
        while True:
            bRet = self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)

            if bRet == 0:
                break  # WM_QUIT

            if msg.message == 0x0312:  # WM_HOTKEY
                hotkey_id = msg.wParam
                if hotkey_id in self._registered_hotkeys:
                    signal = self._registered_hotkeys[hotkey_id]
                    signal.emit()

    def cleanup(self):
        """Unregister all hotkeys"""
        if self._platform == 'win32':
            for id in self._registered_hotkeys.keys():
                self.user32.UnregisterHotKey(None, id)
            print("[GlobalHotkeyManager] Unregistered all hotkeys")