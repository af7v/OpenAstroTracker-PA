"""
*****
Purpose: Unit tests for the PA calculator module

Covers parsing of RA/DEC strings, polar alignment error calculation,
error dataclass behaviour, correction calculation, and iteration
estimation.

Parameters:
None

Returns:
None
*****
"""

import math

import pytest

from pa_calculator import (
    PAError,
    calculate_correction,
    calculate_pa_error,
    estimate_iterations,
    parse_dec_string,
    parse_ra_string,
)


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


# ===========================================================================
# TestParseRaString
# ===========================================================================


class TestParseRaString:
    """
    *****
    Purpose: Verify parse_ra_string converts RA strings to degrees correctly

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_six_hours_to_ninety_degrees(self):
        """
        *****
        Purpose: 06:00:00 is 6 hours which equals 90 degrees (6 * 15)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_ra_string("06:00:00")
        assert_close(result, 90.0)

    def test_twelve_thirty_thirty(self):
        """
        *****
        Purpose: 12:30:30 should convert to approximately 187.625 degrees

        Parameters:
        None

        Returns:
        None
        *****
        """
        # 12h + 30m/60 + 30s/3600 = 12.508333... hours
        # 12.508333... * 15 = 187.625 degrees
        result = parse_ra_string("12:30:30")
        assert_close(result, 187.625)

    def test_zero_hours(self):
        """
        *****
        Purpose: 00:00:00 should convert to 0.0 degrees

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_ra_string("00:00:00")
        assert_close(result, 0.0)

    def test_max_ra_twenty_three_fifty_nine_fifty_nine(self):
        """
        *****
        Purpose: 23:59:59 should convert to approximately 359.996 degrees

        Parameters:
        None

        Returns:
        None
        *****
        """
        # 23 + 59/60 + 59/3600 = 23.99972... hours
        # 23.99972... * 15 = 359.99583... degrees
        expected = (23 + 59 / 60.0 + 59 / 3600.0) * 15.0
        result = parse_ra_string("23:59:59")
        assert_close(result, expected)

    def test_decimal_hours_input(self):
        """
        *****
        Purpose: A bare decimal number (6.0) should be treated as hours and
        converted to degrees (90.0)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_ra_string("6.0")
        assert_close(result, 90.0)

    def test_whitespace_is_stripped(self):
        """
        *****
        Purpose: Leading and trailing whitespace should be stripped before parsing

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_ra_string("  06:00:00  ")
        assert_close(result, 90.0)

    def test_invalid_input_returns_none(self):
        """
        *****
        Purpose: Garbage input should return None without raising

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_ra_string("not-a-number")
        assert result is None

    def test_empty_string_returns_none(self):
        """
        *****
        Purpose: An empty string should return None without raising

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_ra_string("")
        assert result is None


# ===========================================================================
# TestParseDecString
# ===========================================================================


class TestParseDecString:
    """
    *****
    Purpose: Verify parse_dec_string converts DEC strings to degrees correctly

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_positive_forty_five_star_separator(self):
        """
        *****
        Purpose: +45*00:00 should parse to 45.0 degrees

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_dec_string("+45*00:00")
        assert_close(result, 45.0)

    def test_negative_thirty_fifteen_minutes(self):
        """
        *****
        Purpose: -30*15:00 should parse to -30.25 degrees (15 arcminutes = 0.25 deg)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_dec_string("-30*15:00")
        assert_close(result, -30.25)

    def test_colon_separator(self):
        """
        *****
        Purpose: +45:30:00 (colon separator instead of *) should parse to 45.5 degrees

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_dec_string("+45:30:00")
        assert_close(result, 45.5)

    def test_no_sign_defaults_positive(self):
        """
        *****
        Purpose: A DEC string without a leading sign should default to positive

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_dec_string("45*00:00")
        assert_close(result, 45.0)

    def test_zero_dec(self):
        """
        *****
        Purpose: +00*00:00 should parse to 0.0 degrees

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_dec_string("+00*00:00")
        assert_close(result, 0.0)

    def test_negative_ninety(self):
        """
        *****
        Purpose: -90*00:00 should parse to -90.0 degrees

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_dec_string("-90*00:00")
        assert_close(result, -90.0)

    def test_empty_string_returns_none(self):
        """
        *****
        Purpose: An empty string should return None without raising

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_dec_string("")
        assert result is None

    def test_invalid_input_returns_none(self):
        """
        *****
        Purpose: Garbage input should return None without raising

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = parse_dec_string("not-valid")
        assert result is None


# ===========================================================================
# TestCalculatePaError
# ===========================================================================


class TestCalculatePaError:
    """
    *****
    Purpose: Verify calculate_pa_error produces correct AZ/ALT decomposition

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_zero_error_when_positions_match(self):
        """
        *****
        Purpose: Identical solved and mount positions should yield zero error

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = calculate_pa_error(
            solved_ra=90.0,
            solved_dec=45.0,
            mount_ra=90.0,
            mount_dec=45.0,
            latitude=40.0,
        )
        assert_close(result.az_error, 0.0)
        assert_close(result.alt_error, 0.0)
        assert_close(result.total_error, 0.0)

    def test_pure_dec_offset_maps_to_alt_error(self):
        """
        *****
        Purpose: A 1-degree DEC offset should map to 60 arcminutes of ALT error

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = calculate_pa_error(
            solved_ra=90.0,
            solved_dec=46.0,
            mount_ra=90.0,
            mount_dec=45.0,
            latitude=40.0,
        )
        assert_close(result.az_error, 0.0)
        assert_close(result.alt_error, 60.0)

    def test_pure_ra_offset_maps_to_az_error_scaled_by_cos_dec(self):
        """
        *****
        Purpose: A pure RA offset should map to AZ error scaled by cos(DEC).
        At DEC=45, cos(45)=~0.7071, so 1 degree RA offset = 60 arcmin / 0.7071

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = calculate_pa_error(
            solved_ra=91.0,
            solved_dec=45.0,
            mount_ra=90.0,
            mount_dec=45.0,
            latitude=40.0,
        )
        cos_dec = math.cos(math.radians(45.0))
        expected_az = 60.0 / cos_dec  # delta_ra_arcmin / cos_dec
        assert_close(result.az_error, expected_az, tolerance=0.01)
        assert_close(result.alt_error, 0.0)

    def test_ra_wrapping_across_zero_boundary(self):
        """
        *****
        Purpose: RA wrapping across the 0/360 boundary should produce a small
        difference (1 vs 359 should be ~2 degrees apart, not 358)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = calculate_pa_error(
            solved_ra=1.0,
            solved_dec=45.0,
            mount_ra=359.0,
            mount_dec=45.0,
            latitude=40.0,
        )
        # delta_ra should be +2 degrees (wrapped), not -358
        cos_dec = math.cos(math.radians(45.0))
        expected_az = (2.0 * 60.0) / cos_dec
        assert_close(result.az_error, expected_az, tolerance=0.1)

    def test_returns_pa_error_dataclass(self):
        """
        *****
        Purpose: The return value should be an instance of PAError

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = calculate_pa_error(
            solved_ra=90.0,
            solved_dec=45.0,
            mount_ra=90.0,
            mount_dec=45.0,
            latitude=40.0,
        )
        assert isinstance(result, PAError)

    def test_total_error_pythagorean_formula(self):
        """
        *****
        Purpose: Total error should follow Pythagorean formula:
        sqrt(az_error^2 + alt_error^2) * 60 (arcseconds)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = calculate_pa_error(
            solved_ra=91.0,
            solved_dec=46.0,
            mount_ra=90.0,
            mount_dec=45.0,
            latitude=40.0,
        )
        expected_total = math.sqrt(result.az_error ** 2 + result.alt_error ** 2) * 60
        assert_close(result.total_error, expected_total, tolerance=0.1)


# ===========================================================================
# TestPAError
# ===========================================================================


class TestPAError:
    """
    *****
    Purpose: Verify PAError dataclass methods (is_aligned, __str__)

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_is_aligned_true_when_below_target(self):
        """
        *****
        Purpose: is_aligned should return True when total_error < target_accuracy

        Parameters:
        None

        Returns:
        None
        *****
        """
        error = PAError(az_error=0.1, alt_error=0.1, total_error=10.0)
        assert error.is_aligned(target_accuracy=60.0) is True

    def test_is_aligned_false_when_above_target(self):
        """
        *****
        Purpose: is_aligned should return False when total_error >= target_accuracy

        Parameters:
        None

        Returns:
        None
        *****
        """
        error = PAError(az_error=5.0, alt_error=5.0, total_error=120.0)
        assert error.is_aligned(target_accuracy=60.0) is False

    def test_is_aligned_uses_config_default(self):
        """
        *****
        Purpose: When target_accuracy is not supplied, is_aligned should use
        config.TARGET_ACCURACY (mocked to 60 by conftest)

        Parameters:
        None

        Returns:
        None
        *****
        """
        # Below config default of 60 arcseconds
        aligned = PAError(az_error=0.1, alt_error=0.1, total_error=30.0)
        assert aligned.is_aligned() is True

        # Above config default of 60 arcseconds
        not_aligned = PAError(az_error=5.0, alt_error=5.0, total_error=120.0)
        assert not_aligned.is_aligned() is False

    def test_str_contains_labels(self):
        """
        *****
        Purpose: __str__ should contain 'AZ:', 'ALT:', and 'Total:' labels

        Parameters:
        None

        Returns:
        None
        *****
        """
        error = PAError(az_error=1.5, alt_error=-2.3, total_error=165.0)
        text = str(error)
        assert "AZ:" in text
        assert "ALT:" in text
        assert "Total:" in text


# ===========================================================================
# TestCalculateCorrection
# ===========================================================================


class TestCalculateCorrection:
    """
    *****
    Purpose: Verify calculate_correction applies the correct sign inversion

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_default_invert_az_true(self):
        """
        *****
        Purpose: With invert_az=True (default), az_correction should equal
        +az_error (double inversion: -error then negated again)

        Parameters:
        None

        Returns:
        None
        *****
        """
        error = PAError(az_error=5.0, alt_error=3.0, total_error=350.0)
        az_corr, alt_corr = calculate_correction(error)
        # invert_az=True: az_correction = -(-az_error) = az_error
        assert_close(az_corr, 5.0)
        assert_close(alt_corr, 3.0)

    def test_invert_az_false(self):
        """
        *****
        Purpose: With invert_az=False, az_correction should be -az_error
        (single inversion only)

        Parameters:
        None

        Returns:
        None
        *****
        """
        error = PAError(az_error=5.0, alt_error=3.0, total_error=350.0)
        az_corr, alt_corr = calculate_correction(error, invert_az=False)
        # invert_az=False: az_correction = -az_error
        assert_close(az_corr, -5.0)
        assert_close(alt_corr, 3.0)

    def test_zero_error_gives_zero_correction(self):
        """
        *****
        Purpose: Zero error should produce zero correction regardless of flags

        Parameters:
        None

        Returns:
        None
        *****
        """
        error = PAError(az_error=0.0, alt_error=0.0, total_error=0.0)
        az_corr, alt_corr = calculate_correction(error, invert_az=False)
        assert_close(az_corr, 0.0)
        assert_close(alt_corr, 0.0)

        az_corr2, alt_corr2 = calculate_correction(error, invert_az=True)
        assert_close(az_corr2, 0.0)
        assert_close(alt_corr2, 0.0)


# ===========================================================================
# TestEstimateIterations
# ===========================================================================


class TestEstimateIterations:
    """
    *****
    Purpose: Verify estimate_iterations returns sensible iteration counts

    Parameters:
    None

    Returns:
    None
    *****
    """

    def test_already_aligned_returns_zero(self):
        """
        *****
        Purpose: When current_error <= target_accuracy, should return 0

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = estimate_iterations(30.0, target_accuracy=60.0)
        assert result == 0

    def test_large_error_returns_positive_iterations(self):
        """
        *****
        Purpose: When current_error > target_accuracy, should return between 1 and 20

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = estimate_iterations(3600.0, target_accuracy=60.0)
        assert 1 <= result <= 20

    def test_uses_config_default_target(self):
        """
        *****
        Purpose: When target_accuracy is not supplied, should use
        config.TARGET_ACCURACY (mocked to 60 by conftest)

        Parameters:
        None

        Returns:
        None
        *****
        """
        # Below config default of 60 -- should be 0
        assert estimate_iterations(30.0) == 0
        # Above config default of 60 -- should be > 0
        assert estimate_iterations(3600.0) > 0

    def test_max_cap_at_twenty(self):
        """
        *****
        Purpose: Even with an astronomically large error, should never return
        more than 20

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = estimate_iterations(1e12, target_accuracy=1.0)
        assert result == 20

    def test_exact_target_returns_zero(self):
        """
        *****
        Purpose: When current_error == target_accuracy, should return 0
        (the <= check in the source)

        Parameters:
        None

        Returns:
        None
        *****
        """
        result = estimate_iterations(60.0, target_accuracy=60.0)
        assert result == 0
