"""
*****
Purpose: Camera client supporting V4L2 (USB/Pi cameras) and INDI cameras

Parameters:
None - Configuration loaded from config.py

Returns:
CameraClient class for image capture
*****
"""

import os
import time
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("OpenCV not available - V4L2 camera support disabled")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("Pillow not available - image processing limited")

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False
    # Not a warning - only available on Pi with camera module

import config

logger = logging.getLogger(__name__)


class CameraClient:
    """
    *****
    Purpose: Camera client for image capture with multiple backend support

    Parameters:
    None - uses config.py settings

    Returns:
    CameraClient instance
    *****
    """

    def __init__(self):
        self.camera_type = config.CAMERA_TYPE
        self.device = config.CAMERA_DEVICE
        self.capture_dir = Path(config.CAPTURE_DIR)
        self._camera = None
        self._connected = False

        # Ensure capture directory exists
        self.capture_dir.mkdir(parents=True, exist_ok=True)

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, camera_type: Optional[str] = None, device: Optional[str] = None) -> bool:
        """
        *****
        Purpose: Connect to camera

        Parameters:
        str camera_type: Optional override - 'v4l2', 'picamera', or 'indi'
        str device: Optional device path override

        Returns:
        bool: True if connection successful
        *****
        """
        if self._connected:
            logger.warning("Camera already connected")
            return True

        if camera_type:
            self.camera_type = camera_type
        if device:
            self.device = device

        if self.camera_type == 'v4l2':
            return self._connect_v4l2()
        elif self.camera_type == 'picamera':
            return self._connect_picamera()
        elif self.camera_type == 'indi':
            return self._connect_indi()
        else:
            logger.error(f"Unknown camera type: {self.camera_type}")
            return False

    def _connect_v4l2(self) -> bool:
        """Connect to V4L2 camera (USB webcam)."""
        if not CV2_AVAILABLE:
            logger.error("OpenCV not available for V4L2")
            return False

        try:
            # Parse device - could be /dev/video0 or just 0
            if isinstance(self.device, str) and self.device.startswith('/dev/video'):
                device_id = int(self.device.replace('/dev/video', ''))
            else:
                device_id = int(self.device)

            self._camera = cv2.VideoCapture(device_id)

            if not self._camera.isOpened():
                logger.error(f"Cannot open camera device {self.device}")
                return False

            # Set resolution if possible
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

            self._connected = True
            logger.info(f"Connected to V4L2 camera: {self.device}")
            return True

        except Exception as e:
            logger.error(f"V4L2 connection error: {e}")
            return False

    def _connect_picamera(self) -> bool:
        """Connect to Raspberry Pi camera module."""
        if not PICAMERA_AVAILABLE:
            logger.error("picamera2 not available")
            return False

        try:
            self._camera = Picamera2()
            config = self._camera.create_still_configuration()
            self._camera.configure(config)
            self._camera.start()
            time.sleep(1)  # Allow camera to warm up

            self._connected = True
            logger.info("Connected to Pi Camera")
            return True

        except Exception as e:
            logger.error(f"Pi Camera connection error: {e}")
            return False

    def _connect_indi(self) -> bool:
        """Connect to INDI camera."""
        # TODO: Implement INDI camera support
        logger.error("INDI camera support not yet implemented")
        return False

    def disconnect(self):
        """
        *****
        Purpose: Disconnect from camera

        Parameters:
        None

        Returns:
        None
        *****
        """
        if self._camera:
            if self.camera_type == 'v4l2' and CV2_AVAILABLE:
                self._camera.release()
            elif self.camera_type == 'picamera' and PICAMERA_AVAILABLE:
                self._camera.stop()
                self._camera.close()
            self._camera = None

        self._connected = False
        logger.info("Camera disconnected")

    def capture(self, exposure: float = None, gain: int = None,
                filename: str = None) -> Optional[str]:
        """
        *****
        Purpose: Capture an image

        Parameters:
        float exposure: Exposure time in seconds (if supported)
        int gain: Camera gain (if supported)
        str filename: Optional output filename

        Returns:
        str: Path to captured image file, or None on error
        *****
        """
        if not self._connected:
            logger.error("Camera not connected")
            return None

        if exposure is None:
            exposure = config.DEFAULT_EXPOSURE
        if gain is None:
            gain = config.DEFAULT_GAIN

        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.png"

        filepath = self.capture_dir / filename

        try:
            if self.camera_type == 'v4l2':
                return self._capture_v4l2(filepath, exposure, gain)
            elif self.camera_type == 'picamera':
                return self._capture_picamera(filepath, exposure, gain)
            elif self.camera_type == 'indi':
                return self._capture_indi(filepath, exposure, gain)

        except Exception as e:
            logger.error(f"Capture error: {e}")
            return None

    def _capture_v4l2(self, filepath: Path, exposure: float, gain: int) -> Optional[str]:
        """Capture frame from V4L2 camera."""
        # Set exposure if possible (may not work on all cameras)
        self._camera.set(cv2.CAP_PROP_EXPOSURE, exposure * 1000)  # ms
        self._camera.set(cv2.CAP_PROP_GAIN, gain)

        # For longer exposures, we might need multiple frame grabs
        # to allow the camera to adjust
        if exposure > 0.5:
            # Grab a few frames to let camera adjust
            for _ in range(5):
                self._camera.grab()
            time.sleep(exposure)

        ret, frame = self._camera.read()

        if not ret or frame is None:
            logger.error("Failed to capture frame")
            return None

        # Save image
        cv2.imwrite(str(filepath), frame)
        logger.info(f"Captured image: {filepath}")
        return str(filepath)

    def _capture_picamera(self, filepath: Path, exposure: float, gain: int) -> Optional[str]:
        """Capture image from Pi Camera."""
        # Set exposure and gain
        self._camera.set_controls({
            "ExposureTime": int(exposure * 1000000),  # microseconds
            "AnalogueGain": gain / 100.0
        })
        time.sleep(exposure + 0.5)  # Wait for exposure

        # Capture
        self._camera.capture_file(str(filepath))
        logger.info(f"Captured image: {filepath}")
        return str(filepath)

    def _capture_indi(self, filepath: Path, exposure: float, gain: int) -> Optional[str]:
        """Capture image from INDI camera."""
        logger.error("INDI camera capture not implemented")
        return None

    def get_preview(self, scale: float = 0.25) -> Optional[bytes]:
        """
        *****
        Purpose: Get a low-resolution preview image as JPEG bytes

        Parameters:
        float scale: Scale factor (0.25 = quarter resolution)

        Returns:
        bytes: JPEG image data, or None on error
        *****
        """
        if not self._connected:
            return None

        try:
            if self.camera_type == 'v4l2':
                ret, frame = self._camera.read()
                if not ret or frame is None:
                    return None

                # Resize
                height, width = frame.shape[:2]
                new_size = (int(width * scale), int(height * scale))
                small = cv2.resize(frame, new_size)

                # Encode as JPEG
                _, jpeg = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 70])
                return jpeg.tobytes()

            elif self.camera_type == 'picamera':
                # Capture to memory
                import io
                stream = io.BytesIO()
                self._camera.capture_file(stream, format='jpeg')
                return stream.getvalue()

        except Exception as e:
            logger.error(f"Preview error: {e}")

        return None

    def list_devices(self) -> list:
        """
        *****
        Purpose: List available camera devices

        Parameters:
        None

        Returns:
        list: List of available device paths
        *****
        """
        devices = []

        # Check V4L2 devices
        if CV2_AVAILABLE:
            for i in range(10):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    devices.append(f"/dev/video{i}")
                    cap.release()

        # Check Pi Camera
        if PICAMERA_AVAILABLE:
            try:
                cam = Picamera2()
                cam.close()
                devices.append("picamera")
            except:
                pass

        return devices


# Singleton instance
_camera_client = None

def get_camera_client() -> CameraClient:
    """
    *****
    Purpose: Get singleton camera client instance

    Parameters:
    None

    Returns:
    CameraClient: Singleton instance
    *****
    """
    global _camera_client
    if _camera_client is None:
        _camera_client = CameraClient()
    return _camera_client
