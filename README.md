# OAT Web PA — OpenAstroTracker Web Polar Alignment

A mobile-friendly web application for automated polar alignment of the OpenAstroTracker (OAT) mount. Runs on a Raspberry Pi as a background service, accessible from any browser on your local network.

![OAT Web PA Screenshot](docs/screenshot.png)
*Screenshot placeholder — replace with actual UI screenshot*

---

## Table of Contents

- [Features](#features)
- [Hardware Requirements](#hardware-requirements)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Option A: Debian Package (Recommended)](#option-a-debian-package-recommended)
  - [Option B: Manual Installation](#option-b-manual-installation)
- [Configuration](#configuration)
- [Service Management](#service-management)
- [First-Run Walkthrough](#first-run-walkthrough)
- [UI Reference](#ui-reference)
- [Auto-Align Workflow](#auto-align-workflow)
- [Building the Package](#building-the-package)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Automated polar alignment** — hands-free iterative correction loop with configurable target accuracy
- **Real-time feedback** — live polar alignment (PA) error display (azimuth, altitude, total) via WebSocket push
- **Plate solving** — supports ASTAP Command Line Interface (CLI) and astrometry.net (`solve-field`)
- **Flexible camera support** — OpenCV, Video for Linux 2 (V4L2), and Instrument-Neutral Distributed Interface (INDI) backends; configurable per site
- **Mount control** — LX200 protocol over serial (Universal Serial Bus (USB)/UART) via INDI or direct serial
- **RA/DEC jogging** — on-screen directional pad with hold-to-slew and four speed presets
- **Manual AZ/ALT trim** — fine polar axis adjustment in arcminutes directly from the UI
- **Named location presets** — save multiple observing sites by name; one tap to switch between them
- **GPS auto-population** — reads site coordinates from the mount via LX200 on builds with a GPS module
- **Mobile-first UI** — works on phones and tablets; no app install required
- **Runs as a system service** — auto-starts on boot, survives reboots
- **Single-page application** — no page reloads; all state pushed over Socket.IO

---

## Hardware Requirements

| Component | Requirement |
|-----------|-------------|
| Raspberry Pi | Model 3B+ or 4 (Pi 4 recommended for faster plate solving) |
| Camera | USB webcam, Raspberry Pi Camera Module, or V4L2-compatible astronomy camera |
| Mount | OpenAstroTracker with USB or UART serial connection |
| Storage | 8 GB microSD minimum; 16 GB recommended if storing ASTAP star databases on-device |
| Network | Wi-Fi or Ethernet — any device on the same network can access the UI |

The camera should be physically attached to the OAT and aimed at the polar region. A wide-field lens (e.g., 16 mm or shorter) helps when the mount is significantly out of alignment.

---

## Prerequisites

### System Packages

Install the required system packages on the Raspberry Pi before installing OAT Web PA:

```bash
sudo apt-get update
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    python3-opencv \
    libindi-dev
```

> **Note on OpenCV:** If you are running headless (no display), install `python3-opencv-headless` instead of `python3-opencv` to avoid pulling in graphical dependencies.

### ASTAP Plate Solver

ASTAP is the recommended plate solver. **It must be installed separately** — a fresh install without ASTAP will fail every plate solve with no useful error message.

> **Note:** The ASTAP CLI is a separate download from the GUI application. Download the CLI zip, not the GUI installer.

1. Go to [www.hnsky.org/astap.htm](https://www.hnsky.org/astap.htm) and download the Raspberry Pi CLI zip (look for "command-line version" → Raspberry Pi 32-bit or 64-bit depending on your OS)

2. Extract and install the binary:
   ```bash
   unzip astap_command-line_version_Pi*.zip
   sudo mv astap_cli /usr/local/bin/
   sudo chmod +x /usr/local/bin/astap_cli
   ```

3. Update `ASTAP_PATH` in your config to match:
   ```python
   ASTAP_PATH = "/usr/local/bin/astap_cli"
   ```

4. Download at least one star database from the same page. **G05** and **W08** are the current recommended databases for wide-field setups:
   - **G05** — good general-purpose database for most polar alignment fields of view
   - **W08** — wider field coverage, useful if your camera has a very wide FOV or the mount is far off-pole
   - **H18 is obsolete** — if you have it installed, it can be safely removed

5. Verify the CLI is available:
   ```bash
   /usr/local/bin/astap_cli --help
   ```

> **Important:** ASTAP requires at least one star database to be installed before it can solve any image. The binary alone is not sufficient.

### astrometry.net (Optional Alternative)

If you prefer astrometry.net as the plate solver:

```bash
sudo apt-get install -y astrometry.net
```

You will also need to download index files for your camera's field of view. See the [astrometry.net documentation](http://astrometry.net/doc/readme.html) for index file selection.

---

## Installation

### Option A: Debian Package (Recommended)

The `.deb` package handles service user creation, virtual environment setup, and systemd integration automatically.

**Step 1 — Transfer the package to the Pi**

Copy `oat-web-pa_1.0.0-1_all.deb` to the Raspberry Pi (via `scp`, USB drive, or direct download).

**Step 2 — Install**

```bash
sudo dpkg -i oat-web-pa_1.0.0-1_all.deb
sudo apt-get install -f   # resolves any missing dependencies
```

**What the package does:**

- Installs application files to `/opt/oat-web-pa/`
- Creates a dedicated system user `oat-pa`, added to the `dialout` group (serial access) and `video` group (camera access)
- Creates a Python virtual environment at `/opt/oat-web-pa/venv/` and installs all Python dependencies
- Places a local configuration override file at `/etc/oat-web-pa/config.py`
- Installs and enables the `oat-web-pa` systemd service

**Step 3 — Configure your site location**

You can set your observing location either via the config file or the web UI:

- **Config file** (permanent default): edit `/etc/oat-web-pa/config.py` and set `LATITUDE` / `LONGITUDE`
- **Web UI** (per-session or saved preset): use the Location Settings panel after connecting — see [Location Settings Panel](#location-settings-panel)

If your OAT has a GPS module, the **Use Mount GPS** button in the Location Settings panel will read coordinates directly from the mount after connecting.

See the [Configuration](#configuration) section for all available settings.

**Step 4 — Start the service**

```bash
sudo systemctl start oat-web-pa
sudo systemctl status oat-web-pa
```

**Step 5 — Open the web interface**

Open a browser on any device on the same network and navigate to:

```
http://<raspberry-pi-ip-address>:5000
```

To find the Pi's IP address: `hostname -I`

---

### Option B: Manual Installation

Use this method if you want to run OAT Web PA without the `.deb` package, or on a non-Debian system.

```bash
# Clone or copy the project files
sudo mkdir -p /opt/oat-web-pa
sudo cp -r . /opt/oat-web-pa/
cd /opt/oat-web-pa

# Create and populate the virtual environment
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# Install the systemd service
sudo cp oat-web-pa.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now oat-web-pa
```

If you are not running as root, ensure your user is in the `dialout` and `video` groups:

```bash
sudo usermod -a -G dialout,video $USER
# Log out and back in for group membership to take effect
```

---

## Configuration

### Configuration File Location

| Install method | Config file |
|----------------|-------------|
| `.deb` package | `/etc/oat-web-pa/config.py` (overrides) |
| Manual | `/opt/oat-web-pa/config.py` |

Settings in `/etc/oat-web-pa/config.py` override defaults without modifying the installed application files, making upgrades safe.

### Key Settings

```python
# -------------------------------------------------------
# Site Location (REQUIRED for accurate PA calculations)
# -------------------------------------------------------
LATITUDE = 40.0       # Decimal degrees North (negative for South)
LONGITUDE = -111.0    # Decimal degrees East (negative for West)

# -------------------------------------------------------
# Camera
# -------------------------------------------------------
CAMERA_TYPE = "opencv"   # Options: "opencv", "v4l2", "indi"
CAMERA_DEVICE = "0"      # Device index (e.g., 0) or path (e.g., /dev/video0)

# -------------------------------------------------------
# Plate Solver
# -------------------------------------------------------
SOLVER = "astap"                     # Options: "astap", "astrometry"
ASTAP_PATH = "/usr/local/bin/astap_cli"    # Path to ASTAP CLI binary

# -------------------------------------------------------
# Mount (overridable at runtime via the UI)
# -------------------------------------------------------
# Default serial port — can be changed from the Connection panel
# SERIAL_PORT = "/dev/ttyACM0"

# -------------------------------------------------------
# Web Server
# -------------------------------------------------------
WEB_PORT = 5000
WEB_HOST = "0.0.0.0"    # Bind on all interfaces; change to 127.0.0.1 for local-only

# -------------------------------------------------------
# Alignment Loop
# -------------------------------------------------------
TARGET_ACCURACY = 60    # Stop when total PA error is below this value (arcseconds)
MAX_ITERATIONS = 20     # Maximum correction iterations before stopping
DEFAULT_EXPOSURE = 2.0  # Default camera exposure (seconds)
DEFAULT_GAIN = 100      # Default camera gain
```

### Finding Your Latitude and Longitude

Use Google Maps (right-click your location and copy the coordinates) or a GPS app. Enter latitude as a positive number for North and negative for South. Enter longitude as positive for East and negative for West.

---

## Service Management

```bash
# Start the service
sudo systemctl start oat-web-pa

# Stop the service
sudo systemctl stop oat-web-pa

# Restart after configuration changes
sudo systemctl restart oat-web-pa

# Enable auto-start on boot
sudo systemctl enable oat-web-pa

# Disable auto-start
sudo systemctl disable oat-web-pa

# Check current status
sudo systemctl status oat-web-pa

# Stream live logs
journalctl -u oat-web-pa -f

# View the last 100 log lines
journalctl -u oat-web-pa -n 100
```

---

## First-Run Walkthrough

This section walks through getting your first successful polar alignment correction from a fresh install.

### 1. Confirm the service is running

```bash
sudo systemctl status oat-web-pa
```

You should see `active (running)`. If not, check the logs: `journalctl -u oat-web-pa -f`

### 2. Open the web interface

On your phone or any browser on the same network:

```
http://<pi-ip>:5000
```

The Pi's IP address can be found by running `hostname -I` on the Pi.

### 3. Connect to the mount

In the **Connection** panel, enter the serial port for your OAT (typically `/dev/ttyACM0` for USB). Click **Connect**. The mount position panel should update with live RA/DEC values within a few seconds.

> If the connection fails, see [Serial Port Permission Denied](#serial-port-permission-denied) in the Troubleshooting section.

### 4. Point the camera at Polaris

Physically aim the camera attached to your OAT toward the north celestial pole (near Polaris for Northern Hemisphere observers). The field of view must include enough stars for the plate solver to work — at minimum 10–20 stars are needed.

### 5. Test a single capture and solve

In the **Capture and Solve** panel:

1. Set an exposure time (start with 2 seconds)
2. Set gain (start with 100; increase if stars are too faint)
3. Click **Capture and Solve**

Wait 10–60 seconds for the image to be captured, plate-solved, and the PA error calculated. The result appears in the **PA Error** panel showing azimuth error, altitude error, and total error in arcseconds.

> If the solve fails, see [Plate Solve Fails](#plate-solve-fails) in the Troubleshooting section.

### 6. Run the auto-align loop

Once a single solve succeeds:

1. Set your target accuracy in the **Auto Alignment** panel (default 60 arcseconds is a good starting point)
2. Click **Start Auto-Align**
3. Watch the PA error panel update in real time as the loop captures, solves, and applies corrections

The loop stops automatically when the error drops below your target, or when the maximum iteration count is reached. See [Auto-Align Workflow](#auto-align-workflow) for details.

---

## UI Reference

The single-page interface is organized into panels. All panels update in real time without page reloads.

### Connection Panel

- **Serial Port** — Enter the device path for the OAT serial connection (e.g., `/dev/ttyACM0`)
- **Connect / Disconnect** — Opens or closes the serial connection to the mount

### Mount Position Panel

Displays the current mount-reported coordinates and tracking state, updated continuously once connected.

### Capture and Solve Panel

- **Exposure** — Camera exposure time in seconds
- **Gain** — Camera gain value (sensor-dependent range)
- **Capture and Solve** — Takes a single image, runs the plate solver, and computes PA error

### PA Error Panel

Displays the calculated polar alignment error after each solve:

- **AZ Error** — Azimuth axis error in arcminutes
- **ALT Error** — Altitude axis error in arcminutes
- **Total Error** — Combined error in arcseconds, with a progress bar relative to target accuracy

### Auto Alignment Panel

- **Target Accuracy** — The loop stops when total error falls below this value (arcseconds)
- **Start Auto-Align** — Starts the iterative correction loop
- **Stop** — Halts the loop at the end of the current iteration

### RA/DEC Jog Panel

An on-screen directional pad for moving the mount in right ascension and declination:

- **Speed selector** — Guide / Center / Find / Slew
- **Hold to slew** — Press and hold a direction button to move; release to stop

> **Note:** The RA/DEC jog moves the mount via its stepper motors for framing/centering. This is different from the AZ/ALT panel below.

### AZ/ALT Jog Panel

Fine adjustment controls for the polar axis itself (the physical azimuth and altitude adjustment bolts on the OAT):

- Sends correction commands to the mount in arcminute increments
- Use this for manual fine-tuning between auto-align iterations if needed

### Location Settings Panel

Manages the observing site coordinates used by the PA error calculation. Accurate coordinates are required for correct AZ/ALT error decomposition.

- **Saved Sites dropdown** — select a previously saved location preset
- **Load / Delete** — apply or remove the selected preset
- **Site Name** — label for the current coordinates (used when saving)
- **Latitude / Longitude** — decimal degrees; positive = North/East, negative = South/West
- **Use Mount GPS** — reads coordinates directly from the mount via LX200 commands; works on OAT builds with a GPS module connected (requires mount to be connected first)
- **Save Site** — stores the current name + coordinates as a named preset; presets persist across reboots
- **Apply** — applies the current latitude/longitude to the active session without saving

> **Switching between observing sites:** Load a preset → Apply. The active coordinates take effect immediately for the current session. They are not written back to the config file unless you edit `/etc/oat-web-pa/config.py` directly.

---

## Auto-Align Workflow

When you click **Start Auto-Align**, the application runs the following loop:

1. **Capture** — The camera takes an image at the configured exposure and gain
2. **Plate solve** — ASTAP (or astrometry.net) identifies the star field and returns the actual right ascension/declination of the image center
3. **Calculate error** — The solved coordinates are compared to the mount-reported position; the difference is decomposed into azimuth and altitude components using the site latitude
4. **Apply correction** — Correction commands are sent to the OAT via the LX200 protocol to adjust the polar axis
5. **Settle** — The application waits a configurable settle time (default 1 second) for the mount to complete the movement
6. **Check convergence** — If the total error is below the target accuracy, the loop ends successfully; if the maximum iteration count has been reached, the loop ends with a warning; otherwise, go to step 1

All loop state (current iteration, PA error at each step, pass/fail) is pushed to every connected browser over WebSocket in real time. You can monitor progress from multiple devices simultaneously.

### Tips for Best Results

- Start with a larger target accuracy (e.g., 120 arcseconds) to confirm the loop is converging before tightening to 60 arcseconds or less
- If the loop oscillates (error goes up and down without converging), the correction direction may need to be verified for your specific mount configuration
- A Pi 4 with ASTAP (G05 or W08 database) typically solves in 5–15 seconds per iteration; total alignment time for a mount within a few degrees of true north is usually under 5 minutes
- **Set your latitude and longitude correctly in config** — the AZ/ALT error decomposition depends on this value; wrong coordinates produce wrong correction directions

---

## Building the Package

The `.deb` package must be built on a Linux machine (or WSL on Windows).

```bash
chmod +x build-deb.sh
./build-deb.sh
```

Output: `oat-web-pa_1.0.0-1_all.deb`

The build script packages the application files into the standard Debian directory layout, sets up the `postinst` hook for virtual environment creation, and runs `dpkg-deb` to produce the installable package.

---

## Troubleshooting

### Serial Port Permission Denied

**Symptom:** Connection panel shows a permission error when connecting to `/dev/ttyACM0`

**Fix:** Add your user (or the `oat-pa` service user) to the `dialout` group:

```bash
sudo usermod -a -G dialout $USER
```

Log out and back in for the group membership to take effect. If running as the service user, the `.deb` post-install script handles this automatically; try reinstalling the package.

---

### Camera Not Found

**Symptom:** Capture fails with "camera not found" or "device open failed"

**Fix:**

1. List available video devices:
   ```bash
   ls /dev/video*
   ```
2. Update `CAMERA_DEVICE` in `/etc/oat-web-pa/config.py` to match the correct device (e.g., `/dev/video0`)
3. Ensure the `oat-pa` user is in the `video` group (the `.deb` package handles this; for manual installs: `sudo usermod -a -G video oat-pa`)
4. Restart the service after any config change:
   ```bash
   sudo systemctl restart oat-web-pa
   ```

---

### ASTAP Not Found

**Symptom:** Plate solving fails immediately with no solve result

**Fix:**

1. Verify ASTAP is installed at the expected path:
   ```bash
   ls -la /usr/bin/astap_cli
   /usr/bin/astap_cli --help
   ```
2. If installed elsewhere, update `ASTAP_PATH` in config to the correct path
3. Ensure at least one star database is installed — ASTAP requires a star database to solve:
   ```bash
   ls /usr/share/astap/
   ```
   If this directory is empty or missing, download and install a G05 or W08 database from the ASTAP website (H18 is obsolete).

---

### Plate Solve Fails

**Symptom:** Capture succeeds but solving times out or returns no match

**Common causes and fixes:**

| Cause | Fix |
|-------|-----|
| Camera not pointed near the pole | Physically aim the camera toward Polaris / the south celestial pole |
| Exposure too short | Increase `DEFAULT_EXPOSURE` in config or use the UI field; try 5–10 seconds |
| Gain too low | Increase `DEFAULT_GAIN`; faint stars may not be detected |
| Wrong star database for field of view | Download G05 or W08 from the ASTAP website (H18 is obsolete) |
| ASTAP star database not installed | Install a star database package from the ASTAP website |
| astrometry.net index files missing | Download appropriate index files for your field of view |

---

### GPS Reads Wrong Longitude Sign

**Symptom:** "Use Mount GPS" fills in a longitude with the opposite sign (e.g., `+111.0` instead of `-111.0`)

**Cause:** The standard LX200 protocol uses a West-positive longitude convention, opposite to the modern East-positive convention used in config.py. Some OAT firmware versions may handle this differently.

**Fix:** In `mount_client.py`, find `get_site_location()` and change the longitude negation line from:
```python
lon = -self._parse_lx200_angle(lon_str)
```
to:
```python
lon = self._parse_lx200_angle(lon_str)
```
(Remove the negation.) Restart the service after saving.

---

### Configuration Changes Not Taking Effect

**Symptom:** You edited `/etc/oat-web-pa/config.py` but the app still uses old values

**Fix:** Restart the service after any configuration change:

```bash
sudo systemctl restart oat-web-pa
```

---

### Service Will Not Start

**Symptom:** `systemctl status oat-web-pa` shows `failed` or the service exits immediately

**Fix:**

Check the logs for the specific error:

```bash
journalctl -u oat-web-pa -n 50 --no-pager
```

Common causes:

- **Python import error** — A required package is missing from the virtual environment. Reinstall the package or run `venv/bin/pip install -r requirements.txt` in `/opt/oat-web-pa/`
- **Port already in use** — Something else is listening on port 5000. Change `WEB_PORT` in config or stop the conflicting service
- **Config syntax error** — A typo in `/etc/oat-web-pa/config.py` prevents the application from starting. Validate the file with:
  ```bash
  python3 -c "import ast; ast.parse(open('/etc/oat-web-pa/config.py').read()); print('OK')"
  ```

---

### Web Interface Not Accessible

**Symptom:** Browser cannot reach `http://<pi-ip>:5000`

**Checks:**

1. Confirm the service is running: `sudo systemctl status oat-web-pa`
2. Confirm the Pi is listening on the port: `ss -tlnp | grep 5000`
3. Confirm you are on the same network as the Pi
4. Check if a firewall is blocking port 5000: `sudo ufw status`
   - If active and blocking: `sudo ufw allow 5000/tcp`

---

## Contributing

Contributions are welcome. Please follow the workflow in [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request:

1. Fork the repository and create a feature branch from `main`
2. Make your changes with descriptive, atomic commits
3. Test on actual hardware (Raspberry Pi + OAT) where possible
4. Open a pull request describing the change and how it was tested

For bug reports or feature requests, please open a GitHub issue.

---

## License

This project is licensed under the [MIT License](LICENSE).

OpenAstroTracker is a community project. This tool is not officially affiliated with the OpenAstroTracker organization.
