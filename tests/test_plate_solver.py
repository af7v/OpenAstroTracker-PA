"""
*****
Purpose: Unit tests for the plate_solver module

Covers SolveResult dataclass formatting methods (ra_hours, ra_hms, dec_dms),
PlateSolver dispatch logic (set_solver, solve with missing image), without
invoking real ASTAP or astrometry.net subprocesses.

Parameters:
None

Returns:
None
*****
"""

import pytest

from plate_solver import PlateSolver, SolveResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FLOAT_TOLERANCE = 1e-3
"""Tolerance used for floating-point comparisons throughout the test suite."""


def assert_close(actual, expected, tolerance=FLOAT_TOLERANCE):
    """
    *****
    Purpose: Assert that two floats are within a given tolerance

    Parameters:
    float actual: the value produced by the code under test
    float expected: the value the test expects
    float tolerance: maximum allowed absolute difference (default FLOAT_TOLERANCE)

    Returns:
    None
    *****
    """
    assert abs(actual - expected) < tolerance, (
        f"Expected {expected} +/- {tolerance}, got {actual}"
    )


def make_solve_result(**overrides):
    """
    *****
    Purpose: Build a SolveResult with sensible defaults, allowing callers
    to override any field for the specific test scenario

    Parameters:
    dict overrides: keyword arguments that override the default SolveResult fields

    Returns:
    SolveResult: a SolveResult instance with the given or default values
    *****
    """
    defaults = dict(
        ra=0.0,
        dec=0.0,
        rotation=0.0,
        pixel_scale=1.0,
        fov_width=1.0,
        fov_height=1.0,
        solver="astap",
    )
    defaults.update(overrides)
    return SolveResult(**defaults)


# ===========================================================================
# TestSolveResult
# ===========================================================================


class TestSolveResult:
    """
    *****
    Purpose: Verify SolveResult formatting methods (ra_hours, ra_hms, dec_dms)

    Parameters:
    None

    Returns:
    None
    *****
    """

    # -----------------------------------------------------------------------
    # ra_hours
    # -----------------------------------------------------------------------

    def test_ra_hours_one_hundred_eighty_degrees_is_twelve_hours(self):
        """
        *****
        Purpose: RA of 180.0 degrees should convert to 12.0 hours (180 / 15)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(ra=180.0)
        assert_close(result.ra_hours(), 12.0)

    def test_ra_hours_zero_degrees_is_zero_hours(self):
        """
        *****
        Purpose: RA of 0.0 degrees should convert to 0.0 hours

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(ra=0.0)
        assert_close(result.ra_hours(), 0.0)

    def test_ra_hours_ninety_degrees_is_six_hours(self):
        """
        *****
        Purpose: RA of 90.0 degrees should convert to 6.0 hours (90 / 15)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(ra=90.0)
        assert_close(result.ra_hours(), 6.0)

    # -----------------------------------------------------------------------
    # ra_hms
    # -----------------------------------------------------------------------

    def test_ra_hms_zero_degrees(self):
        """
        *****
        Purpose: RA of 0.0 degrees should format as "00:00:00.00"

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(ra=0.0)
        assert result.ra_hms() == "00:00:00.00"

    def test_ra_hms_one_hundred_eighty_degrees(self):
        """
        *****
        Purpose: RA of 180.0 degrees should format as "12:00:00.00"

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(ra=180.0)
        assert result.ra_hms() == "12:00:00.00"

    def test_ra_hms_arbitrary_value(self):
        """
        *****
        Purpose: RA of 97.5 degrees should produce "06:30:00.00"
        (97.5 / 15 = 6.5 hours = 6h 30m 0s)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(ra=97.5)
        assert result.ra_hms() == "06:30:00.00"

    # -----------------------------------------------------------------------
    # dec_dms
    # -----------------------------------------------------------------------

    def test_dec_dms_positive_forty_five_point_five(self):
        """
        *****
        Purpose: DEC of 45.5 degrees should format as "+45:30:00.0"
        (0.5 deg = 30 arcmin)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(dec=45.5)
        assert result.dec_dms() == "+45:30:00.0"

    def test_dec_dms_negative_thirty_point_two_five(self):
        """
        *****
        Purpose: DEC of -30.25 degrees should format as "-30:15:00.0"
        (0.25 deg = 15 arcmin)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(dec=-30.25)
        assert result.dec_dms() == "-30:15:00.0"

    def test_dec_dms_zero(self):
        """
        *****
        Purpose: DEC of 0.0 degrees should format as "+00:00:00.0"
        (zero is treated as positive)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(dec=0.0)
        assert result.dec_dms() == "+00:00:00.0"

    def test_dec_dms_negative_ninety(self):
        """
        *****
        Purpose: DEC of -90.0 degrees should format as "-90:00:00.0"

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(dec=-90.0)
        assert result.dec_dms() == "-90:00:00.0"

    def test_dec_dms_with_arcseconds(self):
        """
        *****
        Purpose: DEC of 45.5125 degrees should include arcseconds.
        0.5125 deg = 30 arcmin + 45.0 arcsec, so "+45:30:45.0"

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = make_solve_result(dec=45.5125)
        assert result.dec_dms() == "+45:30:45.0"


# ===========================================================================
# TestPlateSolverDispatch
# ===========================================================================


class TestPlateSolverDispatch:
    """
    *****
    Purpose: Verify PlateSolver dispatch logic (set_solver, solve error paths)
    without invoking real solver subprocesses

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_set_solver_to_astrometry(self):
        """
        *****
        Purpose: set_solver("astrometry") should change the solver attribute
        from the default "astap" to "astrometry"

        Parameters:
        None

        Returns:
        None
        *****
        """
        solver = PlateSolver()
        assert solver.solver == "astap"  # conftest default
        solver.set_solver("astrometry")
        assert solver.solver == "astrometry"

    def test_set_solver_to_astap(self):
        """
        *****
        Purpose: set_solver("astap") should keep (or restore) the solver
        attribute to "astap"

        Parameters:
        None

        Returns:
        None
        *****
        """
        solver = PlateSolver()
        solver.set_solver("astrometry")
        solver.set_solver("astap")
        assert solver.solver == "astap"

    def test_set_solver_invalid_leaves_unchanged(self):
        """
        *****
        Purpose: set_solver("invalid") should leave the solver attribute
        unchanged at its current value

        Parameters:
        None

        Returns:
        None
        *****
        """
        solver = PlateSolver()
        original = solver.solver
        solver.set_solver("invalid")
        assert solver.solver == original

    def test_set_solver_empty_string_leaves_unchanged(self):
        """
        *****
        Purpose: set_solver("") should leave the solver attribute unchanged

        Parameters:
        None

        Returns:
        None
        *****
        """
        solver = PlateSolver()
        original = solver.solver
        solver.set_solver("")
        assert solver.solver == original

    def test_solve_nonexistent_image_returns_none(self):
        """
        *****
        Purpose: solve() with a nonexistent image path should return None
        without raising an exception

        Parameters:
        None

        Returns:
        None
        *****
        """
        solver = PlateSolver()
        result = solver.solve("/tmp/does_not_exist_12345.fits")
        assert result is None

    def test_solve_unknown_solver_returns_none(self, tmp_path):
        """
        *****
        Purpose: solve() should return None when the solver attribute is set
        to an unrecognised value (bypassing the valid-name check in set_solver
        by directly assigning the attribute)

        Parameters:
        tmp_path tmp_path: pytest fixture providing a unique temporary directory

        Returns:
        None
        *****
        """
        # Create a dummy image file so the "file not found" guard passes
        dummy_image = tmp_path / "test.fits"
        dummy_image.write_text("dummy")

        solver = PlateSolver()
        solver.solver = "unknown_solver"  # bypass set_solver validation
        result = solver.solve(str(dummy_image))
        assert result is None
