# Release Notes

## [1.0.0] - 2025-01-04

### Fellow Collectors - The Grind Just Got Easier

**The situation:** Madam Nazar wants complete sets. Every day. Coins scattered from Annesburg to Blackwater. Arrowheads buried where God forgot. Tarot Cards hidden in every dusty saloon from here to Tumbleweed. And you? You're squinting at hand-drawn maps, scribbling notes on scraps of paper, trying to remember which creekbed you already checked. Other collectors are out there too, racing you to every site. Your saddlebags are half-full, your patience worn thin.

**The solution:** One map. Your map. Press **M** and see every collectible Madam Nazar's after, marked clear as day. Pan around the frontier, plan your route, mark what you've already collected. No more juggling papers, no more wondering if that's today's locations or last week's. Just ride out and collect.

**What this does:** Marks today's collectibles right on your in-game map. Open your map, see the locations, plan your route. Simple as that.

---

**Breaking character for a second:** Those "hand-drawn maps" and "scribbled notes"? That's **[Jean Ropke's RDR2 Collectors Map](https://jeanropke.github.io/RDR2CollectorsMap/)**, and it's the foundation this entire overlay is built on. Jean has been maintaining accurate daily cycle data, collectible locations, and video guides for YEARS, completely free. This tool wouldn't exist without that work. All this overlay does is bring Jean's data into your in-game map so you don't have to alt-tab.

---

### What You Get

**🗺️ Jean Ropke's Map, In Your Game Map**
- All of today's active collectibles from [Jean Ropke's legendary map](https://jeanropke.github.io/RDR2CollectorsMap/) overlaid on your in-game map (press M)
- Daily cycle updates automatically (today's spawns, not yesterday's)
- Auto-tracking: Pan and zoom your map - overlay markers stay synced to the map view

**✨ Actually Useful Features**
- **Hover tooltips**: See what you're collecting without clicking
- **Video guides**: Click play button to watch "where the hell is this arrowhead" videos
- **Collection tracking**: Right-click to mark collected, remembers between sessions
- **Smart opacity**: F7 cycles through transparencies, F8 hides completely
- **Click-through**: All clicks go to game (except when video player is open)

**💪 Built For Collectors**
- Single-monitor friendly (finally!)
- Auto-tracking: Pan your map, overlay updates automatically
- Smooth 5fps position sync (imperceptible while viewing map)
- Works anywhere the in-game map works
- 1920×1080 resolution

### Quick Start

1. Download installer from [Releases](https://github.com/asd007/RDOCollectorMapOverlay/releases)
2. Run it (Windows might warn - click "Run anyway")
3. Launch RDO in Windowed Fullscreen
4. **Press M** to open your in-game map - collectible markers appear overlaid on the map
5. Pan and zoom your map to explore - overlay stays synced
6. Plan your route, close map, go collect, sell complete sets to Madam Nazar, get rich

**Hotkeys:** F8=hide | F7=opacity | F6=refresh data | Ctrl+Q=close

---

### This Is v1.0 - There's Work To Do

This release is **functional and useful**, but not perfect. Map tracking is smooth while viewing. 1920×1080 only right now.

**Feedback is gold.** If something breaks, feels clunky, or you have ideas - open an issue on [GitHub](https://github.com/asd007/RDOCollectorMapOverlay/issues). This tool gets better with your input.

**Known limitations:**
- Resolution: 1920×1080 only
- Window mode: Requires Windowed Fullscreen
- Map view: Works on the full in-game map (M), not minimap or radar
- Performance: ~500MB RAM, ~5-10% CPU (similar to Discord)

---

### Built With
- [OpenCV](https://opencv.org/) - Computer vision magic
- [Electron](https://www.electronjs.org/) - Desktop framework
- [windows-capture](https://github.com/NiiightmareXD/windows-capture) - Game capture
- RDR2 HQ Map (Nexus Mods) - Reference map for matching

**Special Thanks:**
- The RDO collecting community for testing and feedback
- Rockstar Games for creating Red Dead Online

---

### Installation

1. Download `RDO-Map-Overlay-Setup.exe` from [Releases](https://github.com/asd007/RDOCollectorMapOverlay/releases) (~150MB)
2. Run installer (Windows may warn - click "More info" → "Run anyway")
3. First launch: Accept EULA, wait ~30 seconds for setup
4. In-game: Set to Windowed Fullscreen, press **M** to open map - collectible markers appear automatically

**Requirements:** Windows 10/11 (64-bit), 4GB RAM, 1920×1080 resolution, internet connection

**Uninstall:** Windows "Add or Remove Programs"

---

## Development Versions

### Pre-Release Milestones

**v0.9.0** - Performance Optimization
- Implemented cascade scale matcher for 1.5x speed improvement
- Added spatial distribution validation
- Reduced median matching time from 408ms → 177ms

**v0.8.0** - Real Gameplay Testing
- Added test data collector for ground truth capture
- Created real gameplay test suite (9 screenshots)
- Integrated real tests into GitHub Actions CI

**v0.7.0** - Continuous Capture
- Implemented Windows Graphics Capture API integration
- Added background capture service (5fps tracking)
- WebSocket push updates for real-time marker positioning

**v0.6.0** - Image Preprocessing
- Custom preprocessing pipeline (posterization + CLAHE + LUT)
- Terrain edge enhancement for better feature detection
- Optimized resize order (grayscale → resize → posterize)

**v0.5.0** - Coordinate System
- Implemented LatLng ↔ HQ map transforms
- Added collectibles loader with Joan Ropke API
- Viewport coordinate system with screen transforms

**v0.4.0** - Feature Matching
- AKAZE feature detection with binary descriptors
- RANSAC homography estimation
- Ratio test filtering (0.75 threshold)

**v0.3.0** - Electron Overlay
- Transparent overlay window
- Canvas-based rendering
- Hotkey registration (F9/F8/F7/F6)

**v0.2.0** - Flask Backend
- REST API with /align-with-screenshot endpoint
- MSS screenshot capture
- Basic feature matching pipeline

**v0.1.0** - Initial Prototype
- Proof of concept with manual positioning
- Simple collectible display
- Basic map rendering

---

## Future Roadmap

### Planned Features

**v1.1.0** - Multi-Resolution Support
- Dynamic resolution detection
- Support for 2560×1440, 3840×2160
- Adaptive scaling for different aspect ratios

**v1.2.0** - Enhanced Tracking
- ML-based scale prediction for faster matching
- Viewport tracking with Kalman filter
- ROI-based feature matching for speed

**v1.3.0** - Additional Features
- Multiple collectible set support
- Custom marker styles
- Collection progress tracking
- Export collected items list

**v1.4.0** - Performance
- GPU-accelerated feature matching
- Reduced memory footprint
- Sub-100ms matching time target

**v1.5.0** - User Customization
- Configurable hotkeys
- Theme/color customization
- Marker size/opacity settings
- Audio notifications

### Long-Term Goals

- Mac/Linux support (requires alternative to Windows Graphics Capture)
- Multi-monitor support
- Mobile companion app
- Community collectible verification
- Integration with other RDO helper tools

---

## Migration Guides

### Upgrading from Development Builds

If you were using a development build:

1. **Uninstall Development Version**: Remove manually installed Python/Node.js components
2. **Download Release**: Get `RDO-Map-Overlay-Setup.exe` from GitHub Releases
3. **Run Installer**: Follow standard installation process
4. **Settings Migration**: Settings do not carry over (one-time setup)

### Breaking Changes

None (initial release).

---

## Support

**Reporting Issues:**
- GitHub Issues: https://github.com/asd007/RDOCollectorMapOverlay/issues
- Include: OS version, game resolution, steps to reproduce
- Attach: `frontend/renderer.log` and screenshots if applicable

**Feature Requests:**
- GitHub Discussions: https://github.com/asd007/RDOCollectorMapOverlay/discussions
- Explain use case and expected behavior

**Contributing:**
- Fork repository and create feature branch
- Follow coding standards in README.md
- Include tests and documentation
- Submit pull request with description

---

---

## Legal Disclaimer

This project is **not affiliated with, endorsed by, or sponsored by Rockstar Games or Take-Two Interactive.**

**Use at your own risk.** This tool operates using screen capture technology and does not read game memory, inject code, or modify game files. However, Rockstar Games reserves the right to restrict accounts using third-party tools.

The developers of this tool are not responsible for any consequences resulting from its use, including but not limited to account restrictions or bans.

See [README.md - Safety & Legal](README.md#safety--legal) for detailed information.
