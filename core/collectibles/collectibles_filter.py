"""
Filter collectibles by viewport visibility and collection state.
Pure functions - no state, no threads.
"""

from typing import List, Dict, Callable


def filter_visible_collectibles(
    all_collectibles: List,
    viewport_x: float,
    viewport_y: float,
    viewport_width: float,
    viewport_height: float,
    screen_width: int = 1920,
    screen_height: int = 1080,
    is_category_visible: Callable[[str], bool] = lambda cat: True,
    is_collected: Callable[[str, str], bool] = lambda cat, name: False
) -> List[Dict]:
    """
    Filter collectibles visible in current viewport and transform to screen coordinates.

    Pure function - no side effects, safe to call from any thread.

    Args:
        all_collectibles: All collectibles in detection space
        viewport_x: Viewport left edge in detection space
        viewport_y: Viewport top edge in detection space
        viewport_width: Viewport width in detection space
        viewport_height: Viewport height in detection space
        screen_width: Output screen width (default: 1920)
        screen_height: Output screen height (default: 1080)
        is_category_visible: Function to check if category should be shown
        is_collected: Function to check if collectible is collected

    Returns:
        List of dicts with screen coordinates + metadata:
        - x, y: Screen coordinates
        - type: Collectible type
        - name: Collectible name
        - category: Collection category
        - help: Help text (if available)
        - video: Video URL (if available)
        - collected: Collection state
    """
    visible = []

    # Calculate screen transform
    scale_x = screen_width / viewport_width
    scale_y = screen_height / viewport_height

    for col in all_collectibles:
        # Check if in viewport bounds (detection space)
        if not (viewport_x <= col.x <= viewport_x + viewport_width and
                viewport_y <= col.y <= viewport_y + viewport_height):
            continue

        # Check category visibility (tracker filter)
        if not is_category_visible(col.category):
            continue

        # Transform to screen coordinates
        screen_x = int((col.x - viewport_x) * scale_x)
        screen_y = int((col.y - viewport_y) * scale_y)

        # Build result dict
        item = {
            'x': screen_x,
            'y': screen_y,
            'type': col.type,
            'name': col.name,
            'category': col.category,
            'help': col.help if hasattr(col, 'help') else '',
            'video': col.video if hasattr(col, 'video') else '',
            'collected': is_collected(col.category, col.name)
        }

        visible.append(item)

    return visible
