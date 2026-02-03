"""
*****
Purpose: Flask web server for OAT Polar Alignment Interface

Parameters:
None - Configuration loaded from config.py

Returns:
Flask application
*****
"""

import os
import time
import logging
import threading
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

import config
from mount_client import get_mount_client
from camera_client import get_camera_client
from plate_solver import get_plate_solver
from pa_calculator import (
    calculate_pa_error, calculate_correction,
    parse_ra_string, parse_dec_string, PAError
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'oat-pa-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Global state
alignment_running = False
alignment_thread = None
last_pa_error = None
last_solve_result = None


# ============================================================================
# Routes - Pages
# ============================================================================

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


# ============================================================================
# Routes - API
# ============================================================================

@app.route('/api/status')
def api_status():
    """
    *****
    Purpose: Get current mount and system status

    Parameters:
    None

    Returns:
    JSON: Status object
    *****
    """
    mount = get_mount_client()
    camera = get_camera_client()

    status = {
        'mount_connected': mount.connected,
        'camera_connected': camera.connected,
        'alignment_running': alignment_running,
        'target_accuracy': config.TARGET_ACCURACY,
    }

    if mount.connected:
        ra, dec = mount.get_position()
        status['mount_ra'] = ra
        status['mount_dec'] = dec
        status['tracking'] = mount.is_tracking()
        status['slewing'] = mount.is_slewing()
        status['adjusting'] = mount.is_adjusting()

    if last_pa_error:
        status['pa_error'] = {
            'az': last_pa_error.az_error,
            'alt': last_pa_error.alt_error,
            'total': last_pa_error.total_error,
            'aligned': last_pa_error.is_aligned()
        }

    if last_solve_result:
        status['last_solve'] = {
            'ra': last_solve_result.ra,
            'dec': last_solve_result.dec,
            'ra_hms': last_solve_result.ra_hms(),
            'dec_dms': last_solve_result.dec_dms(),
            'solver': last_solve_result.solver
        }

    return jsonify(status)


@app.route('/api/connect', methods=['POST'])
def api_connect():
    """
    *****
    Purpose: Connect to mount and camera

    Parameters:
    JSON body:
        serial_port: Optional serial port path
        camera_device: Optional camera device

    Returns:
    JSON: Success/error response
    *****
    """
    data = request.get_json() or {}

    mount = get_mount_client()
    camera = get_camera_client()

    # Connect mount
    serial_port = data.get('serial_port', '/dev/ttyACM0')
    if not mount.connected:
        if not mount.connect(mode='serial', serial_port=serial_port):
            return jsonify({'error': 'Failed to connect to mount'}), 500

    # Connect camera
    camera_device = data.get('camera_device', config.CAMERA_DEVICE)
    if not camera.connected:
        if not camera.connect(device=camera_device):
            return jsonify({'error': 'Failed to connect to camera'}), 500

    return jsonify({'success': True, 'message': 'Connected'})


@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    """Disconnect from mount and camera."""
    global alignment_running

    alignment_running = False

    mount = get_mount_client()
    camera = get_camera_client()

    mount.disconnect()
    camera.disconnect()

    return jsonify({'success': True, 'message': 'Disconnected'})


@app.route('/api/slew', methods=['POST'])
def api_slew():
    """
    *****
    Purpose: Start or stop slewing

    Parameters:
    JSON body:
        direction: 'n', 's', 'e', 'w'
        action: 'start' or 'stop'

    Returns:
    JSON: Success/error response
    *****
    """
    data = request.get_json() or {}
    direction = data.get('direction', '').lower()
    action = data.get('action', 'start')

    mount = get_mount_client()
    if not mount.connected:
        return jsonify({'error': 'Mount not connected'}), 400

    if action == 'start':
        mount.start_slew(direction)
    else:
        mount.stop_slew(direction)

    return jsonify({'success': True})


@app.route('/api/slew-rate', methods=['POST'])
def api_slew_rate():
    """Set slew rate."""
    data = request.get_json() or {}
    rate = data.get('rate', 'M')

    mount = get_mount_client()
    if not mount.connected:
        return jsonify({'error': 'Mount not connected'}), 400

    mount.set_slew_rate(rate)
    return jsonify({'success': True, 'rate': rate})


@app.route('/api/move-az', methods=['POST'])
def api_move_az():
    """Move azimuth by specified arcminutes."""
    data = request.get_json() or {}
    arcmin = float(data.get('arcmin', 0))

    mount = get_mount_client()
    if not mount.connected:
        return jsonify({'error': 'Mount not connected'}), 400

    mount.move_azimuth(arcmin)
    return jsonify({'success': True, 'arcmin': arcmin})


@app.route('/api/move-alt', methods=['POST'])
def api_move_alt():
    """Move altitude by specified arcminutes."""
    data = request.get_json() or {}
    arcmin = float(data.get('arcmin', 0))

    mount = get_mount_client()
    if not mount.connected:
        return jsonify({'error': 'Mount not connected'}), 400

    mount.move_altitude(arcmin)
    return jsonify({'success': True, 'arcmin': arcmin})


@app.route('/api/tracking', methods=['POST'])
def api_tracking():
    """Toggle tracking on/off."""
    data = request.get_json() or {}
    enabled = data.get('enabled', True)

    mount = get_mount_client()
    if not mount.connected:
        return jsonify({'error': 'Mount not connected'}), 400

    mount.set_tracking(enabled)
    return jsonify({'success': True, 'tracking': enabled})


@app.route('/api/capture', methods=['POST'])
def api_capture():
    """
    *****
    Purpose: Capture an image

    Parameters:
    JSON body:
        exposure: Exposure time in seconds
        gain: Camera gain

    Returns:
    JSON: Path to captured image
    *****
    """
    data = request.get_json() or {}
    exposure = float(data.get('exposure', config.DEFAULT_EXPOSURE))
    gain = int(data.get('gain', config.DEFAULT_GAIN))

    camera = get_camera_client()
    if not camera.connected:
        return jsonify({'error': 'Camera not connected'}), 400

    filepath = camera.capture(exposure=exposure, gain=gain)
    if filepath:
        return jsonify({'success': True, 'filepath': filepath})
    else:
        return jsonify({'error': 'Capture failed'}), 500


@app.route('/api/solve', methods=['POST'])
def api_solve():
    """
    *****
    Purpose: Plate solve the last captured image

    Parameters:
    JSON body:
        filepath: Optional path to image (uses last capture if not provided)

    Returns:
    JSON: Solve result with PA error
    *****
    """
    global last_solve_result, last_pa_error

    data = request.get_json() or {}
    filepath = data.get('filepath')

    if not filepath:
        # Find most recent capture
        import glob
        captures = glob.glob(f"{config.CAPTURE_DIR}/capture_*.png")
        if not captures:
            return jsonify({'error': 'No captured images found'}), 400
        filepath = max(captures, key=os.path.getctime)

    solver = get_plate_solver()
    mount = get_mount_client()

    # Solve the image
    result = solver.solve(filepath)
    if not result:
        return jsonify({'error': 'Plate solve failed'}), 500

    last_solve_result = result

    # Calculate PA error if mount is connected
    if mount.connected:
        ra_str, dec_str = mount.get_position()
        mount_ra = parse_ra_string(ra_str) if ra_str else None
        mount_dec = parse_dec_string(dec_str) if dec_str else None

        if mount_ra is not None and mount_dec is not None:
            last_pa_error = calculate_pa_error(
                result.ra, result.dec,
                mount_ra, mount_dec
            )

            return jsonify({
                'success': True,
                'solved': {
                    'ra': result.ra,
                    'dec': result.dec,
                    'ra_hms': result.ra_hms(),
                    'dec_dms': result.dec_dms()
                },
                'mount': {
                    'ra': mount_ra,
                    'dec': mount_dec
                },
                'pa_error': {
                    'az': last_pa_error.az_error,
                    'alt': last_pa_error.alt_error,
                    'total': last_pa_error.total_error,
                    'aligned': last_pa_error.is_aligned()
                }
            })

    return jsonify({
        'success': True,
        'solved': {
            'ra': result.ra,
            'dec': result.dec,
            'ra_hms': result.ra_hms(),
            'dec_dms': result.dec_dms()
        }
    })


@app.route('/api/auto-align/start', methods=['POST'])
def api_auto_align_start():
    """Start automated polar alignment."""
    global alignment_running, alignment_thread

    if alignment_running:
        return jsonify({'error': 'Alignment already running'}), 400

    data = request.get_json() or {}
    target_accuracy = float(data.get('target_accuracy', config.TARGET_ACCURACY))

    alignment_running = True
    alignment_thread = threading.Thread(
        target=auto_align_loop,
        args=(target_accuracy,)
    )
    alignment_thread.start()

    return jsonify({'success': True, 'message': 'Auto-align started'})


@app.route('/api/auto-align/stop', methods=['POST'])
def api_auto_align_stop():
    """Stop automated polar alignment."""
    global alignment_running

    alignment_running = False
    return jsonify({'success': True, 'message': 'Auto-align stopped'})


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update settings."""
    if request.method == 'GET':
        return jsonify({
            'target_accuracy': config.TARGET_ACCURACY,
            'default_exposure': config.DEFAULT_EXPOSURE,
            'default_gain': config.DEFAULT_GAIN,
            'solver': config.SOLVER,
            'latitude': config.LATITUDE,
            'longitude': config.LONGITUDE,
            'az_step': config.AZ_STEP_DEFAULT,
            'alt_step': config.ALT_STEP_DEFAULT,
        })
    else:
        data = request.get_json() or {}

        if 'target_accuracy' in data:
            config.TARGET_ACCURACY = float(data['target_accuracy'])
        if 'solver' in data:
            config.SOLVER = data['solver']
            get_plate_solver().set_solver(data['solver'])
        if 'latitude' in data:
            config.LATITUDE = float(data['latitude'])
        if 'longitude' in data:
            config.LONGITUDE = float(data['longitude'])

        return jsonify({'success': True})


# ============================================================================
# Auto-Align Loop
# ============================================================================

def auto_align_loop(target_accuracy: float):
    """
    *****
    Purpose: Automated polar alignment loop

    Parameters:
    float target_accuracy: Target accuracy in arcseconds

    Returns:
    None
    *****
    """
    global alignment_running, last_pa_error, last_solve_result

    mount = get_mount_client()
    camera = get_camera_client()
    solver = get_plate_solver()

    iteration = 0
    max_iterations = config.MAX_ITERATIONS

    emit_status('Auto-align started', 'info')

    while alignment_running and iteration < max_iterations:
        iteration += 1
        emit_status(f'Iteration {iteration}: Capturing...', 'info')

        # 1. Capture image
        filepath = camera.capture(exposure=config.DEFAULT_EXPOSURE)
        if not filepath:
            emit_status('Capture failed', 'error')
            time.sleep(2)
            continue

        emit_status(f'Iteration {iteration}: Solving...', 'info')

        # 2. Plate solve
        result = solver.solve(filepath)
        if not result:
            emit_status('Plate solve failed - check framing', 'warning')
            time.sleep(2)
            continue

        last_solve_result = result

        # 3. Get mount position
        ra_str, dec_str = mount.get_position()
        mount_ra = parse_ra_string(ra_str)
        mount_dec = parse_dec_string(dec_str)

        if mount_ra is None or mount_dec is None:
            emit_status('Cannot read mount position', 'error')
            time.sleep(2)
            continue

        # 4. Calculate PA error
        pa_error = calculate_pa_error(
            result.ra, result.dec,
            mount_ra, mount_dec
        )
        last_pa_error = pa_error

        emit_status(
            f'Iteration {iteration}: Error = {pa_error.total_error:.1f}" '
            f'(AZ: {pa_error.az_error:+.2f}\', ALT: {pa_error.alt_error:+.2f}\')',
            'info'
        )

        # 5. Check if aligned
        if pa_error.total_error < target_accuracy:
            emit_status(
                f'Aligned! Final error: {pa_error.total_error:.1f}"',
                'success'
            )
            break

        # 6. Apply correction
        az_correction, alt_correction = calculate_correction(pa_error)

        emit_status(f'Applying correction: AZ={az_correction:+.2f}\', ALT={alt_correction:+.2f}\'', 'info')

        mount.move_azimuth(az_correction)
        mount.move_altitude(alt_correction)

        # 7. Wait for movement to complete
        time.sleep(0.5)
        wait_count = 0
        while mount.is_adjusting() and wait_count < 30:
            time.sleep(0.5)
            wait_count += 1

        # 8. Settle time
        time.sleep(config.SETTLE_TIME)

    if iteration >= max_iterations:
        emit_status(f'Max iterations ({max_iterations}) reached', 'warning')

    alignment_running = False
    emit_status('Auto-align finished', 'info')


def emit_status(message: str, level: str = 'info'):
    """Emit status message to all connected clients."""
    socketio.emit('status', {'message': message, 'level': level})
    logger.info(f"[{level.upper()}] {message}")


# ============================================================================
# WebSocket Events
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")
    emit('connected', {'message': 'Connected to OAT PA Server'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")


@socketio.on('request_status')
def handle_request_status():
    """Handle status request from client."""
    mount = get_mount_client()

    status = {
        'connected': mount.connected,
        'alignment_running': alignment_running,
    }

    if mount.connected:
        ra, dec = mount.get_position()
        status['ra'] = ra
        status['dec'] = dec

    if last_pa_error:
        status['pa_error'] = {
            'az': last_pa_error.az_error,
            'alt': last_pa_error.alt_error,
            'total': last_pa_error.total_error
        }

    emit('status_update', status)


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    logger.info(f"Starting OAT PA Server on {config.WEB_HOST}:{config.WEB_PORT}")
    socketio.run(
        app,
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        debug=config.DEBUG
    )
