"""
*****
Purpose: API route tests for the OAT Web Polar Alignment Flask application.

Validates HTTP status codes, JSON response structure, and basic behaviour
of the /api/* endpoints using the Flask test client fixture.

Parameters:
None

Returns:
None
*****
"""

import json


# ============================================================================
# Index Route
# ============================================================================

class TestIndexRoute:
    """
    *****
    Purpose: Verify that the root index page is served correctly.

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_get_index_returns_200(self, client):
        """
        *****
        Purpose: GET / should return HTTP 200 with the rendered index page.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.get("/")
        assert response.status_code == 200


# ============================================================================
# Status Route
# ============================================================================

class TestStatusRoute:
    """
    *****
    Purpose: Verify the /api/status endpoint returns correct JSON structure
    when no hardware is connected.

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_get_status_returns_200(self, client):
        """
        *****
        Purpose: GET /api/status should return HTTP 200.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.get("/api/status")
        assert response.status_code == 200

    def test_status_has_mount_connected_key(self, client):
        """
        *****
        Purpose: Response JSON must contain the 'mount_connected' key.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.get("/api/status")
        data = json.loads(response.data)
        assert "mount_connected" in data

    def test_mount_connected_is_false_by_default(self, client):
        """
        *****
        Purpose: With no real hardware, mount_connected should be False.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.get("/api/status")
        data = json.loads(response.data)
        assert data["mount_connected"] is False


# ============================================================================
# Settings Route
# ============================================================================

class TestSettingsRoute:
    """
    *****
    Purpose: Verify the /api/settings endpoint for GET and POST methods.

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_get_settings_returns_200(self, client):
        """
        *****
        Purpose: GET /api/settings should return HTTP 200.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.get("/api/settings")
        assert response.status_code == 200

    def test_settings_has_latitude_key(self, client):
        """
        *****
        Purpose: Response JSON must contain 'latitude'.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.get("/api/settings")
        data = json.loads(response.data)
        assert "latitude" in data

    def test_settings_has_longitude_key(self, client):
        """
        *****
        Purpose: Response JSON must contain 'longitude'.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.get("/api/settings")
        data = json.loads(response.data)
        assert "longitude" in data

    def test_post_settings_returns_200(self, client):
        """
        *****
        Purpose: POST /api/settings with a valid JSON body should return 200.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.post(
            "/api/settings",
            data=json.dumps({"target_accuracy": 30}),
            content_type="application/json",
        )
        assert response.status_code == 200


# ============================================================================
# Connect Route
# ============================================================================

class TestConnectRoute:
    """
    *****
    Purpose: Verify the /api/connect endpoint behaves gracefully when
    no real serial device is available.

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_post_connect_without_device_returns_500(self, client):
        """
        *****
        Purpose: POST /api/connect with a nonexistent serial port should
        return HTTP 500 because the serial connection will fail.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.post(
            "/api/connect",
            data=json.dumps({"serial_port": "/dev/ttyUSB0"}),
            content_type="application/json",
        )
        assert response.status_code == 500


# ============================================================================
# Locations Route
# ============================================================================

class TestLocationsRoute:
    """
    *****
    Purpose: Verify the /api/locations endpoint returns a valid JSON
    response.

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_get_locations_returns_200(self, client):
        """
        *****
        Purpose: GET /api/locations should return HTTP 200.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.get("/api/locations")
        assert response.status_code == 200

    def test_locations_response_is_dict(self, client):
        """
        *****
        Purpose: The locations response should be a JSON object (dict),
        since locations are stored as a name-to-coordinate mapping.

        Parameters:
        FlaskClient client: Flask test client fixture

        Returns:
        None
        *****
        """
        response = client.get("/api/locations")
        data = json.loads(response.data)
        assert isinstance(data, dict)
