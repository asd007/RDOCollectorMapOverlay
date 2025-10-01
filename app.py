#!/usr/bin/env python3
"""
RDO Map Overlay - Main Application
Pixel-perfect collectible tracking overlay for Red Dead Online
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import SERVER, CACHE_PATHS
from core import CoordinateTransform, MapLoader, CollectiblesLoader
from matching import CascadeMatcher, PyramidBuilder
from api import OverlayState, create_app


def initialize_system():
    """Initialize the overlay system"""
    print("="*60)
    print("RDO Map Overlay - Pixel-Perfect Precision Edition")
    print("="*60)
    
    state = OverlayState()
    
    try:
        # Initialize coordinate transform
        print("Initializing coordinate system...")
        state.coord_transform = CoordinateTransform()
        
        # Load map
        print("Loading map...")
        state.full_map = MapLoader.load_map()
        if state.full_map is None:
            print("ERROR: Failed to load map!")
            return None
        
        h, w = state.full_map.shape
        print(f"Map loaded: {w}x{h}")
        
        # Load or build feature pyramids
        print("Loading feature pyramids...")
        state.pyramids = PyramidBuilder.load_pyramids(state.full_map.shape)
        
        if state.pyramids is None:
            print("Building feature pyramids...")
            state.pyramids = PyramidBuilder.build_pyramids(state.full_map)
            PyramidBuilder.save_pyramids(state.pyramids)
        
        # Initialize matcher
        print("Initializing cascade matcher...")
        state.cascade_matcher = CascadeMatcher()
        
        # Load collectibles
        print("Loading collectibles...")
        collectibles = CollectiblesLoader.load(state.coord_transform)
        state.set_collectibles(collectibles)
        
        state.is_initialized = True
        
        print("\n" + "="*60)
        print("System Ready!")
        print("="*60)
        print(f"  Collectibles loaded: {len(state.collectibles)}")
        print(f"  Pyramid scales: {list(state.pyramids.keys())}")
        print(f"  Precision mode: PIXEL-PERFECT")
        print(f"  Target performance: <100ms")
        print("="*60)
        
        return state
        
    except Exception as e:
        print(f"\nInitialization failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main application entry point"""
    state = initialize_system()
    
    if state is None:
        print("\nFailed to initialize system. Exiting.")
        sys.exit(1)
    
    # Create Flask app
    app = create_app(state)
    
    # Start server
    print(f"\nStarting server on http://{SERVER.HOST}:{SERVER.PORT}")
    print("Press Ctrl+C to stop\n")
    
    app.run(
        host=SERVER.HOST,
        port=SERVER.PORT,
        debug=SERVER.DEBUG
    )


if __name__ == '__main__':
    main()
