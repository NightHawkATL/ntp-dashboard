import os
import json
import unittest
from unittest.mock import patch

# Set testing environment variables before importing app
os.environ['APP_VERSION'] = 'test-v1'
os.environ['LOG_LEVEL'] = 'CRITICAL' # Suppress noisy logs during tests

from app import app, encrypt_pwd, decrypt_pwd, get_latest_dockerhub_tag, _update_cache

class TestNTPDashboardApp(unittest.TestCase):
    def setUp(self):
        """Set up a test client before each test."""
        self.app = app.test_client()
        self.app.testing = True

        # Clear the Docker Hub cache before each test
        _update_cache["latest"] = None
        _update_cache["checked"] = 0
        _update_cache["error"] = None

    def test_index_route(self):
        """Test that the main dashboard page loads correctly and includes the version."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        # Ensure our test version string appears somewhere in the rendered HTML
        self.assertIn(b'test-v1', response.data)

    def test_manifest_route(self):
        """Test that the PWA manifest loads successfully."""
        response = self.app.get('/manifest.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response.headers.get('Content-Type', '').lower())

    def test_security_headers(self):
        """Test that caching security headers are rigidly applied to prevent PWA staleness."""
        response = self.app.get('/')
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        self.assertEqual(response.headers.get('Pragma'), 'no-cache')

    def test_encryption_roundtrip(self):
        """Test that the local cryptography suite successfully encrypts and decrypts credentials."""
        secret_password = "my_super_secret_password_123!"
        encrypted = encrypt_pwd(secret_password)
        
        self.assertNotEqual(secret_password, encrypted)
        self.assertTrue(len(encrypted) > 0)
        
        decrypted = decrypt_pwd(encrypted)
        self.assertEqual(secret_password, decrypted)

    @patch('app.requests.get')
    def test_dockerhub_api_check_success(self, mock_get):
        """Test that the backend correctly grabs the newest tag from Docker Hub and ignores 'latest'."""
        # Mock the Docker Hub API response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "results": [
                {"name": "latest"},
                {"name": "v0.1.15"},
                {"name": "v0.1.14"}
            ]
        }
        
        tag, error = get_latest_dockerhub_tag()
        
        self.assertEqual(tag, "v0.1.15")
        self.assertIsNone(error)
        self.assertEqual(_update_cache["latest"], "v0.1.15")  # Verify it cached correctly

    @patch('app.requests.get')
    def test_dockerhub_api_check_no_tags(self, mock_get):
        """Test behavior when Docker Hub returns an empty result set."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"results": []}
        
        tag, error = get_latest_dockerhub_tag()
        
        self.assertIsNone(tag)
        self.assertEqual(error, "No tags found")

    @patch('app.load_config')
    def test_system_metrics_disabled(self, mock_config):
        """Test that system metrics returns 403 when the monitor is disabled in configuration."""
        mock_config.return_value = {"enable_monitor": False}
        response = self.app.get('/api/system_metrics')
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'Resource monitor disabled', response.data)

    @patch('app.load_config')
    @patch('app.run_commands_local')
    def test_system_metrics_enabled_local(self, mock_run_cmd, mock_config):
        """Test that system metrics successfully parses local command outputs when enabled."""
        mock_config.return_value = {"enable_monitor": True, "mode": "local"}
        # Mocking top, free, and thermal outputs
        mock_run_cmd.return_value = ["15.5", "1024 4096", "45000"]
        
        response = self.app.get('/api/system_metrics')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertEqual(data["cpu_percent"], "15.5")
        self.assertEqual(data["ram_used_mb"], 1024)
        self.assertEqual(data["ram_total_mb"], 4096)
        self.assertEqual(data["ram_percent"], 25.0)
        self.assertEqual(data["temperature_c"], 45.0)

if __name__ == '__main__':
    unittest.main()