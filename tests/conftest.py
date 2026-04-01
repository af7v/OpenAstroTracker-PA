"""
Shared pytest fixtures for OAT Web Polar Alignment tests.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_config(monkeypatch, tmp_path):
    """
    *****
    Purpose: Override all config module constants so tests never touch real
    hardware, network services, or filesystem paths.

    Parameters:
    monkeypatch monkeypatch: pytest monkeypatch fixture for patching module attributes
    pathlib.Path tmp_path: pytest tmp_path fixture providing a unique temporary directory

    Returns:
    pathlib.Path: the temporary CAPTURE_DIR path created for the test
    *****
    """
    capture_dir = tmp_path / "captures"
    capture_dir.mkdir()

    import config

    # INDI server settings
    monkeypatch.setattr(config, "INDI_HOST", "localhost")
    monkeypatch.setattr(config, "INDI_PORT", 7624)
    monkeypatch.setattr(config, "TELESCOPE_NAME", "Test Telescope")

    # Camera settings
    monkeypatch.setattr(config, "CAMERA_TYPE", "opencv")
    monkeypatch.setattr(config, "CAMERA_DEVICE", "0")
    monkeypatch.setattr(config, "INDI_CAMERA_NAME", "Test Camera")

    # Plate solver settings
    monkeypatch.setattr(config, "SOLVER", "astap")
    monkeypatch.setattr(config, "ASTAP_PATH", "/tmp/fake_astap")
    monkeypatch.setattr(config, "ASTROMETRY_PATH", "/tmp/fake_solve-field")
    monkeypatch.setattr(config, "SOLVER_TIMEOUT", 10)

    # Capture defaults
    monkeypatch.setattr(config, "DEFAULT_EXPOSURE", 1.0)
    monkeypatch.setattr(config, "DEFAULT_GAIN", 50)

    # Polar alignment settings
    monkeypatch.setattr(config, "TARGET_ACCURACY", 60)
    monkeypatch.setattr(config, "MAX_ITERATIONS", 5)
    monkeypatch.setattr(config, "SETTLE_TIME", 0.0)

    # Site location
    monkeypatch.setattr(config, "LATITUDE", 40.0)
    monkeypatch.setattr(config, "LONGITUDE", -111.0)

    # Jog control defaults
    monkeypatch.setattr(config, "AZ_STEP_DEFAULT", 5.0)
    monkeypatch.setattr(config, "ALT_STEP_DEFAULT", 5.0)

    # File paths
    monkeypatch.setattr(config, "CAPTURE_DIR", str(capture_dir))

    # Web server settings
    monkeypatch.setattr(config, "WEB_HOST", "127.0.0.1")
    monkeypatch.setattr(config, "WEB_PORT", 5555)
    monkeypatch.setattr(config, "DEBUG", True)

    return capture_dir


@pytest.fixture
def mock_serial():
    """
    *****
    Purpose: Create a MagicMock that simulates an OAT serial connection
    responding to Meade LX200 protocol commands.

    Parameters:
    None

    Returns:
    unittest.mock.MagicMock: a mock serial port whose read_until method
        returns realistic OAT responses for common Meade LX200 commands
    *****
    """
    serial_mock = MagicMock()

    # Map Meade LX200 commands to expected OAT responses
    responses = {
        b":GVP#": b"OpenAstroTracker#",  # Get product name
        b":GR#": b"06:30:00#",           # Get RA
        b":GD#": b"+45*00:00#",          # Get Dec
        b":Q#": b"1",                    # Stop slew
    }

    def _read_until(terminator=b"#", size=None):
        """
        *****
        Purpose: Return a canned response matching the last command written
        to the mock serial port.

        Parameters:
        bytes terminator: the delimiter byte sequence (default b"#")
        NoneType size: unused, kept for API compatibility

        Returns:
        bytes: the simulated OAT response for the most recent command,
            or b"1" for any unrecognised command
        *****
        """
        last_write = serial_mock.write.call_args
        if last_write is not None:
            command = last_write[0][0]
            return responses.get(command, b"1")
        return b"1"

    serial_mock.read_until = MagicMock(side_effect=_read_until)

    return serial_mock


def _ensure_app_imported():
    """
    *****
    Purpose: Import the app module safely by forcing SocketIO to use
    the 'threading' async mode instead of 'eventlet', which is not
    installed in the test environment.

    The app module is only imported once (cached in sys.modules).
    This helper patches flask_socketio.SocketIO.__init__ on the first
    import so the module-level SocketIO(..., async_mode='eventlet')
    call succeeds without eventlet being installed.

    Parameters:
    None

    Returns:
    module: the imported app module
    *****
    """
    import sys
    if "app" in sys.modules:
        return sys.modules["app"]

    import flask_socketio
    _orig_init = flask_socketio.SocketIO.__init__

    def _patched_init(self, *args, **kwargs):
        """
        *****
        Purpose: Wrapper that replaces async_mode='eventlet' with
        'threading' so tests can run without eventlet installed.

        Parameters:
        SocketIO self: the SocketIO instance being initialised
        args: positional arguments forwarded to original __init__
        kwargs: keyword arguments forwarded to original __init__

        Returns:
        None
        *****
        """
        kwargs["async_mode"] = "threading"
        return _orig_init(self, *args, **kwargs)

    flask_socketio.SocketIO.__init__ = _patched_init
    try:
        import app as app_module
    finally:
        flask_socketio.SocketIO.__init__ = _orig_init

    return app_module


@pytest.fixture
def client(mock_config):
    """
    *****
    Purpose: Provide a Flask test client with all hardware singletons
    reset and optional-dependency flags patched so that tests run in
    isolation without touching real serial ports, cameras, or solvers.

    Parameters:
    pathlib.Path mock_config: the autouse mock_config fixture (ensures
        config module constants are safe for testing)

    Returns:
    flask.testing.FlaskClient: a test client bound to the Flask app
    *****
    """
    import mount_client
    import camera_client
    import plate_solver

    # Reset singletons so each test gets a fresh instance
    mount_client._mount_client = None
    camera_client._camera_client = None
    plate_solver._plate_solver = None

    with patch.object(mount_client, "SERIAL_AVAILABLE", True), \
         patch.object(camera_client, "CV2_AVAILABLE", False), \
         patch.object(plate_solver, "ASTROPY_AVAILABLE", False):

        app_module = _ensure_app_imported()
        app_module.app.config["TESTING"] = True

        yield app_module.app.test_client()

    # Cleanup singletons after test
    mount_client._mount_client = None
    camera_client._camera_client = None
    plate_solver._plate_solver = None
