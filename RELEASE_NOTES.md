# Release Notes

## [1.0.0] - TBD

### Initial Release

First public release of RDO Map Overlay with full feature set.

#### Features

**Core Functionality:**
- Automatic map position detection using computer vision (AKAZE features)
- Real-time collectible tracking with 5fps continuous capture
- Integration with Joan Ropke's Collectors Map API for daily cycles
- Transparent overlay window with zero-configuration setup

**Computer Vision:**
- Multi-scale cascade matcher (25% → 50% → 70%) for speed/accuracy balance
- Custom image preprocessing pipeline (posterization + CLAHE + custom LUT)
- Spatial distribution validation for robust inlier selection
- Windows Graphics Capture API for clean game capture

**User Experience:**
- One-click installer (no Python/Node.js required)
- Hotkey controls (F9/F8/F7/F6/Ctrl+Q)
- Interactive collectible markers with hover tooltips
- Right-click menu to mark collectibles as collected
- Adjustable opacity levels (30%/50%/70%/90%)
- Status bar with connection state, FPS, and match quality

**Performance:**
- ~200ms median matching time
- 0.0px position error on real gameplay tests
- 100% success rate on validation suite
- ~500MB RAM usage, ~5-10% CPU

**Developer Features:**
- Comprehensive test suite (synthetic + real gameplay)
- GitHub Actions CI/CD with automated testing
- Dynamic port allocation (no hardcoded port 5000)
- Embedded backend (PyInstaller) + frontend (Electron) packaging
- Git LFS for large map file management

#### Technical Details

**Backend:**
- Python 3.10+ with OpenCV
- Flask + Flask-SocketIO for REST API + WebSocket push updates
- AKAZE binary descriptors with BFMatcher (faster than FLANN)
- Cascade scale matching with confidence thresholds

**Frontend:**
- Electron 27 with HTML5 Canvas rendering
- Socket.IO client for real-time viewport/collectible updates
- Dynamic backend port discovery via IPC

**Testing:**
- 15 synthetic test cases (100% pass, 1.08px mean error)
- 9 real gameplay test cases (100% pass, 0.0px error)
- Automated CI validation on pull requests

#### Known Issues

- **Resolution Limitation**: Currently supports 1920×1080 resolution only
- **Windowed Mode Required**: Overlay requires Windowed Fullscreen mode (not Exclusive Fullscreen)
- **Interior Matching**: F9 sync may fail in dense interior areas (use open world locations)
- **Single Monitor**: Designed for single monitor setups (primary monitor)

#### Installation

Download `RDO-Map-Overlay-Setup.exe` from [Releases](https://github.com/asd007/RDOCollectorMapOverlay/releases) and run the installer.

**Requirements:**
- Windows 10/11 (64-bit)
- Red Dead Online
- 4GB RAM minimum
- Internet connection (for collectible data)

#### Contributors

- alexandru.clontea - Initial implementation

#### Credits

- HQ Map: RDR2 HQ Map from Nexus Mods
- Collectible data: [Jean Ropke's RDR2 Collectors Map](https://jeanropke.github.io/RDR2CollectorsMap/)
- Computer vision: OpenCV Project

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

_This project is not affiliated with Rockstar Games or Take-Two Interactive._
