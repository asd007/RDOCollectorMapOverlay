"""
Unit tests for collectibles_filter pure function.
"""

import pytest
from core.collectibles.collectibles_filter import filter_visible_collectibles
from tests.conftest import MockCollectible


class TestCollectiblesFilterBasic:
    """Test basic collectible filtering."""

    def test_empty_collectibles(self):
        """Test with no collectibles."""
        result = filter_visible_collectibles(
            all_collectibles=[],
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500
        )
        assert result == []

    def test_single_collectible_in_viewport(self):
        """Test single collectible within viewport."""
        collectible = MockCollectible(
            x=6000,  # In detection space
            y=4500,
            type='card_tarot',
            name='The Fool',
            category='tarot_cards'
        )

        result = filter_visible_collectibles(
            all_collectibles=[collectible],
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500,
            screen_width=1920,
            screen_height=1080
        )

        assert len(result) == 1
        assert result[0]['type'] == 'card_tarot'
        assert result[0]['name'] == 'The Fool'
        assert result[0]['category'] == 'tarot_cards'

    def test_collectible_outside_viewport(self):
        """Test collectible outside viewport bounds."""
        collectible = MockCollectible(
            x=8000,  # Outside viewport (5000-7000)
            y=4500,
            type='card_tarot',
            name='The Fool',
            category='tarot_cards'
        )

        result = filter_visible_collectibles(
            all_collectibles=[collectible],
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500
        )

        assert len(result) == 0


class TestCollectiblesFilterCoordinateTransform:
    """Test coordinate transformation from detection space to screen space."""

    def test_coordinate_transformation(self):
        """Test that coordinates are transformed correctly."""
        # Collectible at center of viewport
        collectible = MockCollectible(
            x=6000,  # Center X of viewport (5000-7000)
            y=4750,  # Center Y of viewport (4000-5500)
            type='card_tarot',
            name='Center Card',
            category='tarot_cards'
        )

        result = filter_visible_collectibles(
            all_collectibles=[collectible],
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500,
            screen_width=1920,
            screen_height=1080
        )

        assert len(result) == 1

        # Center of viewport should map to center of screen
        # x: (6000 - 5000) / 2000 * 1920 = 1000 / 2000 * 1920 = 960
        # y: (4750 - 4000) / 1500 * 1080 = 750 / 1500 * 1080 = 540
        assert result[0]['x'] == 960
        assert result[0]['y'] == 540

    def test_top_left_corner(self):
        """Test collectible at top-left corner of viewport."""
        collectible = MockCollectible(
            x=5000,  # Left edge
            y=4000,  # Top edge
            type='card_tarot',
            name='Corner Card',
            category='tarot_cards'
        )

        result = filter_visible_collectibles(
            all_collectibles=[collectible],
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500,
            screen_width=1920,
            screen_height=1080
        )

        assert len(result) == 1
        # Top-left should map to (0, 0)
        assert result[0]['x'] == 0
        assert result[0]['y'] == 0

    def test_bottom_right_corner(self):
        """Test collectible at bottom-right corner of viewport."""
        collectible = MockCollectible(
            x=7000,  # Right edge (5000 + 2000)
            y=5500,  # Bottom edge (4000 + 1500)
            type='card_tarot',
            name='Corner Card',
            category='tarot_cards'
        )

        result = filter_visible_collectibles(
            all_collectibles=[collectible],
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500,
            screen_width=1920,
            screen_height=1080
        )

        assert len(result) == 1
        # Bottom-right should map to (1920, 1080)
        assert result[0]['x'] == 1920
        assert result[0]['y'] == 1080


class TestCollectiblesFilterCategoryVisibility:
    """Test category visibility filtering."""

    def test_category_filter_default(self):
        """Test default behavior (all categories visible)."""
        collectibles = [
            MockCollectible(x=6000, y=4500, type='card_tarot', name='Card 1', category='tarot_cards'),
            MockCollectible(x=6100, y=4500, type='egg', name='Egg 1', category='eggs'),
            MockCollectible(x=6200, y=4500, type='flower', name='Flower 1', category='flowers')
        ]

        result = filter_visible_collectibles(
            all_collectibles=collectibles,
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500
        )

        assert len(result) == 3

    def test_category_filter_custom(self):
        """Test custom category visibility function."""
        collectibles = [
            MockCollectible(x=6000, y=4500, type='card_tarot', name='Card 1', category='tarot_cards'),
            MockCollectible(x=6100, y=4500, type='egg', name='Egg 1', category='eggs'),
            MockCollectible(x=6200, y=4500, type='flower', name='Flower 1', category='flowers')
        ]

        # Only show tarot cards
        def is_visible(category):
            return category == 'tarot_cards'

        result = filter_visible_collectibles(
            all_collectibles=collectibles,
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500,
            is_category_visible=is_visible
        )

        assert len(result) == 1
        assert result[0]['category'] == 'tarot_cards'

    def test_category_filter_hide_all(self):
        """Test hiding all categories."""
        collectibles = [
            MockCollectible(x=6000, y=4500, type='card_tarot', name='Card 1', category='tarot_cards'),
            MockCollectible(x=6100, y=4500, type='egg', name='Egg 1', category='eggs')
        ]

        def is_visible(category):
            return False

        result = filter_visible_collectibles(
            all_collectibles=collectibles,
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500,
            is_category_visible=is_visible
        )

        assert len(result) == 0


class TestCollectiblesFilterCollectionState:
    """Test collection state filtering."""

    def test_collection_state_default(self):
        """Test default behavior (nothing collected)."""
        collectible = MockCollectible(
            x=6000,
            y=4500,
            type='card_tarot',
            name='The Fool',
            category='tarot_cards'
        )

        result = filter_visible_collectibles(
            all_collectibles=[collectible],
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500
        )

        assert len(result) == 1
        assert result[0]['collected'] is False

    def test_collection_state_custom(self):
        """Test custom collection state function."""
        collectibles = [
            MockCollectible(x=6000, y=4500, type='card_tarot', name='The Fool', category='tarot_cards'),
            MockCollectible(x=6100, y=4500, type='card_tarot', name='The Magician', category='tarot_cards')
        ]

        # Mark "The Fool" as collected
        def is_collected(category, name):
            return name == 'The Fool'

        result = filter_visible_collectibles(
            all_collectibles=collectibles,
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500,
            is_collected=is_collected
        )

        assert len(result) == 2
        assert result[0]['collected'] is True  # The Fool
        assert result[1]['collected'] is False  # The Magician


class TestCollectiblesFilterMetadata:
    """Test metadata inclusion in results."""

    def test_basic_metadata(self):
        """Test that basic metadata is included."""
        collectible = MockCollectible(
            x=6000,
            y=4500,
            type='card_tarot',
            name='The Fool',
            category='tarot_cards',
            help='Found on a barrel',
            video='https://example.com/video'
        )

        result = filter_visible_collectibles(
            all_collectibles=[collectible],
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500
        )

        assert len(result) == 1
        assert result[0]['type'] == 'card_tarot'
        assert result[0]['name'] == 'The Fool'
        assert result[0]['category'] == 'tarot_cards'
        assert result[0]['help'] == 'Found on a barrel'
        assert result[0]['video'] == 'https://example.com/video'

    def test_missing_optional_metadata(self):
        """Test handling of missing optional metadata."""
        collectible = MockCollectible(
            x=6000,
            y=4500,
            type='card_tarot',
            name='The Fool',
            category='tarot_cards'
        )

        result = filter_visible_collectibles(
            all_collectibles=[collectible],
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500
        )

        assert len(result) == 1
        assert result[0]['help'] == ''
        assert result[0]['video'] == ''


class TestCollectiblesFilterPureFunctionProperties:
    """Test pure function properties (no side effects, deterministic)."""

    def test_no_mutation_of_input(self):
        """Test that input collectibles are not mutated."""
        collectibles = [
            MockCollectible(x=6000, y=4500, type='card_tarot', name='Card 1', category='tarot_cards')
        ]

        original_x = collectibles[0].x
        original_y = collectibles[0].y

        filter_visible_collectibles(
            all_collectibles=collectibles,
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500
        )

        # Original collectibles should be unchanged
        assert collectibles[0].x == original_x
        assert collectibles[0].y == original_y

    def test_deterministic_output(self):
        """Test that same inputs produce same outputs."""
        collectibles = [
            MockCollectible(x=6000, y=4500, type='card_tarot', name='Card 1', category='tarot_cards'),
            MockCollectible(x=6100, y=4600, type='egg', name='Egg 1', category='eggs')
        ]

        result1 = filter_visible_collectibles(
            all_collectibles=collectibles,
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500
        )

        result2 = filter_visible_collectibles(
            all_collectibles=collectibles,
            viewport_x=5000,
            viewport_y=4000,
            viewport_width=2000,
            viewport_height=1500
        )

        # Results should be identical
        assert len(result1) == len(result2)
        for r1, r2 in zip(result1, result2):
            assert r1 == r2
