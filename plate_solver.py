"""
*****
Purpose: Plate solver wrapper for ASTAP and astrometry.net

Parameters:
None - Configuration loaded from config.py

Returns:
PlateSolver class for astronomical image solving
*****
"""

import os
import subprocess
import logging
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

try:
    from astropy.io import fits
    from astropy.wcs import WCS
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    ASTROPY_AVAILABLE = True
except ImportError:
    ASTROPY_AVAILABLE = False
    logging.warning("astropy not available - WCS parsing limited")

import config

logger = logging.getLogger(__name__)


@dataclass
class SolveResult:
    """
    *****
    Purpose: Container for plate solve results

    Parameters:
    float ra: Right Ascension in degrees
    float dec: Declination in degrees
    float rotation: Field rotation in degrees
    float pixel_scale: Arcseconds per pixel
    float fov_width: Field of view width in degrees
    float fov_height: Field of view height in degrees
    str solver: Which solver produced this result

    Returns:
    SolveResult instance
    *****
    """
    ra: float  # degrees
    dec: float  # degrees
    rotation: float  # degrees
    pixel_scale: float  # arcsec/pixel
    fov_width: float  # degrees
    fov_height: float  # degrees
    solver: str

    def ra_hours(self) -> float:
        """Convert RA to hours."""
        return self.ra / 15.0

    def ra_hms(self) -> str:
        """Format RA as HH:MM:SS."""
        hours = self.ra / 15.0
        h = int(hours)
        m = int((hours - h) * 60)
        s = ((hours - h) * 60 - m) * 60
        return f"{h:02d}:{m:02d}:{s:05.2f}"

    def dec_dms(self) -> str:
        """Format DEC as sDD:MM:SS."""
        sign = '+' if self.dec >= 0 else '-'
        dec_abs = abs(self.dec)
        d = int(dec_abs)
        m = int((dec_abs - d) * 60)
        s = ((dec_abs - d) * 60 - m) * 60
        return f"{sign}{d:02d}:{m:02d}:{s:04.1f}"


class PlateSolver:
    """
    *****
    Purpose: Plate solver supporting ASTAP and astrometry.net backends

    Parameters:
    None - uses config.py settings

    Returns:
    PlateSolver instance
    *****
    """

    def __init__(self):
        self.solver = config.SOLVER
        self.astap_path = config.ASTAP_PATH
        self.astrometry_path = config.ASTROMETRY_PATH
        self.timeout = config.SOLVER_TIMEOUT

    def solve(self, image_path: str, fov_hint: float = None,
              ra_hint: float = None, dec_hint: float = None) -> Optional[SolveResult]:
        """
        *****
        Purpose: Plate solve an image

        Parameters:
        str image_path: Path to image file (FITS, PNG, JPEG)
        float fov_hint: Estimated field of view in degrees
        float ra_hint: Hint RA in degrees (speeds up solving)
        float dec_hint: Hint DEC in degrees (speeds up solving)

        Returns:
        SolveResult: Solve result or None if failed
        *****
        """
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error(f"Image not found: {image_path}")
            return None

        if self.solver == 'astap':
            return self._solve_astap(image_path, fov_hint, ra_hint, dec_hint)
        elif self.solver == 'astrometry':
            return self._solve_astrometry(image_path, fov_hint, ra_hint, dec_hint)
        else:
            logger.error(f"Unknown solver: {self.solver}")
            return None

    def _solve_astap(self, image_path: Path, fov_hint: float,
                     ra_hint: float, dec_hint: float) -> Optional[SolveResult]:
        """Solve using ASTAP."""
        # Build command
        cmd = [
            self.astap_path,
            '-f', str(image_path),
            '-r', '30',  # Search radius in degrees
            '-z', '0',   # Downsample (0 = auto)
        ]

        # Add FOV hint if provided
        if fov_hint:
            cmd.extend(['-fov', str(fov_hint)])

        # Add position hint if provided
        if ra_hint is not None and dec_hint is not None:
            cmd.extend(['-ra', str(ra_hint / 15.0)])  # ASTAP uses hours
            cmd.extend(['-spd', str(dec_hint + 90)])  # South Pole Distance

        logger.info(f"Running ASTAP: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            # Check for .wcs file (indicates success)
            wcs_path = image_path.with_suffix('.wcs')
            ini_path = image_path.with_suffix('.ini')

            if wcs_path.exists():
                return self._parse_astap_result(wcs_path, ini_path)
            else:
                logger.warning(f"ASTAP failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"ASTAP timeout after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"ASTAP error: {e}")
            return None

    def _parse_astap_result(self, wcs_path: Path, ini_path: Path) -> Optional[SolveResult]:
        """Parse ASTAP output files."""
        try:
            # Parse INI file for additional info
            ini_data = {}
            if ini_path.exists():
                with open(ini_path, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            ini_data[key.strip()] = value.strip()

            # Parse WCS file
            if ASTROPY_AVAILABLE:
                with fits.open(wcs_path) as hdul:
                    header = hdul[0].header
                    wcs = WCS(header)

                    # Get center coordinates
                    naxis1 = header.get('NAXIS1', header.get('IMAGEW', 1920))
                    naxis2 = header.get('NAXIS2', header.get('IMAGEH', 1080))
                    center = wcs.pixel_to_world(naxis1 / 2, naxis2 / 2)

                    ra = center.ra.deg
                    dec = center.dec.deg

                    # Get rotation and scale
                    cd1_1 = header.get('CD1_1', 0)
                    cd1_2 = header.get('CD1_2', 0)
                    cd2_1 = header.get('CD2_1', 0)
                    cd2_2 = header.get('CD2_2', 0)

                    import math
                    pixel_scale = math.sqrt(cd1_1**2 + cd2_1**2) * 3600  # arcsec/pixel
                    rotation = math.degrees(math.atan2(cd2_1, cd1_1))

                    fov_width = naxis1 * pixel_scale / 3600
                    fov_height = naxis2 * pixel_scale / 3600

                    return SolveResult(
                        ra=ra,
                        dec=dec,
                        rotation=rotation,
                        pixel_scale=pixel_scale,
                        fov_width=fov_width,
                        fov_height=fov_height,
                        solver='astap'
                    )
            else:
                # Parse without astropy (basic parsing)
                crval1 = float(ini_data.get('CRVAL1', 0))
                crval2 = float(ini_data.get('CRVAL2', 0))

                return SolveResult(
                    ra=crval1,
                    dec=crval2,
                    rotation=0,
                    pixel_scale=0,
                    fov_width=0,
                    fov_height=0,
                    solver='astap'
                )

        except Exception as e:
            logger.error(f"Error parsing ASTAP result: {e}")
            return None

    def _solve_astrometry(self, image_path: Path, fov_hint: float,
                          ra_hint: float, dec_hint: float) -> Optional[SolveResult]:
        """Solve using astrometry.net."""
        # Build command
        cmd = [
            self.astrometry_path,
            str(image_path),
            '--no-plots',
            '--overwrite',
            '--no-remove-lines',
            '--uniformize', '0',
        ]

        # Add scale hint if FOV provided
        if fov_hint:
            low = fov_hint * 0.8
            high = fov_hint * 1.2
            cmd.extend(['--scale-low', str(low), '--scale-high', str(high)])
            cmd.extend(['--scale-units', 'degwidth'])

        # Add position hint
        if ra_hint is not None and dec_hint is not None:
            cmd.extend(['--ra', str(ra_hint)])
            cmd.extend(['--dec', str(dec_hint)])
            cmd.extend(['--radius', '30'])

        logger.info(f"Running astrometry.net: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            # Check for .solved file
            solved_path = image_path.with_suffix('.solved')
            wcs_path = image_path.with_suffix('.wcs')

            if solved_path.exists() and wcs_path.exists():
                return self._parse_astrometry_result(wcs_path)
            else:
                logger.warning(f"astrometry.net failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"astrometry.net timeout after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"astrometry.net error: {e}")
            return None

    def _parse_astrometry_result(self, wcs_path: Path) -> Optional[SolveResult]:
        """Parse astrometry.net WCS file."""
        if not ASTROPY_AVAILABLE:
            logger.error("astropy required for parsing astrometry.net results")
            return None

        try:
            with fits.open(wcs_path) as hdul:
                header = hdul[0].header
                wcs = WCS(header)

                naxis1 = header.get('NAXIS1', header.get('IMAGEW', 1920))
                naxis2 = header.get('NAXIS2', header.get('IMAGEH', 1080))
                center = wcs.pixel_to_world(naxis1 / 2, naxis2 / 2)

                ra = center.ra.deg
                dec = center.dec.deg

                cd1_1 = header.get('CD1_1', 0)
                cd2_1 = header.get('CD2_1', 0)

                import math
                pixel_scale = math.sqrt(cd1_1**2 + cd2_1**2) * 3600
                rotation = math.degrees(math.atan2(cd2_1, cd1_1))

                fov_width = naxis1 * pixel_scale / 3600
                fov_height = naxis2 * pixel_scale / 3600

                return SolveResult(
                    ra=ra,
                    dec=dec,
                    rotation=rotation,
                    pixel_scale=pixel_scale,
                    fov_width=fov_width,
                    fov_height=fov_height,
                    solver='astrometry'
                )

        except Exception as e:
            logger.error(f"Error parsing astrometry.net result: {e}")
            return None

    def set_solver(self, solver: str):
        """
        *****
        Purpose: Change the active solver

        Parameters:
        str solver: 'astap' or 'astrometry'

        Returns:
        None
        *****
        """
        if solver in ['astap', 'astrometry']:
            self.solver = solver
            logger.info(f"Solver set to: {solver}")
        else:
            logger.error(f"Unknown solver: {solver}")


# Singleton instance
_plate_solver = None

def get_plate_solver() -> PlateSolver:
    """
    *****
    Purpose: Get singleton plate solver instance

    Parameters:
    None

    Returns:
    PlateSolver: Singleton instance
    *****
    """
    global _plate_solver
    if _plate_solver is None:
        _plate_solver = PlateSolver()
    return _plate_solver
