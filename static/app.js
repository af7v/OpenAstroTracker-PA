/**
 * OAT Polar Alignment Web Interface
 * Frontend JavaScript
 */

// WebSocket connection
let socket = null;
let statusPollInterval = null;
let alignmentRunning = false;

// DOM Elements
const elements = {
    // Status
    mountStatus: document.getElementById('mount-status'),
    mountLabel: document.getElementById('mount-label'),
    mountRa: document.getElementById('mount-ra'),
    mountDec: document.getElementById('mount-dec'),
    trackingIndicator: document.getElementById('tracking-indicator'),
    trackingLabel: document.getElementById('tracking-label'),

    // PA Error
    paAz: document.getElementById('pa-az'),
    paAlt: document.getElementById('pa-alt'),
    paTotal: document.getElementById('pa-total'),
    paProgressFill: document.getElementById('pa-progress-fill'),
    paStatus: document.getElementById('pa-status'),

    // Controls
    btnAutoAlign: document.getElementById('btn-auto-align'),
    targetAccuracy: document.getElementById('target-accuracy'),
    alignStatus: document.getElementById('align-status'),

    // Jog
    slewRate: document.getElementById('slew-rate'),
    azStep: document.getElementById('az-step'),
    altStep: document.getElementById('alt-step'),

    // Capture
    exposure: document.getElementById('exposure'),
    gain: document.getElementById('gain'),
    btnCapture: document.getElementById('btn-capture'),
    btnSolve: document.getElementById('btn-solve'),
    btnCaptureSolve: document.getElementById('btn-capture-solve'),
    solveResult: document.getElementById('solve-result'),

    // Connection
    serialPort: document.getElementById('serial-port'),
    btnConnect: document.getElementById('btn-connect'),
    btnDisconnect: document.getElementById('btn-disconnect'),

    // Location settings
    locationSelect: document.getElementById('location-select'),
    siteName: document.getElementById('site-name'),
    latitude: document.getElementById('latitude'),
    longitude: document.getElementById('longitude'),
    btnLoadLocation: document.getElementById('btn-load-location'),
    btnDeleteLocation: document.getElementById('btn-delete-location'),
    btnUseGps: document.getElementById('btn-use-gps'),
    btnSaveSite: document.getElementById('btn-save-site'),
    btnApplyLocation: document.getElementById('btn-apply-location'),
    locationStatus: document.getElementById('location-status'),
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    initEventListeners();
    pollStatus();
    statusPollInterval = setInterval(pollStatus, 2000);
    loadLocations();
});

// WebSocket Setup
function initWebSocket() {
    socket = io();

    socket.on('connect', () => {
        console.log('WebSocket connected');
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
    });

    socket.on('status', (data) => {
        addStatusLog(data.message, data.level);
    });

    socket.on('status_update', (data) => {
        updateDisplay(data);
    });
}

// Event Listeners
function initEventListeners() {
    // Connection
    elements.btnConnect.addEventListener('click', connect);
    elements.btnDisconnect.addEventListener('click', disconnect);

    // Auto-align
    elements.btnAutoAlign.addEventListener('click', toggleAutoAlign);

    // RA/DEC Jog - D-Pad
    document.querySelectorAll('.dpad-btn').forEach(btn => {
        btn.addEventListener('mousedown', () => startSlew(btn.dataset.dir));
        btn.addEventListener('mouseup', () => stopSlew(btn.dataset.dir));
        btn.addEventListener('mouseleave', () => stopSlew(btn.dataset.dir));

        // Touch support
        btn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            startSlew(btn.dataset.dir);
        });
        btn.addEventListener('touchend', (e) => {
            e.preventDefault();
            stopSlew(btn.dataset.dir);
        });
    });

    // Slew rate change
    elements.slewRate.addEventListener('change', () => {
        setSlewRate(elements.slewRate.value);
    });

    // AZ/ALT Jog
    document.getElementById('btn-az-minus').addEventListener('click', () => {
        const step = validateNumericInput(elements.azStep.value, 0.1, 60, 'AZ step');
        if (step === null) return;
        moveAz(-step);
    });
    document.getElementById('btn-az-plus').addEventListener('click', () => {
        const step = validateNumericInput(elements.azStep.value, 0.1, 60, 'AZ step');
        if (step === null) return;
        moveAz(step);
    });
    document.getElementById('btn-alt-minus').addEventListener('click', () => {
        const step = validateNumericInput(elements.altStep.value, 0.1, 60, 'ALT step');
        if (step === null) return;
        moveAlt(-step);
    });
    document.getElementById('btn-alt-plus').addEventListener('click', () => {
        const step = validateNumericInput(elements.altStep.value, 0.1, 60, 'ALT step');
        if (step === null) return;
        moveAlt(step);
    });

    // Capture
    elements.btnCapture.addEventListener('click', capture);
    elements.btnSolve.addEventListener('click', solve);
    elements.btnCaptureSolve.addEventListener('click', captureAndSolve);

    // Location settings
    elements.btnLoadLocation.addEventListener('click', loadSelectedLocation);
    elements.btnDeleteLocation.addEventListener('click', deleteLocation);
    elements.btnUseGps.addEventListener('click', useGps);
    elements.btnSaveSite.addEventListener('click', saveSite);
    elements.btnApplyLocation.addEventListener('click', applyLocation);
    elements.locationSelect.addEventListener('change', () => {
        if (elements.locationSelect.value) loadSelectedLocation();
    });
}

function validateNumericInput(value, min, max, fieldName) {
    const num = parseFloat(value);
    if (isNaN(num) || num < min || num > max) {
        addStatusLog(`Invalid ${fieldName}: must be between ${min} and ${max}`, 'error');
        return null;
    }
    return num;
}

// API Functions
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (data) {
        options.body = JSON.stringify(data);
    }
    const response = await fetch(`/api/${endpoint}`, options);
    return response.json();
}

async function connect() {
    const serialPort = elements.serialPort.value;
    elements.btnConnect.disabled = true;
    elements.btnConnect.textContent = 'Connecting...';

    try {
        const result = await apiCall('connect', 'POST', { serial_port: serialPort });
        if (result.error) {
            addStatusLog(`Connection failed: ${result.error}`, 'error');
        }
    } catch (e) {
        addStatusLog(`Connection error: ${e.message}`, 'error');
    }

    elements.btnConnect.disabled = false;
    elements.btnConnect.textContent = 'Connect';
    pollStatus();
}

async function disconnect() {
    await apiCall('disconnect', 'POST');
    pollStatus();
}

async function pollStatus() {
    try {
        const status = await apiCall('status');
        updateDisplay(status);
    } catch (e) {
        console.error('Status poll error:', e);
    }
}

function updateDisplay(status) {
    // Connection status
    if (status.mount_connected) {
        elements.mountStatus.classList.add('connected');
        elements.mountStatus.classList.remove('disconnected');
        elements.mountLabel.textContent = 'Mount: Connected';
    } else {
        elements.mountStatus.classList.remove('connected');
        elements.mountStatus.classList.add('disconnected');
        elements.mountLabel.textContent = 'Mount: Disconnected';
    }

    // Position
    elements.mountRa.textContent = status.mount_ra || '--:--:--';
    elements.mountDec.textContent = status.mount_dec || "--°--'--\"";

    // Tracking
    if (status.tracking) {
        elements.trackingIndicator.classList.add('on');
        elements.trackingIndicator.classList.remove('off');
        elements.trackingLabel.textContent = 'Tracking: On';
    } else {
        elements.trackingIndicator.classList.remove('on');
        elements.trackingIndicator.classList.add('off');
        elements.trackingLabel.textContent = 'Tracking: Off';
    }

    // PA Error
    if (status.pa_error) {
        elements.paAz.textContent = status.pa_error.az.toFixed(2);
        elements.paAlt.textContent = status.pa_error.alt.toFixed(2);
        elements.paTotal.textContent = status.pa_error.total.toFixed(1);

        // Progress bar (0-300 arcsec scale, inverted for progress)
        const targetAccuracy = parseFloat(elements.targetAccuracy.value);
        const maxError = 300;
        const progress = Math.max(0, 100 - (status.pa_error.total / maxError * 100));
        elements.paProgressFill.style.width = `${progress}%`;
        elements.paProgressFill.setAttribute('aria-valuenow', Math.round(progress));

        if (status.pa_error.aligned) {
            elements.paStatus.textContent = 'Aligned!';
            elements.paStatus.style.color = '#4ecca3';
        } else {
            elements.paStatus.textContent = `Target: <${targetAccuracy}"`;
            elements.paStatus.style.color = '';
        }
    }

    // Alignment status
    alignmentRunning = status.alignment_running;
    if (alignmentRunning) {
        elements.btnAutoAlign.textContent = 'Stop Auto-Align';
        elements.btnAutoAlign.classList.add('running');
    } else {
        elements.btnAutoAlign.textContent = 'Start Auto-Align';
        elements.btnAutoAlign.classList.remove('running');
    }
}

// Slew functions
async function startSlew(direction) {
    if (direction === 'a') {
        await apiCall('slew', 'POST', { direction: 'a', action: 'stop' });
    } else {
        await apiCall('slew', 'POST', { direction: direction, action: 'start' });
    }
}

async function stopSlew(direction) {
    if (direction !== 'a') {
        await apiCall('slew', 'POST', { direction: direction, action: 'stop' });
    }
}

async function setSlewRate(rate) {
    await apiCall('slew-rate', 'POST', { rate: rate });
}

// AZ/ALT movement
async function moveAz(arcmin) {
    await apiCall('move-az', 'POST', { arcmin: arcmin });
    addStatusLog(`Moving AZ by ${arcmin > 0 ? '+' : ''}${arcmin.toFixed(1)}'`, 'info');
}

async function moveAlt(arcmin) {
    await apiCall('move-alt', 'POST', { arcmin: arcmin });
    addStatusLog(`Moving ALT by ${arcmin > 0 ? '+' : ''}${arcmin.toFixed(1)}'`, 'info');
}

// Capture functions
async function capture() {
    const exposure = validateNumericInput(elements.exposure.value, 0.1, 60, 'exposure');
    if (exposure === null) return;
    const gain = validateNumericInput(elements.gain.value, 0, 1000, 'gain');
    if (gain === null) return;

    elements.btnCapture.disabled = true;
    elements.btnCapture.textContent = 'Capturing...';

    try {
        const result = await apiCall('capture', 'POST', {
            exposure: exposure,
            gain: Math.round(gain)
        });

        if (result.filepath) {
            addStatusLog(`Captured: ${result.filepath}`, 'success');
        } else {
            addStatusLog(`Capture failed: ${result.error}`, 'error');
        }
    } catch (e) {
        addStatusLog(`Capture error: ${e.message}`, 'error');
    }

    elements.btnCapture.disabled = false;
    elements.btnCapture.textContent = 'Capture';
}

async function solve() {
    elements.btnSolve.disabled = true;
    elements.btnSolve.textContent = 'Solving...';

    try {
        const result = await apiCall('solve', 'POST');

        if (result.solved) {
            const html = `
                <strong>Solved:</strong> RA ${result.solved.ra_hms}, DEC ${result.solved.dec_dms}<br>
                ${result.pa_error ? `<strong>PA Error:</strong> AZ ${result.pa_error.az.toFixed(2)}', ALT ${result.pa_error.alt.toFixed(2)}', Total ${result.pa_error.total.toFixed(1)}"` : ''}
            `;
            elements.solveResult.innerHTML = html;
            elements.solveResult.classList.add('visible');
            addStatusLog('Plate solve successful', 'success');
        } else {
            addStatusLog(`Solve failed: ${result.error}`, 'error');
        }
    } catch (e) {
        addStatusLog(`Solve error: ${e.message}`, 'error');
    }

    elements.btnSolve.disabled = false;
    elements.btnSolve.textContent = 'Solve';
    pollStatus();
}

async function captureAndSolve() {
    elements.btnCaptureSolve.disabled = true;
    elements.btnCaptureSolve.textContent = 'Working...';
    elements.btnCapture.disabled = true;
    elements.btnSolve.disabled = true;

    await capture();
    await solve();

    elements.btnCaptureSolve.disabled = false;
    elements.btnCaptureSolve.textContent = 'Capture & Solve';
    elements.btnCapture.disabled = false;
    elements.btnSolve.disabled = false;
}

// Auto-align
async function toggleAutoAlign() {
    if (alignmentRunning) {
        await apiCall('auto-align/stop', 'POST');
        addStatusLog('Auto-align stopped', 'info');
    } else {
        const targetAccuracy = validateNumericInput(elements.targetAccuracy.value, 1, 600, 'target accuracy');
        if (targetAccuracy === null) return;
        await apiCall('auto-align/start', 'POST', { target_accuracy: targetAccuracy });
    }
    pollStatus();
}

// Status log
function addStatusLog(message, level = 'info') {
    const p = document.createElement('p');
    p.className = level;
    p.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    elements.alignStatus.appendChild(p);
    elements.alignStatus.scrollTop = elements.alignStatus.scrollHeight;

    // Keep only last 20 messages
    while (elements.alignStatus.children.length > 20) {
        elements.alignStatus.removeChild(elements.alignStatus.firstChild);
    }
}

// Location presets
async function loadLocations() {
    try {
        const result = await apiCall('locations');
        const select = elements.locationSelect;
        const current = select.value;
        while (select.options.length > 1) select.remove(1);
        for (const name of Object.keys(result)) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        }
        if (current) select.value = current;
    } catch (e) {
        console.error('Failed to load locations:', e);
    }
}

async function loadSelectedLocation() {
    const name = elements.locationSelect.value;
    if (!name) return;
    try {
        const locations = await apiCall('locations');
        if (locations[name]) {
            elements.latitude.value = locations[name].latitude;
            elements.longitude.value = locations[name].longitude;
            elements.siteName.value = name;
            setLocationStatus(`Loaded: ${name}`, 'success');
        }
    } catch (e) {
        setLocationStatus('Failed to load site', 'error');
    }
}

async function saveSite() {
    const name = elements.siteName.value.trim();
    const lat = parseFloat(elements.latitude.value);
    const lon = parseFloat(elements.longitude.value);
    if (!name) { setLocationStatus('Enter a site name first', 'error'); return; }
    if (isNaN(lat) || lat < -90 || lat > 90) { setLocationStatus('Invalid latitude (−90 to 90)', 'error'); return; }
    if (isNaN(lon) || lon < -180 || lon > 180) { setLocationStatus('Invalid longitude (−180 to 180)', 'error'); return; }
    const result = await apiCall('locations', 'POST', { name, latitude: lat, longitude: lon });
    if (result.error) {
        setLocationStatus(`Save failed: ${result.error}`, 'error');
        return;
    }
    setLocationStatus(`Saved: ${name}`, 'success');
    loadLocations();
}

async function deleteLocation() {
    const name = elements.locationSelect.value;
    if (!name) return;
    try {
        const result = await apiCall(`locations/${encodeURIComponent(name)}`, 'DELETE');
        if (result.error) {
            setLocationStatus(`Delete failed: ${result.error}`, 'error');
            return;
        }
        setLocationStatus(`Deleted: ${name}`, 'info');
        elements.siteName.value = '';
        loadLocations();
    } catch (e) {
        setLocationStatus(`Delete error: ${e.message}`, 'error');
    }
}

async function applyLocation() {
    const lat = parseFloat(elements.latitude.value);
    const lon = parseFloat(elements.longitude.value);
    if (isNaN(lat) || lat < -90 || lat > 90) { setLocationStatus('Invalid latitude', 'error'); return; }
    if (isNaN(lon) || lon < -180 || lon > 180) { setLocationStatus('Invalid longitude', 'error'); return; }
    const result = await apiCall('location/apply', 'POST', { latitude: lat, longitude: lon });
    if (result.success) {
        setLocationStatus(`Applied: ${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`, 'success');
    } else {
        setLocationStatus(`Apply failed: ${result.error}`, 'error');
    }
}

async function useGps() {
    elements.btnUseGps.disabled = true;
    elements.btnUseGps.textContent = 'Reading GPS...';
    try {
        const result = await apiCall('location/from-mount');
        if (result.latitude !== undefined) {
            elements.latitude.value = result.latitude.toFixed(4);
            elements.longitude.value = result.longitude.toFixed(4);
            setLocationStatus(`GPS: ${result.latitude.toFixed(4)}°N, ${result.longitude.toFixed(4)}°E`, 'success');
        } else {
            setLocationStatus(`GPS read failed: ${result.error}`, 'error');
        }
    } catch (e) {
        setLocationStatus(`GPS error: ${e.message}`, 'error');
    }
    elements.btnUseGps.disabled = false;
    elements.btnUseGps.textContent = 'Use Mount GPS';
}

function setLocationStatus(message, level = 'info') {
    elements.locationStatus.textContent = message;
    elements.locationStatus.className = `location-status ${level}`;
}
