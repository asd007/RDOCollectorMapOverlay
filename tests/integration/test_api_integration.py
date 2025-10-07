"""
Integration tests for Flask API endpoints.

Tests the complete API workflow including server lifecycle, endpoint responses,
and integration with backend services.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import time
import threading
import requests
from flask import Flask

from api.routes import create_app
from core.state.application_state import ApplicationState


class TestAPIIntegration:
    """Integration tests for Flask API."""

    @pytest.fixture
    def app_state(self):
        """Create application state."""
        state = ApplicationState()
        yield state
        # Cleanup
        if hasattr(state, 'capture_service') and state.capture_service:
            state.capture_service.stop()

    @pytest.fixture
    def app(self, app_state):
        """Create Flask app for testing."""
        app, _ = create_app(app_state)  # Returns (app, None) tuple
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    def test_status_endpoint(self, client):
        """Test /status endpoint returns correct structure."""
        response = client.get('/status')
        assert response.status_code == 200

        data = response.get_json()
        assert 'ready' in data
        assert 'collectibles_loaded' in data
        assert 'total_collectibles' in data
        assert isinstance(data['total_collectibles'], int)

    def test_stats_endpoint(self, client):
        """Test /stats endpoint returns performance metrics."""
        response = client.get('/stats')
        assert response.status_code == 200

        data = response.get_json()
        # Should contain timing and FPS metrics
        assert 'backend_fps' in data or 'message' in data

    @pytest.mark.requires_network
    def test_refresh_data_endpoint(self, client):
        """Test /refresh-data reloads collectibles from API."""
        response = client.post('/refresh-data')
        assert response.status_code in [200, 500]  # May fail if API unavailable

        data = response.get_json()
        assert 'message' in data

        if response.status_code == 200:
            assert 'collectibles' in data or 'reloaded' in data['message'].lower()

    def test_reset_tracking_endpoint(self, client):
        """Test /reset-tracking clears matcher state."""
        response = client.post('/reset-tracking')
        assert response.status_code == 200

        data = response.get_json()
        assert 'message' in data
        assert 'reset' in data['message'].lower()

    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.get('/status')
        assert 'Access-Control-Allow-Origin' in response.headers

    def test_invalid_endpoint(self, client):
        """Test invalid endpoint returns 404."""
        response = client.get('/invalid-endpoint-that-does-not-exist')
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Test POST on GET-only endpoint returns 405."""
        response = client.post('/status')
        assert response.status_code == 405


class TestAPIServerLifecycle:
    """Test Flask server startup and shutdown."""

    @pytest.mark.slow
    def test_concurrent_requests(self):
        """Test server handles concurrent requests."""
        from api.routes import create_app
        from core.state.application_state import ApplicationState

        state = ApplicationState()
        flask_app, _ = create_app(state)  # Returns (app, None) tuple
        client = flask_app.test_client()

        def make_request():
            return client.get('/status')

        # Make multiple concurrent requests
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]

        # All requests should succeed
        assert all(r.status_code == 200 for r in results)


class TestAPIErrorHandling:
    """Test API error handling and edge cases."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from api.routes import create_app
        from core.state.application_state import ApplicationState

        state = ApplicationState()
        flask_app, _ = create_app(state)  # Returns (app, None) tuple
        flask_app.config['TESTING'] = True
        return flask_app.test_client()

    def test_malformed_json(self, client):
        """Test handling of malformed JSON in POST request."""
        response = client.post(
            '/align-with-screenshot',
            data='not valid json',
            content_type='application/json'
        )
        # Should handle gracefully (400 or 500)
        assert response.status_code in [400, 415, 500]

    def test_large_payload(self, client):
        """Test handling of large JSON payload."""
        large_payload = {'data': 'x' * 10_000_000}  # 10MB
        response = client.post(
            '/reset-tracking',
            json=large_payload
        )
        # Should either accept or reject gracefully
        assert response.status_code in [200, 400, 413, 500]

    def test_timeout_handling(self, client):
        """Test API handles long-running operations."""
        # This test is informational - shows timeout behavior
        import time
        start = time.time()
        response = client.get('/stats', timeout=10)
        duration = time.time() - start

        # Should respond quickly (< 1s for stats)
        assert duration < 1.0
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
