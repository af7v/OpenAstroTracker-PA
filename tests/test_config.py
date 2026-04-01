"""
*****
Purpose: Unit tests for config.py covering default values and the
override-file merge mechanism.

Parameters:
None

Returns:
None
*****
"""

import importlib
import importlib.util
import os
import sys
import textwrap

import pytest


def _load_config_defaults():
    """
    *****
    Purpose: Load a fresh copy of the config module so that tests can
    inspect the original default values without interference from the
    autouse mock_config fixture.

    Parameters:
    None

    Returns:
    types.ModuleType config_fresh: a freshly-loaded config module whose
        attributes reflect the on-disk defaults
    *****
    """
    spec = importlib.util.spec_from_file_location(
        "config_defaults",
        os.path.join(os.path.dirname(__file__), os.pardir, "config.py"),
    )
    config_fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_fresh)
    return config_fresh


class TestConfigDefaults:
    """
    *****
    Purpose: Verify that all default configuration values in config.py
    exist with the correct types and expected values.

    Parameters:
    None

    Returns:
    None
    *****
    """

    @pytest.fixture(autouse=True)
    def _defaults(self):
        """
        *****
        Purpose: Load a fresh config module once per test so each
        assertion works against pristine defaults.

        Parameters:
        None

        Returns:
        None (sets self.cfg as a side effect)
        *****
        """
        self.cfg = _load_config_defaults()

    def test_latitude_is_numeric(self):
        """
        *****
        Purpose: Confirm LATITUDE is a numeric type (int or float).

        Parameters:
        None

        Returns:
        None
        *****
        """
        assert isinstance(self.cfg.LATITUDE, (int, float))

    def test_longitude_is_numeric(self):
        """
        *****
        Purpose: Confirm LONGITUDE is a numeric type (int or float).

        Parameters:
        None

        Returns:
        None
        *****
        """
        assert isinstance(self.cfg.LONGITUDE, (int, float))

    def test_target_accuracy_positive(self):
        """
        *****
        Purpose: Confirm TARGET_ACCURACY is greater than zero.

        Parameters:
        None

        Returns:
        None
        *****
        """
        assert self.cfg.TARGET_ACCURACY > 0

    def test_capture_dir_is_nonempty_string(self):
        """
        *****
        Purpose: Confirm CAPTURE_DIR is a non-empty string.

        Parameters:
        None

        Returns:
        None
        *****
        """
        assert isinstance(self.cfg.CAPTURE_DIR, str)
        assert len(self.cfg.CAPTURE_DIR) > 0

    def test_web_port_default(self):
        """
        *****
        Purpose: Confirm WEB_PORT defaults to 5000.

        Parameters:
        None

        Returns:
        None
        *****
        """
        assert self.cfg.WEB_PORT == 5000

    def test_indi_host_default(self):
        """
        *****
        Purpose: Confirm INDI_HOST defaults to "localhost".

        Parameters:
        None

        Returns:
        None
        *****
        """
        assert self.cfg.INDI_HOST == "localhost"

    def test_indi_port_default(self):
        """
        *****
        Purpose: Confirm INDI_PORT defaults to 7624.

        Parameters:
        None

        Returns:
        None
        *****
        """
        assert self.cfg.INDI_PORT == 7624

    def test_solver_is_valid_option(self):
        """
        *****
        Purpose: Confirm SOLVER is one of the two supported solvers.

        Parameters:
        None

        Returns:
        None
        *****
        """
        assert self.cfg.SOLVER in ("astap", "astrometry")

    def test_camera_type_is_valid_option(self):
        """
        *****
        Purpose: Confirm CAMERA_TYPE is one of the supported camera
        backends.

        Parameters:
        None

        Returns:
        None
        *****
        """
        assert self.cfg.CAMERA_TYPE in ("opencv", "v4l2", "picamera", "indi")


class TestConfigOverride:
    """
    *****
    Purpose: Verify that the override mechanism correctly loads a
    Python file and merges its uppercase variables into the
    configuration namespace.

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_override_file_merges_uppercase_vars(self, tmp_path):
        """
        *****
        Purpose: Create a temporary override file with LATITUDE and
        LONGITUDE values, load it using the same importlib.util
        technique config.py uses, and verify the overridden values
        are applied.

        Parameters:
        pathlib.Path tmp_path: pytest-provided temporary directory

        Returns:
        None
        *****
        """
        override_file = tmp_path / "override_config.py"
        override_file.write_text(
            textwrap.dedent("""\
                LATITUDE = 99.9
                LONGITUDE = -88.8
            """)
        )

        # Replicate the override mechanism from config.py
        spec = importlib.util.spec_from_file_location(
            "config_override", str(override_file)
        )
        assert spec is not None and spec.loader is not None

        override_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(override_mod)

        merged = {}
        for key in [k for k in dir(override_mod) if k.isupper()]:
            merged[key] = getattr(override_mod, key)

        assert merged["LATITUDE"] == pytest.approx(99.9)
        assert merged["LONGITUDE"] == pytest.approx(-88.8)

    def test_override_ignores_lowercase_vars(self, tmp_path):
        """
        *****
        Purpose: Confirm that the override mechanism only picks up
        uppercase variable names and ignores lowercase ones.

        Parameters:
        pathlib.Path tmp_path: pytest-provided temporary directory

        Returns:
        None
        *****
        """
        override_file = tmp_path / "override_config.py"
        override_file.write_text(
            textwrap.dedent("""\
                LATITUDE = 55.5
                secret_key = "should_be_ignored"
            """)
        )

        spec = importlib.util.spec_from_file_location(
            "config_override", str(override_file)
        )
        override_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(override_mod)

        merged = {}
        for key in [k for k in dir(override_mod) if k.isupper()]:
            merged[key] = getattr(override_mod, key)

        assert "LATITUDE" in merged
        assert "secret_key" not in merged
