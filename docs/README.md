# Documentation

This folder contains documentation and assets for the RDO Map Overlay project.

## Contents

### `/images`
Screenshots and visual assets used in documentation.

**Current images:**
- `overlay-example.png` - Example screenshot showing the overlay with collectibles displayed on the in-game map

## Main Documentation

- **[Main README](../README.md)** - User-facing documentation, installation guide, features, and usage
- **[CLAUDE.md](../CLAUDE.md)** - Developer documentation for Claude Code, includes architecture, workflow, and implementation details
- **[LICENSE.txt](../LICENSE.txt)** - Project license and third-party attributions

## Build Documentation

Build and installer documentation is located in:
- **[.build/installer/README.md](../.build/installer/README.md)** - NSIS installer architecture and build process
- **[.build/launcher/README.md](../.build/launcher/README.md)** - Launcher batch file documentation
- **[.build/scripts/README.md](../.build/scripts/README.md)** - Build scripts documentation

## Testing Documentation

Test data and documentation:
- **[tests/data/](../tests/data/)** - Real gameplay test cases with screenshots and metadata
- **[tests/README.md](../tests/README.md)** - Testing framework documentation (if exists)

## Adding Documentation

When adding new documentation:

1. **User-facing documentation** → Update main [README.md](../README.md)
2. **Developer documentation** → Update [CLAUDE.md](../CLAUDE.md)
3. **Visual assets** → Add to `docs/images/` and reference from relevant docs
4. **Build/deployment docs** → Add to `.build/` subdirectories
5. **Test documentation** → Add to `tests/` directory

Keep documentation close to the code it describes.
