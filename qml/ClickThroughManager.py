"""
Click-through management for Qt overlay windows.

Provides platform-specific solutions for selective click-through regions
in transparent overlay windows.
"""

import sys
import ctypes
from PySide6.QtCore import QObject, QTimer, QRect, QPoint, Signal, Slot, Property, Qt
from PySide6.QtGui import QCursor, QRegion
from typing import List, Optional


class ClickThroughManager(QObject):
    """
    Manages selective click-through for overlay windows.

    This class handles the complex task of making certain regions of a
    transparent overlay window interactive while keeping others click-through.
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

        # Platform-specific setup
        if self._platform == 'win32':
            self._setup_windows()
        elif self._platform == 'darwin':
            self._setup_macos()
        else:  # Linux
            self._setup_linux()

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

    def _setup_macos(self):
        """macOS-specific initialization"""
        # macOS uses different window server APIs
        # Would need PyObjC for full implementation
        pass

    def _setup_linux(self):
        """Linux/X11-specific initialization"""
        # X11 uses shape extension for input regions
        # Would need python-xlib for full implementation
        pass

    @Slot('QVariant')
    def setWindow(self, window):
        """Set the window to manage"""
        print(f"[ClickThroughManager] setWindow called with window: {window}")
        print(f"[ClickThroughManager] Window type: {type(window)}")
        self._window = window

        if window and self._platform == 'win32':
            # Get native window handle
            try:
                # For QML windows, we need to check if it's a QQuickWindow
                if hasattr(window, 'winId'):
                    win_id = window.winId()
                    self._hwnd = int(win_id)
                    print(f"[ClickThroughManager] Window handle extracted: {self._hwnd}")

                    # Verify the window position can be accessed
                    try:
                        x = window.x()
                        y = window.y()
                        print(f"[ClickThroughManager] Window position: ({x}, {y})")
                    except Exception as e:
                        print(f"[ClickThroughManager] Warning: Cannot access window position: {e}")
                else:
                    print(f"[ClickThroughManager] ERROR: Window object has no winId() method")

            except Exception as e:
                print(f"[ClickThroughManager] ERROR extracting winId: {e}")
                import traceback
                traceback.print_exc()

    @Slot(int)
    def setWindowId(self, win_id):
        """Set the window by its native ID (for QML compatibility)"""
        if self._platform == 'win32':
            self._hwnd = int(win_id)
            print(f"[ClickThroughManager] Window handle set: {self._hwnd}")

    @Slot()
    def start(self):
        """Start monitoring cursor position"""
        if self._platform == 'win32' and not hasattr(self, '_hwnd'):
            print("[ClickThroughManager] ERROR: No window handle set, cannot start")
            return

        print(f"[ClickThroughManager] Starting cursor monitoring (hwnd: {self._hwnd if hasattr(self, '_hwnd') else 'N/A'})")

        # Enable click-through by default
        self._enable_click_through()

        self._poll_timer.start()

    @Slot()
    def stop(self):
        """Stop monitoring cursor position"""
        print("[ClickThroughManager] Stopping cursor monitoring")
        self._poll_timer.stop()

    @Slot(list)
    def setInteractiveRegions(self, regions: List[QRect]):
        """
        Set regions that should be interactive (not click-through).

        Args:
            regions: List of QRect objects defining interactive areas in LOCAL window coordinates
        """
        # Convert local regions to global screen coordinates
        self._interactive_regions = []

        if self._window and regions:
            # Get window position (top-left corner in global coordinates)
            try:
                # Try multiple methods to get window position
                window_x = 0
                window_y = 0

                # Method 1: Direct x() and y() methods (QML Window)
                if hasattr(self._window, 'x') and hasattr(self._window, 'y'):
                    window_x = self._window.x()
                    window_y = self._window.y()
                    print(f"[ClickThroughManager] Window position from x()/y(): ({window_x}, {window_y})")

                # Method 2: position() method (Qt Widget)
                elif hasattr(self._window, 'position'):
                    pos = self._window.position()
                    window_x = pos.x()
                    window_y = pos.y()
                    print(f"[ClickThroughManager] Window position from position(): ({window_x}, {window_y})")

                # Method 3: geometry() method
                elif hasattr(self._window, 'geometry'):
                    geo = self._window.geometry()
                    window_x = geo.x()
                    window_y = geo.y()
                    print(f"[ClickThroughManager] Window position from geometry(): ({window_x}, {window_y})")

                # For fullscreen windows, position is typically (0, 0)
                # Double-check with window flags
                if hasattr(self._window, 'visibility'):
                    visibility = self._window.visibility()
                    print(f"[ClickThroughManager] Window visibility state: {visibility}")

                for local_rect in regions:
                    # Convert local rect to global coordinates
                    global_rect = QRect(
                        local_rect.x() + window_x,
                        local_rect.y() + window_y,
                        local_rect.width(),
                        local_rect.height()
                    )
                    self._interactive_regions.append(global_rect)
                    print(f"[ClickThroughManager] Region: local({local_rect.x()},{local_rect.y()},{local_rect.width()}x{local_rect.height()}) -> global({global_rect.x()},{global_rect.y()})")

            except Exception as e:
                print(f"[ClickThroughManager] Error converting regions: {e}")
                import traceback
                traceback.print_exc()
                # For fullscreen overlays, assume window is at (0, 0)
                print("[ClickThroughManager] Assuming fullscreen window at (0, 0)")
                for local_rect in regions:
                    self._interactive_regions.append(QRect(local_rect))
        else:
            self._interactive_regions = regions

        print(f"[ClickThroughManager] Updated interactive regions: {len(self._interactive_regions)} regions")

        # Force immediate check after region update (cursor might not have moved)
        self._force_check_cursor()

    @Slot(QRect)
    def addInteractiveRegion(self, rect: QRect):
        """Add a single interactive region"""
        self._interactive_regions.append(rect)

    @Slot()
    def clearInteractiveRegions(self):
        """Clear all interactive regions"""
        self._interactive_regions.clear()

    def _check_cursor(self):
        """Check cursor position and update click-through state"""
        # Get global cursor position
        cursor_pos = QCursor.pos()

        # Only update if cursor moved significantly
        if (abs(cursor_pos.x() - self._last_cursor_pos.x()) < 2 and
            abs(cursor_pos.y() - self._last_cursor_pos.y()) < 2):
            return

        self._last_cursor_pos = cursor_pos

        # Check if cursor is over any interactive region (global coordinates)
        cursor_over_ui = False
        for i, region in enumerate(self._interactive_regions):
            if region.contains(cursor_pos):
                cursor_over_ui = True
                # Debug: show which region was hit
                # print(f"[ClickThroughManager] Cursor at ({cursor_pos.x()},{cursor_pos.y()}) is inside region {i}: ({region.x()},{region.y()},{region.width()}x{region.height()})")
                break

        # Update click-through state if needed
        if cursor_over_ui and self._click_through_enabled:
            print(f"[ClickThroughManager] Cursor entered interactive region at ({cursor_pos.x()},{cursor_pos.y()})")
            self._disable_click_through()
        elif not cursor_over_ui and not self._click_through_enabled:
            print(f"[ClickThroughManager] Cursor left interactive regions at ({cursor_pos.x()},{cursor_pos.y()})")
            self._enable_click_through()

    def _force_check_cursor(self):
        """Force cursor check without movement threshold (for region updates)"""
        # Get global cursor position
        cursor_pos = QCursor.pos()
        self._last_cursor_pos = cursor_pos

        # Check if cursor is over any interactive region (global coordinates)
        cursor_over_ui = False
        for i, region in enumerate(self._interactive_regions):
            if region.contains(cursor_pos):
                cursor_over_ui = True
                print(f"[ClickThroughManager] Force check: Cursor at ({cursor_pos.x()},{cursor_pos.y()}) is inside region {i}")
                break

        if not cursor_over_ui and self._interactive_regions:
            print(f"[ClickThroughManager] Force check: Cursor at ({cursor_pos.x()},{cursor_pos.y()}) is outside all regions")

        # Update click-through state if needed
        if cursor_over_ui and self._click_through_enabled:
            print(f"[ClickThroughManager] Force check: Disabling click-through")
            self._disable_click_through()
        elif not cursor_over_ui and not self._click_through_enabled:
            print(f"[ClickThroughManager] Force check: Enabling click-through")
            self._enable_click_through()

    def _enable_click_through(self):
        """Make window click-through"""
        if self._platform == 'win32':
            self._enable_click_through_windows()
        else:
            self._enable_click_through_qt()

        self._click_through_enabled = True
        self.clickThroughChanged.emit(True)
        print("[ClickThroughManager] Click-through ENABLED")

    def _disable_click_through(self):
        """Make window interactive"""
        if self._platform == 'win32':
            self._disable_click_through_windows()
        else:
            self._disable_click_through_qt()

        self._click_through_enabled = False
        self.clickThroughChanged.emit(False)
        print("[ClickThroughManager] Click-through DISABLED")

    def _enable_click_through_windows(self):
        """Windows-specific: Add WS_EX_TRANSPARENT style"""
        if not hasattr(self, '_hwnd'):
            print("[ClickThroughManager] ERROR: No window handle (_hwnd) set")
            return

        # Get current extended style
        ex_style = self.GetWindowLongPtr(self._hwnd, self.GWL_EXSTYLE)

        # Add transparent flag
        new_style = ex_style | self.WS_EX_TRANSPARENT | self.WS_EX_LAYERED

        # Apply new style
        self.SetWindowLongPtr(self._hwnd, self.GWL_EXSTYLE, new_style)

    def _disable_click_through_windows(self):
        """Windows-specific: Remove WS_EX_TRANSPARENT style"""
        if not hasattr(self, '_hwnd'):
            print("[ClickThroughManager] ERROR: No window handle (_hwnd) set")
            return

        # Get current extended style
        ex_style = self.GetWindowLongPtr(self._hwnd, self.GWL_EXSTYLE)

        # Remove transparent flag but keep layered for transparency
        new_style = (ex_style & ~self.WS_EX_TRANSPARENT) | self.WS_EX_LAYERED

        # Apply new style
        self.SetWindowLongPtr(self._hwnd, self.GWL_EXSTYLE, new_style)

    def _enable_click_through_qt(self):
        """Qt fallback: Set window flags"""
        if not self._window:
            return

        # Store current position
        pos = self._window.position() if hasattr(self._window, 'position') else None

        # Update flags
        flags = self._window.flags()
        flags |= Qt.WindowTransparentForInput
        self._window.setFlags(flags)

        # Restore position and visibility
        if pos:
            self._window.setPosition(pos)
        self._window.show()

    def _disable_click_through_qt(self):
        """Qt fallback: Remove window flags"""
        if not self._window:
            return

        # Store current position
        pos = self._window.position() if hasattr(self._window, 'position') else None

        # Update flags
        flags = self._window.flags()
        flags &= ~Qt.WindowTransparentForInput
        self._window.setFlags(flags)

        # Restore position and visibility
        if pos:
            self._window.setPosition(pos)
        self._window.show()

    # Properties for QML

    @Property(bool, notify=clickThroughChanged)
    def isClickThrough(self):
        """Whether click-through is currently enabled"""
        return self._click_through_enabled


class GlobalHotkeyManager(QObject):
    """
    Manages global hotkeys that work even when window is click-through.

    Uses platform-specific APIs to register system-wide hotkeys that
    bypass Qt's event system.
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
        else:
            print("[GlobalHotkeyManager] Platform not supported, using Qt shortcuts")

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
            else:
                print(f"[GlobalHotkeyManager] Failed to register hotkey ID {id}")

        # Message loop
        msg = wintypes.MSG()
        while True:
            bRet = self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)

            if bRet == 0:
                break  # WM_QUIT

            if msg.message == 0x0312:  # WM_HOTKEY
                hotkey_id = msg.wParam
                if hotkey_id in self._registered_hotkeys:
                    # Emit signal in main thread
                    signal = self._registered_hotkeys[hotkey_id]
                    signal.emit()

    def cleanup(self):
        """Unregister all hotkeys"""
        if self._platform == 'win32':
            for id in self._registered_hotkeys.keys():
                self.user32.UnregisterHotKey(None, id)
            print("[GlobalHotkeyManager] Unregistered all hotkeys")