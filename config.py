"""
*****
Purpose: Configuration settings for OAT Web Polar Alignment

Parameters:
None

Returns:
None
*****
"""

# INDI Server Settings
INDI_HOST = "localhost"
INDI_PORT = 7624
TELESCOPE_NAME = "LX200 GPS"  # INDI driver name for OAT

# Camera Settings
# Options: "opencv" (cross-platform), "v4l2" (Linux), "picamera" (RPi), "indi"
# "opencv" uses cv2.VideoCapture - works on Windows, macOS, and Linux
CAMERA_TYPE = "opencv"
CAMERA_DEVICE = "0"  # Device index (0, 1, 2...) or Linux path (/dev/video0)
INDI_CAMERA_NAME = "CCD Simulator"  # For INDI camera

# Plate Solver Settings
SOLVER = "astap"  # Options: "astap", "astrometry"
ASTAP_PATH = "/usr/bin/astap_cli"
ASTROMETRY_PATH = "/usr/bin/solve-field"
SOLVER_TIMEOUT = 60  # seconds

# Default capture settings
DEFAULT_EXPOSURE = 2.0  # seconds
DEFAULT_GAIN = 100

# Polar Alignment Settings
TARGET_ACCURACY = 60  # arcseconds - stop auto-align when error < this
MAX_ITERATIONS = 20  # Maximum alignment attempts before giving up
SETTLE_TIME = 1.0  # seconds to wait after movement

# Site Location (for PA calculations)
# Set these to your observing location
LATITUDE = 40.0  # degrees, positive = North
LONGITUDE = -111.0  # degrees, positive = East

# Jog Control Defaults
AZ_STEP_DEFAULT = 5.0  # arcminutes
ALT_STEP_DEFAULT = 5.0  # arcminutes

# Web Server Settings
WEB_HOST = "0.0.0.0"  # Listen on all interfaces
WEB_PORT = 5000
DEBUG = False

# File Paths
CAPTURE_DIR = "/tmp/oat-pa-captures"
