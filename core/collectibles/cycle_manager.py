"""
Cycle management: periodic cycle change detection and collectibles reload.
Extracted from ContinuousCaptureService for single responsibility.
"""

import time
from typing import Optional


class CycleManager:
    """
    Manages periodic cycle change detection and collectibles reloading.

    Red Dead Online has daily cycles that change collectible locations.
    This component periodically checks for cycle changes and triggers reloads.

    Responsibilities:
    - Periodic cycle change detection
    - Collectibles reload coordination
    - Cycle change statistics

    Thread safety: Not thread-safe (designed for single capture thread).
    """

    def __init__(self, check_interval: float = 300.0):
        """
        Initialize cycle manager.

        Args:
            check_interval: Time between cycle checks in seconds (default 300 = 5 minutes)
        """
        self.check_interval = check_interval
        self.last_check_time = time.time()

        # Statistics
        self.total_checks = 0
        self.cycle_changes_detected = 0
        self.reload_successes = 0
        self.reload_failures = 0

    def should_check_now(self) -> bool:
        """
        Check if it's time to check for cycle changes.

        Returns:
            True if enough time has passed since last check
        """
        current_time = time.time()
        elapsed = current_time - self.last_check_time

        if elapsed >= self.check_interval:
            self.last_check_time = current_time
            return True

        return False

    def check_and_reload(self, state) -> bool:
        """
        Check for cycle changes and reload collectibles if needed.

        Args:
            state: ApplicationState instance with set_collectibles() method
                  and coord_transform attribute

        Returns:
            True if cycle changed and reload succeeded, False otherwise
        """
        self.total_checks += 1

        try:
            from core.collectibles.collectibles_repository import CollectiblesRepository

            # Check if daily cycle changed
            cycle_changed = CollectiblesRepository.check_cycle_changed()

            if cycle_changed:
                self.cycle_changes_detected += 1
                print("[Cycle Change] Detected cycle change - reloading collectibles...")

                if state is None:
                    print("[Cycle Change] Warning: state not set, cannot reload collectibles")
                    self.reload_failures += 1
                    return False

                # Reload collectibles from Joan Ropke API
                collectibles = CollectiblesRepository.load(state.coord_transform)
                state.set_collectibles(collectibles)

                self.reload_successes += 1
                print(f"[Cycle Change] Reloaded {len(collectibles)} collectibles")
                return True

        except Exception as e:
            self.reload_failures += 1
            print(f"[Cycle Change] Error checking/reloading: {e}")
            return False

        return False

    def get_stats(self) -> dict:
        """
        Get cycle management statistics.

        Returns:
            Dict with:
                - check_interval: Time between checks (seconds)
                - last_check_time: Timestamp of last check
                - seconds_until_next_check: Time until next check
                - total_checks: Total number of checks performed
                - cycle_changes_detected: Number of cycle changes found
                - reload_successes: Successful collectible reloads
                - reload_failures: Failed reload attempts
        """
        current_time = time.time()
        elapsed = current_time - self.last_check_time
        seconds_until_next = max(0, self.check_interval - elapsed)

        return {
            'check_interval': self.check_interval,
            'last_check_time': self.last_check_time,
            'seconds_until_next_check': seconds_until_next,
            'total_checks': self.total_checks,
            'cycle_changes_detected': self.cycle_changes_detected,
            'reload_successes': self.reload_successes,
            'reload_failures': self.reload_failures
        }

    def reset(self):
        """Reset cycle manager (resets check timer and statistics)."""
        self.last_check_time = time.time()
        self.total_checks = 0
        self.cycle_changes_detected = 0
        self.reload_successes = 0
        self.reload_failures = 0
