"""Click Observer - observes global mouse clicks and emits to frontend"""

import threading
from typing import Callable

try:
    from pynput import mouse
    CLICK_OBSERVATION_AVAILABLE = True
except ImportError:
    CLICK_OBSERVATION_AVAILABLE = False


class ClickObserver:
    """
    Observes global mouse clicks at OS level using pynput.
    Does NOT consume or interfere with clicks - purely observational.
    Emits click events to frontend for hit-testing and reaction.
    Also tracks mouse button state for panning detection.
    """

    def __init__(self, emit_callback: Callable):
        """
        Args:
            emit_callback: Function to call with (event_name, data) for WebSocket emission
        """
        self.emit_callback = emit_callback
        self.running = False
        self.listener = None

        # Mouse button state tracking
        self._left_button_down = False
        self._right_button_down = False

    def _on_click(self, x: int, y: int, button, pressed: bool):
        """
        Global click handler - called by pynput at OS level.

        Args:
            x, y: Screen coordinates of click
            button: mouse.Button.left or mouse.Button.right
            pressed: True on button down, False on button up

        Returns:
            True: Always let click continue to game (never consume)
        """
        # Track button state
        is_left = (button == mouse.Button.left)
        is_right = (button == mouse.Button.right)

        if is_left:
            self._left_button_down = pressed
        elif is_right:
            self._right_button_down = pressed

        # Emit button state change (for panning detection)
        try:
            self.emit_callback('mouse-button-state', {
                'left_down': self._left_button_down,
                'right_down': self._right_button_down,
                'pressed': pressed,
                'button': 'left' if is_left else 'right'
            })
        except Exception as e:
            print(f"[Click Observer] Error emitting button state: {e}")

        # Also emit click event on button down (for click handling)
        if pressed:
            try:
                self.emit_callback('mouse-clicked', {
                    'x': x,
                    'y': y,
                    'button': 'left' if is_left else 'right'
                })
            except Exception as e:
                print(f"[Click Observer] Error emitting click: {e}")

        # Always return True - let click pass through to game
        return True

    def start(self):
        """Start observing global mouse clicks"""
        if self.running:
            return

        if not CLICK_OBSERVATION_AVAILABLE:
            print("[ERROR] Click observation unavailable (pynput not installed)")
            return

        self.running = True

        # Start pynput mouse listener
        self.listener = mouse.Listener(on_click=self._on_click)
        self.listener.start()

        print("[OK] Click observer started (global mouse hooks - observe only)")

    def is_left_button_down(self) -> bool:
        """Check if left mouse button is currently pressed"""
        return self._left_button_down

    def is_right_button_down(self) -> bool:
        """Check if right mouse button is currently pressed"""
        return self._right_button_down

    def stop(self):
        """Stop observing clicks"""
        if not self.running:
            return

        self.running = False

        if self.listener:
            self.listener.stop()
            self.listener = None

        print("[OK] Click observer stopped")
