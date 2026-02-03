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
    btnDisconnect: document.getElementById('btn-disconnect')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initWebSocket();
    initEventListeners();
    pollStatus();
    statusPollInterval = setInterval(pollStatus, 2000);
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
        moveAz(-parseFloat(elements.azStep.value));
    });
    document.getElementById('btn-az-plus').addEventListener('click', () => {
        moveAz(parseFloat(elements.azStep.value));
    });
    document.getElementById('btn-alt-minus').addEventListener('click', () => {
        moveAlt(-parseFloat(elements.altStep.value));
    });
    document.getElementById('btn-alt-plus').addEventListener('click', () => {
        moveAlt(parseFloat(elements.altStep.value));
    });

    // Capture
    elements.btnCapture.addEventListener('click', capture);
    elements.btnSolve.addEventListener('click', solve);
    elements.btnCaptureSolve.addEventListener('click', captureAndSolve);
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
            alert(`Connection failed: ${result.error}`);
        }
    } catch (e) {
        alert(`Connection error: ${e.message}`);
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
    elements.btnCapture.disabled = true;
    elements.btnCapture.textContent = 'Capturing...';

    try {
        const result = await apiCall('capture', 'POST', {
            exposure: parseFloat(elements.exposure.value),
            gain: parseInt(elements.gain.value)
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

    await capture();
    await solve();

    elements.btnCaptureSolve.disabled = false;
    elements.btnCaptureSolve.textContent = 'Capture & Solve';
}

// Auto-align
async function toggleAutoAlign() {
    if (alignmentRunning) {
        await apiCall('auto-align/stop', 'POST');
        addStatusLog('Auto-align stopped', 'info');
    } else {
        const targetAccuracy = parseFloat(elements.targetAccuracy.value);
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
