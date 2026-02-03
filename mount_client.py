"""
*****
Purpose: INDI/Serial mount client for OpenAstroTracker communication

Parameters:
None - Configuration loaded from config.py

Returns:
MountClient class for telescope control
*****
"""

import time
import logging
import threading
import re
from typing import Optional, Tuple

try:
    import PyIndi
    INDI_AVAILABLE = True
except ImportError:
    INDI_AVAILABLE = False
    logging.warning("PyIndi not available - INDI mode disabled")

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logging.warning("pyserial not available - direct serial mode disabled")

import config

logger = logging.getLogger(__name__)


class IndiClient(PyIndi.BaseClient):
    """
    *****
    Purpose: PyIndi client wrapper for receiving INDI events

    Parameters:
    None

    Returns:
    IndiClient instance
    *****
    """
    def __init__(self):
        super(IndiClient, self).__init__()
        self.device = None
        self.connected_event = threading.Event()

    def newDevice(self, d):
        logger.debug(f"New device: {d.getDeviceName()}")

    def newProperty(self, p):
        pass

    def removeProperty(self, p):
        pass

    def newBLOB(self, bp):
        pass

    def newSwitch(self, svp):
        pass

    def newNumber(self, nvp):
        pass

    def newText(self, tvp):
        pass

    def newLight(self, lvp):
        pass

    def newMessage(self, d, m):
        logger.debug(f"Message from {d.getDeviceName()}: {m}")

    def serverConnected(self):
        logger.info("Connected to INDI server")
        self.connected_event.set()

    def serverDisconnected(self, code):
        logger.warning(f"Disconnected from INDI server (code: {code})")
        self.connected_event.clear()


class MountClient:
    """
    *****
    Purpose: High-level mount control client supporting INDI and direct serial

    Parameters:
    None - uses config.py settings

    Returns:
    MountClient instance
    *****
    """

    def __init__(self):
        self.mode = None  # 'indi' or 'serial'
        self.indi_client = None
        self.serial_conn = None
        self.telescope_name = config.TELESCOPE_NAME
        self._connected = False
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, mode: str = 'serial', serial_port: str = '/dev/ttyACM0') -> bool:
        """
        *****
        Purpose: Connect to mount via INDI server or direct serial

        Parameters:
        str mode: Connection mode - 'indi' or 'serial'
        str serial_port: Serial port path for direct serial mode

        Returns:
        bool: True if connection successful
        *****
        """
        if self._connected:
            logger.warning("Already connected")
            return True

        if mode == 'indi':
            return self._connect_indi()
        elif mode == 'serial':
            return self._connect_serial(serial_port)
        else:
            logger.error(f"Unknown mode: {mode}")
            return False

    def _connect_indi(self) -> bool:
        """Connect via INDI server."""
        if not INDI_AVAILABLE:
            logger.error("PyIndi not available")
            return False

        try:
            self.indi_client = IndiClient()
            self.indi_client.setServer(config.INDI_HOST, config.INDI_PORT)

            if not self.indi_client.connectServer():
                logger.error(f"Cannot connect to INDI server at {config.INDI_HOST}:{config.INDI_PORT}")
                return False

            # Wait for connection
            self.indi_client.connected_event.wait(timeout=5.0)

            # Get telescope device
            device = self.indi_client.getDevice(self.telescope_name)
            timeout = 10
            while not device and timeout > 0:
                time.sleep(0.5)
                device = self.indi_client.getDevice(self.telescope_name)
                timeout -= 0.5

            if not device:
                logger.error(f"Telescope '{self.telescope_name}' not found")
                return False

            self.mode = 'indi'
            self._connected = True
            logger.info(f"Connected to {self.telescope_name} via INDI")
            return True

        except Exception as e:
            logger.error(f"INDI connection error: {e}")
            return False

    def _connect_serial(self, port: str) -> bool:
        """Connect via direct serial port."""
        if not SERIAL_AVAILABLE:
            logger.error("pyserial not available")
            return False

        try:
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=19200,
                timeout=2.0,
                write_timeout=2.0
            )
            time.sleep(0.5)  # Allow connection to stabilize

            # Verify connection with product name query
            response = self._serial_command(":GVP#")
            if response and "OpenAstro" in response:
                self.mode = 'serial'
                self._connected = True
                logger.info(f"Connected to OAT via serial {port}: {response}")
                return True
            else:
                logger.error(f"Unexpected response: {response}")
                self.serial_conn.close()
                return False

        except Exception as e:
            logger.error(f"Serial connection error: {e}")
            if self.serial_conn:
                self.serial_conn.close()
            return False

    def disconnect(self):
        """
        *****
        Purpose: Disconnect from mount

        Parameters:
        None

        Returns:
        None
        *****
        """
        if self.mode == 'indi' and self.indi_client:
            self.indi_client.disconnectServer()
            self.indi_client = None
        elif self.mode == 'serial' and self.serial_conn:
            self.serial_conn.close()
            self.serial_conn = None

        self.mode = None
        self._connected = False
        logger.info("Disconnected from mount")

    def send_command(self, command: str, expect_response: bool = True) -> Optional[str]:
        """
        *****
        Purpose: Send Meade LX200 command to mount

        Parameters:
        str command: Meade command (e.g., ':GR#', ':MAZ+5.0#')
        bool expect_response: Whether to wait for response

        Returns:
        str: Response string or None if no response/error
        *****
        """
        if not self._connected:
            logger.error("Not connected")
            return None

        with self._lock:
            if self.mode == 'serial':
                return self._serial_command(command, expect_response)
            elif self.mode == 'indi':
                return self._indi_command(command, expect_response)

        return None

    def _serial_command(self, command: str, expect_response: bool = True) -> Optional[str]:
        """Send command via serial port."""
        try:
            # Clear input buffer
            self.serial_conn.reset_input_buffer()

            # Send command
            self.serial_conn.write(command.encode('ascii'))

            if not expect_response:
                return ""

            # Read response until # terminator
            response = ""
            start_time = time.time()
            while time.time() - start_time < 2.0:
                if self.serial_conn.in_waiting:
                    char = self.serial_conn.read(1).decode('ascii', errors='ignore')
                    if char == '#':
                        break
                    response += char
                else:
                    time.sleep(0.01)

            return response

        except Exception as e:
            logger.error(f"Serial command error: {e}")
            return None

    def _indi_command(self, command: str, expect_response: bool = True) -> Optional[str]:
        """Send command via INDI (requires driver support)."""
        # Note: This requires the INDI driver to support command passthrough
        # For LX200-compatible mounts, we may need to disconnect INDI and use serial
        logger.warning("INDI command passthrough not fully implemented - use serial mode")
        return None

    # High-level mount control methods

    def get_position(self) -> Tuple[Optional[str], Optional[str]]:
        """
        *****
        Purpose: Get current RA/DEC position

        Parameters:
        None

        Returns:
        Tuple[str, str]: (RA string 'HH:MM:SS', DEC string 'sDD*MM:SS') or (None, None)
        *****
        """
        ra = self.send_command(":GR#")
        dec = self.send_command(":GD#")
        return (ra, dec)

    def get_status(self) -> Optional[str]:
        """
        *****
        Purpose: Get full mount status string

        Parameters:
        None

        Returns:
        str: Status string from :GX# command
        *****
        """
        return self.send_command(":GX#")

    def is_slewing(self) -> bool:
        """
        *****
        Purpose: Check if mount is currently slewing

        Parameters:
        None

        Returns:
        bool: True if slewing
        *****
        """
        response = self.send_command(":GIS#")
        return response == "1"

    def is_tracking(self) -> bool:
        """
        *****
        Purpose: Check if tracking is enabled

        Parameters:
        None

        Returns:
        bool: True if tracking
        *****
        """
        response = self.send_command(":GIT#")
        return response == "1"

    def is_adjusting(self) -> bool:
        """
        *****
        Purpose: Check if AZ/ALT motors are currently moving

        Parameters:
        None

        Returns:
        bool: True if AZ or ALT is adjusting
        *****
        """
        status = self.get_status()
        if status:
            # Status format: "State,--T--,..." where position 4,5 are AZ,ALT flags
            parts = status.split(',')
            if len(parts) >= 2:
                motion = parts[1]
                if len(motion) >= 5:
                    # Position 3 is AZ (Z/z/-), Position 4 is ALT (A/a/-)
                    az_moving = motion[3] != '-'
                    alt_moving = motion[4] != '-'
                    return az_moving or alt_moving
        return False

    def start_slew(self, direction: str):
        """
        *****
        Purpose: Start continuous slew in direction

        Parameters:
        str direction: 'n', 's', 'e', 'w'

        Returns:
        None
        *****
        """
        direction = direction.lower()
        if direction in ['n', 's', 'e', 'w']:
            self.send_command(f":M{direction}#", expect_response=False)
        else:
            logger.error(f"Invalid direction: {direction}")

    def stop_slew(self, direction: str = 'a'):
        """
        *****
        Purpose: Stop slewing in direction (or all)

        Parameters:
        str direction: 'n', 's', 'e', 'w', or 'a' for all

        Returns:
        None
        *****
        """
        direction = direction.lower()
        if direction == 'a':
            self.send_command(":Q#", expect_response=False)
        elif direction in ['n', 's', 'e', 'w']:
            self.send_command(f":Q{direction}#", expect_response=False)

    def set_slew_rate(self, rate: str):
        """
        *****
        Purpose: Set slew speed

        Parameters:
        str rate: 'S' (slew/fastest), 'M' (find), 'C' (center), 'G' (guide/slowest)

        Returns:
        None
        *****
        """
        rate = rate.upper()
        if rate in ['S', 'M', 'C', 'G']:
            self.send_command(f":R{rate}#", expect_response=False)

    def move_azimuth(self, arcminutes: float):
        """
        *****
        Purpose: Move azimuth by specified amount

        Parameters:
        float arcminutes: Amount to move (positive = right, negative = left)

        Returns:
        None
        *****
        """
        cmd = f":MAZ{arcminutes:+.2f}#"
        self.send_command(cmd, expect_response=False)
        logger.info(f"Moving AZ by {arcminutes:.2f} arcmin")

    def move_altitude(self, arcminutes: float):
        """
        *****
        Purpose: Move altitude by specified amount

        Parameters:
        float arcminutes: Amount to move (positive = up, negative = down)

        Returns:
        None
        *****
        """
        cmd = f":MAL{arcminutes:+.2f}#"
        self.send_command(cmd, expect_response=False)
        logger.info(f"Moving ALT by {arcminutes:.2f} arcmin")

    def set_tracking(self, enabled: bool):
        """
        *****
        Purpose: Enable or disable tracking

        Parameters:
        bool enabled: True to enable tracking

        Returns:
        None
        *****
        """
        cmd = ":MT1#" if enabled else ":MT0#"
        self.send_command(cmd)

    def get_az_alt_position(self) -> Tuple[Optional[int], Optional[int]]:
        """
        *****
        Purpose: Get AZ/ALT stepper positions

        Parameters:
        None

        Returns:
        Tuple[int, int]: (AZ steps, ALT steps) or (None, None)
        *****
        """
        response = self.send_command(":XGAA#")
        if response:
            parts = response.split('|')
            if len(parts) >= 2:
                try:
                    return (int(parts[0]), int(parts[1]))
                except ValueError:
                    pass
        return (None, None)

    def home_az_alt(self):
        """
        *****
        Purpose: Move AZ and ALT to home position

        Parameters:
        None

        Returns:
        None
        *****
        """
        self.send_command(":MAAH#", expect_response=False)


# Singleton instance
_mount_client = None

def get_mount_client() -> MountClient:
    """
    *****
    Purpose: Get singleton mount client instance

    Parameters:
    None

    Returns:
    MountClient: Singleton instance
    *****
    """
    global _mount_client
    if _mount_client is None:
        _mount_client = MountClient()
    return _mount_client
