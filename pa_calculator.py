"""
*****
Purpose: Polar alignment error calculator

Calculates the azimuth and altitude correction needed based on
the difference between the plate-solved position and the mount's
reported position.

Parameters:
None

Returns:
Functions for PA error calculation
*****
"""

import math
import logging
from typing import Tuple, Optional
from dataclasses import dataclass

import config

logger = logging.getLogger(__name__)


@dataclass
class PAError:
    """
    *****
    Purpose: Container for polar alignment error

    Parameters:
    float az_error: Azimuth error in arcminutes (+ = adjust right)
    float alt_error: Altitude error in arcminutes (+ = adjust up)
    float total_error: Total error in arcseconds

    Returns:
    PAError instance
    *****
    """
    az_error: float  # arcminutes
    alt_error: float  # arcminutes
    total_error: float  # arcseconds

    def is_aligned(self, target_accuracy: float = None) -> bool:
        """Check if error is within target accuracy."""
        if target_accuracy is None:
            target_accuracy = config.TARGET_ACCURACY
        return self.total_error < target_accuracy

    def __str__(self) -> str:
        return (f"AZ: {self.az_error:+.2f}', ALT: {self.alt_error:+.2f}', "
                f"Total: {self.total_error:.1f}\"")


def calculate_pa_error(
    solved_ra: float,
    solved_dec: float,
    mount_ra: float,
    mount_dec: float,
    latitude: float = None
) -> PAError:
    """
    *****
    Purpose: Calculate polar alignment error from solved vs mount position

    The basic principle: If the mount is perfectly polar aligned, the solved
    position should match the mount's reported position. Any difference
    indicates polar misalignment, which can be decomposed into azimuth and
    altitude components.

    Parameters:
    float solved_ra: Plate-solved Right Ascension in degrees
    float solved_dec: Plate-solved Declination in degrees
    float mount_ra: Mount's reported RA in degrees
    float mount_dec: Mount's reported DEC in degrees
    float latitude: Observer's latitude in degrees (uses config if None)

    Returns:
    PAError: Polar alignment error with AZ/ALT components
    *****
    """
    if latitude is None:
        latitude = config.LATITUDE

    # Convert to radians
    solved_ra_rad = math.radians(solved_ra)
    solved_dec_rad = math.radians(solved_dec)
    mount_ra_rad = math.radians(mount_ra)
    mount_dec_rad = math.radians(mount_dec)
    lat_rad = math.radians(latitude)

    # Calculate the difference in RA and DEC
    delta_ra = solved_ra_rad - mount_ra_rad
    delta_dec = solved_dec_rad - mount_dec_rad

    # Wrap delta_ra to [-pi, pi]
    while delta_ra > math.pi:
        delta_ra -= 2 * math.pi
    while delta_ra < -math.pi:
        delta_ra += 2 * math.pi

    # Convert to arcminutes
    delta_ra_arcmin = math.degrees(delta_ra) * 60
    delta_dec_arcmin = math.degrees(delta_dec) * 60

    # Transform the RA/DEC error to AZ/ALT error
    # This depends on where the mount is pointing and the latitude
    # For a mount pointing near the pole, the transformation is approximately:
    #   AZ error ≈ RA error / cos(DEC) at low latitudes
    #   ALT error ≈ DEC error

    # Hour angle of the observation
    # (Would need sidereal time for accurate calculation, but for PA
    # near the meridian, we can approximate)

    # Simple approximation for equatorial mount PA error:
    # When pointed at celestial pole, the error transformation is straightforward
    cos_dec = math.cos(mount_dec_rad)
    if cos_dec < 0.1:
        cos_dec = 0.1  # Prevent division issues near pole

    # Calculate azimuth error component
    # RA error maps to azimuth, scaled by declination
    az_error = delta_ra_arcmin / cos_dec

    # Calculate altitude error component
    # DEC error maps to altitude
    alt_error = delta_dec_arcmin

    # Apply latitude correction for more accuracy
    # At the celestial pole, the relationship depends on latitude
    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)

    # For observations near the meridian:
    # az_error_corrected = az_error * sin_lat
    # alt_error stays approximately the same

    # Total error (Pythagorean)
    total_error_arcmin = math.sqrt(az_error**2 + alt_error**2)
    total_error_arcsec = total_error_arcmin * 60

    logger.debug(f"PA Error: dRA={delta_ra_arcmin:.2f}' dDEC={delta_dec_arcmin:.2f}' "
                 f"-> AZ={az_error:.2f}' ALT={alt_error:.2f}'")

    return PAError(
        az_error=az_error,
        alt_error=alt_error,
        total_error=total_error_arcsec
    )


def parse_ra_string(ra_str: str) -> Optional[float]:
    """
    *****
    Purpose: Parse RA string to degrees

    Parameters:
    str ra_str: RA in format 'HH:MM:SS' or 'HH:MM:SS.ss'

    Returns:
    float: RA in degrees, or None on parse error
    *****
    """
    try:
        # Remove any leading/trailing whitespace
        ra_str = ra_str.strip()

        # Parse HH:MM:SS format
        parts = ra_str.split(':')
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])

            # Convert to degrees (1 hour = 15 degrees)
            ra_degrees = (hours + minutes / 60.0 + seconds / 3600.0) * 15.0
            return ra_degrees

        # Try parsing as decimal hours
        ra_hours = float(ra_str)
        return ra_hours * 15.0

    except Exception as e:
        logger.error(f"Cannot parse RA '{ra_str}': {e}")
        return None


def parse_dec_string(dec_str: str) -> Optional[float]:
    """
    *****
    Purpose: Parse DEC string to degrees

    Parameters:
    str dec_str: DEC in format 'sDD*MM:SS' or 'sDD:MM:SS'

    Returns:
    float: DEC in degrees, or None on parse error
    *****
    """
    try:
        # Remove any leading/trailing whitespace
        dec_str = dec_str.strip()

        # Determine sign
        sign = 1
        if dec_str[0] == '-':
            sign = -1
            dec_str = dec_str[1:]
        elif dec_str[0] == '+':
            dec_str = dec_str[1:]

        # Handle different separators (* or :)
        dec_str = dec_str.replace('*', ':').replace("'", ':').replace('"', '')

        parts = dec_str.split(':')
        if len(parts) >= 2:
            degrees = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2]) if len(parts) > 2 else 0.0

            dec_degrees = sign * (degrees + minutes / 60.0 + seconds / 3600.0)
            return dec_degrees

        # Try parsing as decimal degrees
        return float(dec_str) * sign

    except Exception as e:
        logger.error(f"Cannot parse DEC '{dec_str}': {e}")
        return None


def calculate_correction(pa_error: PAError, invert_az: bool = True) -> Tuple[float, float]:
    """
    *****
    Purpose: Calculate the mount correction commands to apply

    Parameters:
    PAError pa_error: The calculated PA error
    bool invert_az: Whether to invert azimuth (OAT convention)

    Returns:
    Tuple[float, float]: (az_correction, alt_correction) in arcminutes
    *****
    """
    # Apply the correction (negative of error to compensate)
    az_correction = -pa_error.az_error
    alt_correction = pa_error.alt_error  # ALT is typically not inverted

    # OAT AutoPA inverts the azimuth correction
    if invert_az:
        az_correction = -az_correction

    return (az_correction, alt_correction)


def estimate_iterations(current_error: float, target_accuracy: float = None) -> int:
    """
    *****
    Purpose: Estimate number of iterations to reach target accuracy

    Parameters:
    float current_error: Current total error in arcseconds
    float target_accuracy: Target accuracy in arcseconds

    Returns:
    int: Estimated number of iterations
    *****
    """
    if target_accuracy is None:
        target_accuracy = config.TARGET_ACCURACY

    if current_error <= target_accuracy:
        return 0

    # Assume each iteration reduces error by ~50-70%
    # Use 60% as estimate
    reduction_factor = 0.6
    iterations = 0
    error = current_error

    while error > target_accuracy and iterations < 20:
        error *= reduction_factor
        iterations += 1

    return iterations
