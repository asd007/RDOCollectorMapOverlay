# Folder Structure Review & Recommendations

> **Windows Development Environment**: This project is developed and deployed on Windows. All scripts and commands use PowerShell. CI/CD pipelines run on `windows-latest`.

## Current Structure Analysis

### Strengths ✅

1. **Clear domain separation**: `core/`, `matching/`, `models/`, `api/`, `qml/`
2. **Configuration centralized**: `config/` directory
3. **Documentation exists**: `docs/` with architecture docs
4. **Data isolation**: `data/` for map files and cache

### Issues Identified ❌

1. **Tests are flat and mixed**
   - All test files in single `tests/` directory
   - No separation of unit/integration/e2e tests
   - Test utilities mixed with actual tests
   - No fixtures organization
   - Some test files in root (`test_scenegraph_texture.py`)

2. **QML organization**
   - Python and QML files mixed in `qml/`
   - Multiple test/experimental QML files cluttering directory
   - Renderers subdirectory exists but inconsistent usage

3. **Root directory clutter**
   - Application entry points (`app.py`, `app_qml.py`) in root
   - Test files in root
   - No `src/` directory

4. **Unclear purposes**
   - `analysis/`, `debug/`, `visualizations/` - Dev tools vs production?
   - `tools/`, `utils/` - Empty or minimal content?
   - `scenegraph_customgeometry/` - Experimental code?

5. **Build artifacts mixed**
   - `.build/`, `build/`, `dist/` at root level
   - Not clearly separated from source

6. **Missing test infrastructure**
   - No `conftest.py` for pytest fixtures
   - No test utilities/helpers directory
   - No mock/stub organization
   - No test data fixtures directory

---

## Recommended Structure

```
rdo_overlay/
├── README.md
├── LICENSE.txt
├── pyproject.toml              # Modern Python packaging
├── setup.py                    # Backwards compatibility
├── requirements.txt
├── requirements-dev.txt        # NEW: Dev dependencies (pytest, etc.)
├── .gitignore
├── .env.example               # NEW: Environment variables template
│
├── src/                       # NEW: All production source code
│   ├── rdo_overlay/           # Main package
│   │   ├── __init__.py
│   │   ├── __main__.py        # Entry point (python -m rdo_overlay)
│   │   │
│   │   ├── core/              # Core business logic
│   │   │   ├── __init__.py
│   │   │   ├── application_state.py
│   │   │   ├── collectibles_filter.py
│   │   │   ├── collectibles_loader.py
│   │   │   ├── collection_tracker.py
│   │   │   ├── continuous_capture.py
│   │   │   ├── coordinate_transform.py
│   │   │   ├── performance_monitor.py
│   │   │   ├── metrics.py
│   │   │   ├── click_observer.py
│   │   │   ├── game_focus_manager.py
│   │   │   └── map_detector.py
│   │   │
│   │   ├── matching/          # Computer vision matching
│   │   │   ├── __init__.py
│   │   │   ├── cascade_scale_matcher.py
│   │   │   ├── simple_matcher.py
│   │   │   ├── translation_tracker.py
│   │   │   ├── viewport_tracker.py
│   │   │   ├── spatial_keypoint_index.py
│   │   │   └── spatial_feature_selector.py
│   │   │
│   │   ├── preprocessing/     # NEW: Image processing utilities
│   │   │   ├── __init__.py
│   │   │   ├── image_preprocessing.py
│   │   │   ├── frame_deduplicator.py
│   │   │   ├── feature_cache.py
│   │   │   └── map_loader.py
│   │   │
│   │   ├── models/            # Data models
│   │   │   ├── __init__.py
│   │   │   └── collectible.py
│   │   │
│   │   ├── api/               # HTTP API (Flask)
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   │
│   │   ├── ui/                # NEW: Renamed from qml/
│   │   │   ├── __init__.py
│   │   │   │
│   │   │   ├── python/        # Python QML backends
│   │   │   │   ├── __init__.py
│   │   │   │   ├── overlay_backend.py
│   │   │   │   ├── click_through_manager.py
│   │   │   │   ├── collectible_renderer.py
│   │   │   │   └── svg_icons.py
│   │   │   │
│   │   │   ├── qml/           # QML UI files
│   │   │   │   ├── Overlay.qml
│   │   │   │   ├── CollectibleTooltip.qml
│   │   │   │   ├── CollectionTracker.qml
│   │   │   │   ├── StatusPill.qml
│   │   │   │   ├── FPSCounter.qml
│   │   │   │   ├── VideoPlayer.qml
│   │   │   │   └── components/
│   │   │   │       ├── CollectibleIcon.qml
│   │   │   │       └── CollectionSetItem.qml
│   │   │   │
│   │   │   ├── renderers/     # Rendering implementations
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sprite_atlas.py
│   │   │   │   └── scenegraph/
│   │   │   │       ├── __init__.py
│   │   │   │       └── collectible_renderer_scenegraph.py
│   │   │   │
│   │   │   └── theme/         # Styling
│   │   │       └── Theme.qml
│   │   │
│   │   ├── config/            # Configuration
│   │   │   ├── __init__.py
│   │   │   ├── settings.py
│   │   │   └── paths.py
│   │   │
│   │   └── utils/             # Shared utilities
│   │       ├── __init__.py
│   │       ├── port_manager.py
│   │       └── map_downloader.py
│   │
├── tests/                     # All test code
│   ├── __init__.py            # Make tests importable
│   ├── conftest.py            # Pytest configuration & global fixtures
│   │
│   ├── unit/                  # Unit tests (isolated, fast)
│   │   ├── __init__.py
│   │   ├── conftest.py        # Unit test fixtures
│   │   │
│   │   ├── core/
│   │   │   ├── test_application_state.py
│   │   │   ├── test_collectibles_filter.py
│   │   │   ├── test_performance_monitor.py
│   │   │   ├── test_metrics.py
│   │   │   └── test_coordinate_transform.py
│   │   │
│   │   ├── matching/
│   │   │   ├── test_simple_matcher.py
│   │   │   ├── test_translation_tracker.py
│   │   │   ├── test_viewport_tracker.py
│   │   │   └── test_spatial_keypoint_index.py
│   │   │
│   │   ├── preprocessing/
│   │   │   ├── test_frame_deduplicator.py
│   │   │   ├── test_feature_cache.py
│   │   │   └── test_image_preprocessing.py
│   │   │
│   │   └── models/
│   │       └── test_collectible.py
│   │
│   ├── integration/           # Integration tests (multiple components)
│   │   ├── __init__.py
│   │   ├── conftest.py        # Integration test fixtures
│   │   │
│   │   ├── test_cascade_matcher.py
│   │   ├── test_cascade_integration.py
│   │   ├── test_continuous_capture.py
│   │   ├── test_collectibles_loading.py
│   │   └── test_api_endpoints.py
│   │
│   ├── e2e/                   # End-to-end tests (full system)
│   │   ├── __init__.py
│   │   ├── conftest.py        # E2E fixtures (app setup, teardown)
│   │   │
│   │   ├── test_overlay_startup.py
│   │   ├── test_matching_pipeline.py
│   │   ├── test_collection_tracking.py
│   │   └── test_hotkey_interactions.py
│   │
│   ├── performance/           # Performance/benchmark tests
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   │
│   │   ├── test_matching_performance.py
│   │   ├── test_rendering_performance.py
│   │   └── benchmark_cascade_scales.py
│   │
│   ├── fixtures/              # Shared test fixtures & data
│   │   ├── __init__.py
│   │   ├── screenshots/       # Test screenshot images
│   │   ├── maps/              # Test map data
│   │   ├── collectibles/      # Test collectible data
│   │   └── synthetic/         # Synthetic test data
│   │
│   ├── helpers/               # Test utilities & helpers
│   │   ├── __init__.py
│   │   ├── mock_matcher.py
│   │   ├── mock_capture.py
│   │   ├── test_data_generator.py
│   │   └── assertions.py
│   │
│   ├── real_data/             # Real gameplay data (from test collector)
│   │   ├── screenshots/       # Captured screenshots
│   │   ├── metadata/          # Viewport metadata
│   │   └── test_manifest.json
│   │
│   └── experimental/          # Research & prototyping
│       ├── README.md
│       ├── test_synthetic_movements.py
│       └── synthetic_movement_results/
│
├── data/                      # Application data (not in version control)
│   ├── rdr2_map_hq.png       # Reference map
│   ├── cache/                # Computed caches
│   │   ├── collection_tracker.json
│   │   └── cascade_pyramids_v7.pkl
│   └── logs/                 # Runtime logs
│
├── docs/                      # Documentation
│   ├── README.md
│   ├── ARCHITECTURE.md        # NEW: High-level architecture overview
│   ├── CLAUDE.md              # Developer guide for Claude Code
│   ├── THREADING.md
│   ├── REFACTORING_ROADMAP.md
│   ├── CONTINUOUS_CAPTURE_REFACTOR.md
│   ├── TESTING.md             # NEW: Testing guide
│   ├── CONTRIBUTING.md        # NEW: Contribution guidelines
│   ├── API.md                 # NEW: API documentation
│   ├── images/
│   └── ui-mockups/
│
├── scripts/                   # Development scripts (PowerShell for Windows)
│   ├── setup.ps1             # Setup script for dev environment
│   ├── run_tests.ps1         # Run test suite
│   ├── format_code.ps1       # Code formatting (black, isort)
│   ├── lint.ps1              # Linting (flake8, mypy)
│   └── build.ps1             # Build script
│
├── tools/                     # Development tools
│   ├── test_data_collector.py
│   ├── visualize_features.py
│   └── benchmark_matchers.py
│
├── .build/                    # Build configuration
│   ├── installer/
│   └── launcher/
│
├── build/                     # Build outputs (gitignored)
├── dist/                      # Distribution outputs (gitignored)
│
└── .github/
    └── workflows/
        ├── test.yml          # CI: Run tests
        ├── lint.yml          # CI: Linting
        └── build.yml         # CI: Build & package
```

---

## Migration Plan

### Phase 1: Test Reorganization (Priority: HIGH)

**Goal**: Separate unit/integration/e2e tests for clarity and selective execution

**Steps:**

1. **Create test structure** (PowerShell):
   ```powershell
   # Create test directories
   New-Item -ItemType Directory -Force -Path tests\unit\core
   New-Item -ItemType Directory -Force -Path tests\unit\matching
   New-Item -ItemType Directory -Force -Path tests\unit\preprocessing
   New-Item -ItemType Directory -Force -Path tests\unit\models
   New-Item -ItemType Directory -Force -Path tests\integration
   New-Item -ItemType Directory -Force -Path tests\e2e
   New-Item -ItemType Directory -Force -Path tests\performance
   New-Item -ItemType Directory -Force -Path tests\fixtures
   New-Item -ItemType Directory -Force -Path tests\helpers
   New-Item -ItemType Directory -Force -Path tests\real_data
   ```

2. **Create conftest.py files**:
   ```python
   # tests/conftest.py
   import pytest
   import sys
   from pathlib import Path

   # Add src to path
   sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

   @pytest.fixture
   def test_data_dir():
       return Path(__file__).parent / "fixtures"

   @pytest.fixture
   def real_data_dir():
       return Path(__file__).parent / "real_data"
   ```

3. **Move existing tests**:
   - `test_matching.py` → `tests/unit/matching/test_simple_matcher.py`
   - `test_cascade_matcher.py` → `tests/integration/test_cascade_matcher.py`
   - `test_translation_tracker.py` → `tests/unit/matching/test_translation_tracker.py`
   - `test_cascade_integration.py` → `tests/integration/test_cascade_integration.py`
   - `test_windows_capture.py` → `tests/integration/test_windows_capture.py`
   - `run_real_tests.py` → `tests/e2e/test_real_gameplay.py`
   - `test_data_collector.py` → `tools/test_data_collector.py`

4. **Move test data**:
   - `tests/synthetic_movement_results/` → `tests/experimental/synthetic_movement_results/`
   - Real gameplay data already in good location

5. **Create test helpers**:
   ```python
   # tests/helpers/mock_matcher.py
   class MockMatcher:
       def match(self, screenshot):
           # Return predictable results for testing
           pass

   # tests/helpers/test_data_generator.py
   def generate_test_screenshot(width, height):
       # Generate synthetic test images
       pass
   ```

6. **Update pytest.ini**:
   ```ini
   [pytest]
   testpaths = tests
   python_files = test_*.py
   python_classes = Test*
   python_functions = test_*

   # Markers for test types
   markers =
       unit: Unit tests (fast, isolated)
       integration: Integration tests (multiple components)
       e2e: End-to-end tests (full system)
       performance: Performance benchmarks
       slow: Tests that take >1s
   ```

7. **Run tests selectively**:
   ```bash
   pytest tests/unit                    # Fast unit tests only
   pytest tests/integration             # Integration tests
   pytest tests/e2e                     # E2E tests
   pytest -m "not slow"                 # Skip slow tests
   pytest -m unit                       # Run by marker
   ```

---

### Phase 2: Source Code Reorganization (Priority: MEDIUM)

**Goal**: Move all source to `src/` for cleaner packaging

**Steps:**

1. **Create src structure** (PowerShell):
   ```powershell
   New-Item -ItemType Directory -Force -Path src\rdo_overlay
   ```

2. **Move packages** (PowerShell):
   ```powershell
   Move-Item -Path api,core,matching,models,config -Destination src\rdo_overlay\
   ```

3. **Reorganize qml → ui** (PowerShell):
   ```powershell
   # Create UI structure
   New-Item -ItemType Directory -Force -Path src\rdo_overlay\ui\python
   New-Item -ItemType Directory -Force -Path src\rdo_overlay\ui\qml
   New-Item -ItemType Directory -Force -Path src\rdo_overlay\ui\renderers
   New-Item -ItemType Directory -Force -Path src\rdo_overlay\ui\theme

   # Move Python files
   Move-Item -Path qml\*.py -Destination src\rdo_overlay\ui\python\

   # Move QML files
   Move-Item -Path qml\*.qml -Destination src\rdo_overlay\ui\qml\

   # Move subdirectories
   Move-Item -Path qml\renderers -Destination src\rdo_overlay\ui\
   Move-Item -Path qml\theme -Destination src\rdo_overlay\ui\
   ```

4. **Update entry points**:
   ```python
   # src/rdo_overlay/__main__.py
   from rdo_overlay.app_qml import main

   if __name__ == '__main__':
       main()
   ```

5. **Update imports** throughout codebase:
   ```python
   # Before
   from core import ApplicationState
   from matching import CascadeScaleMatcher

   # After
   from rdo_overlay.core import ApplicationState
   from rdo_overlay.matching import CascadeScaleMatcher
   ```

6. **Update pyproject.toml**:
   ```toml
   [project]
   name = "rdo-overlay"
   version = "0.1.0"

   [project.scripts]
   rdo-overlay = "rdo_overlay.__main__:main"
   ```

---

### Phase 3: Cleanup & Documentation (Priority: LOW)

**Steps:**

1. **Consolidate debug/dev tools** (PowerShell):
   ```powershell
   New-Item -ItemType Directory -Force -Path tools

   # Move files from analysis, debug, visualizations if they exist
   if (Test-Path analysis) { Move-Item -Path analysis\* -Destination tools\ }
   if (Test-Path debug) { Move-Item -Path debug\* -Destination tools\ }
   if (Test-Path visualizations) { Move-Item -Path visualizations\* -Destination tools\ }

   # Remove empty directories
   Remove-Item -Path analysis,debug,visualizations -Force -ErrorAction SilentlyContinue
   ```

3. **Create documentation**:
   - `docs/TESTING.md` - Testing guide
   - `docs/ARCHITECTURE.md` - Architecture overview
   - `docs/CONTRIBUTING.md` - Contribution guidelines
   - `docs/API.md` - API documentation

4. **Update .gitignore**:
   ```gitignore
   # Build
   build/
   dist/
   *.egg-info/

   # Cache
   __pycache__/
   *.pyc
   .pytest_cache/

   # Data
   data/cache/
   data/logs/

   # IDE
   .vscode/
   .idea/
   ```

---

## Testing Best Practices

### 1. Unit Tests

**Characteristics:**
- Test single functions/classes in isolation
- Fast (<10ms per test)
- Use mocks/stubs for dependencies
- No I/O, no network, no Qt

**Example:**
```python
# tests/unit/core/test_collectibles_filter.py
import pytest
from rdo_overlay.core.collectibles_filter import filter_visible_collectibles

def test_filter_visible_collectibles_empty():
    result = filter_visible_collectibles([], 0, 0, 100, 100)
    assert result == []

def test_filter_visible_collectibles_outside_viewport():
    collectibles = [MockCollectible(x=1000, y=1000)]
    result = filter_visible_collectibles(
        collectibles, 0, 0, 100, 100
    )
    assert len(result) == 0
```

### 2. Integration Tests

**Characteristics:**
- Test multiple components working together
- May use real dependencies (files, databases)
- Moderate speed (<1s per test)
- May require setup/teardown

**Example:**
```python
# tests/integration/test_cascade_matcher.py
import pytest
from rdo_overlay.matching import CascadeScaleMatcher
from tests.fixtures import load_test_screenshot

@pytest.fixture
def matcher():
    # Setup matcher with real dependencies
    pass

def test_cascade_matcher_real_screenshot(matcher):
    screenshot = load_test_screenshot("test_001.png")
    result = matcher.match(screenshot)
    assert result['success']
    assert result['confidence'] > 0.7
```

### 3. E2E Tests

**Characteristics:**
- Test full application workflows
- May launch actual application
- Slow (>1s per test)
- Test user-facing behavior

**Example:**
```python
# tests/e2e/test_overlay_startup.py
import pytest
from rdo_overlay.app_qml import main

def test_overlay_launches_successfully(qtbot):
    # Launch overlay
    # Verify window appears
    # Check initial state
    pass
```

### 4. Performance Tests

**Characteristics:**
- Measure speed, memory, FPS
- Establish performance baselines
- Run separately from regular tests

**Example:**
```python
# tests/performance/test_matching_performance.py
import pytest

@pytest.mark.performance
def test_cascade_matcher_speed(benchmark, matcher, screenshot):
    result = benchmark(matcher.match, screenshot)
    assert benchmark.stats['mean'] < 0.1  # <100ms
```

---

## Running Tests

### Command Patterns (PowerShell/CMD)

```powershell
# All tests
pytest

# Unit tests only (fast)
pytest tests\unit

# Integration tests
pytest tests\integration

# E2E tests
pytest tests\e2e

# Performance tests
pytest tests\performance

# By marker
pytest -m unit
pytest -m "not slow"
pytest -m integration

# With coverage (HTML report)
pytest --cov=src\rdo_overlay --cov-report=html

# Parallel execution (requires pytest-xdist)
pytest -n auto

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Re-run failed tests
pytest --lf

# Generate JUnit XML for CI
pytest --junitxml=test-results.xml
```

### PowerShell Test Scripts

Create `scripts/run_tests.ps1`:
```powershell
# Run test suite with appropriate flags
param(
    [string]$TestType = "all",
    [switch]$Coverage,
    [switch]$Parallel
)

$baseArgs = @("-v")

switch ($TestType) {
    "unit" { $baseArgs += "tests\unit" }
    "integration" { $baseArgs += "tests\integration" }
    "e2e" { $baseArgs += "tests\e2e" }
    "performance" { $baseArgs += "tests\performance" }
    "all" { $baseArgs += "tests" }
}

if ($Coverage) {
    $baseArgs += "--cov=src\rdo_overlay"
    $baseArgs += "--cov-report=html"
    $baseArgs += "--cov-report=term"
}

if ($Parallel) {
    $baseArgs += "-n"
    $baseArgs += "auto"
}

Write-Host "Running tests with args: $baseArgs" -ForegroundColor Cyan
pytest @baseArgs
```

Usage:
```powershell
# Run all tests
.\scripts\run_tests.ps1

# Run unit tests with coverage
.\scripts\run_tests.ps1 -TestType unit -Coverage

# Run all tests in parallel
.\scripts\run_tests.ps1 -Parallel

# Run integration tests with coverage and parallel
.\scripts\run_tests.ps1 -TestType integration -Coverage -Parallel
```

### CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run unit tests
        run: pytest tests/unit -v

      - name: Run integration tests
        run: pytest tests/integration -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Benefits of New Structure

### For Development

1. **Clear test organization** - Know where to add tests
2. **Selective test execution** - Run only relevant tests
3. **Better CI/CD** - Parallel test execution by category
4. **Easier debugging** - Isolated test failures

### For Maintenance

1. **Clean imports** - `from rdo_overlay.core import ...`
2. **Package distribution** - `pip install rdo-overlay`
3. **IDE support** - Better autocomplete, navigation
4. **Dependency management** - Clear separation dev/prod deps

### For Contributors

1. **Clear structure** - Easy to understand project layout
2. **Testing guide** - Know how to write tests
3. **Fast feedback** - Run unit tests in seconds
4. **Documentation** - Comprehensive guides

---

## Next Steps

1. ✅ **Review this proposal** with team
2. **Create feature branch** `refactor/folder-structure`
3. **Implement Phase 1** (test reorganization)
4. **Test CI/CD pipeline**
5. **Implement Phase 2** (src/ reorganization) if approved
6. **Update documentation**
7. **Merge to main**

---

## Appendix: Rationale

### Why `src/` Layout?

The `src/` layout (also called "nested" or "import-friendly" layout) has several advantages:

1. **Prevents accidental imports** - Can't import from source directory accidentally
2. **Proper package distribution** - setuptools/pip work correctly
3. **Testing isolation** - Tests import from installed package, not source
4. **Industry standard** - Used by major Python projects

### Why Separate Test Categories?

Different test types have different:

1. **Speed requirements** - Unit tests must be fast
2. **Dependencies** - Integration tests may need external services
3. **Execution frequency** - Unit tests run constantly, E2E less often
4. **CI/CD strategy** - Parallel execution, selective runs
5. **Maintenance burden** - Easier to refactor isolated tests

### Why conftest.py?

pytest's `conftest.py` provides:

1. **Shared fixtures** - Reusable test setup
2. **Plugins** - Custom pytest behavior
3. **Scope control** - Session/module/function fixtures
4. **Cleaner tests** - Less boilerplate in test files
