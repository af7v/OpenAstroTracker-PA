"""
Shared pytest fixtures for OAT Web Polar Alignment tests.
"""

import os
from unittest.mock import MagicMock

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
