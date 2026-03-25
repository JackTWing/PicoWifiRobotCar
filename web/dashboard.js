const statusEl = document.getElementById("status");
const speedEl = document.getElementById("speed");
const connectionEl = document.getElementById("connection");
const diagnosticsEl = document.getElementById("diagnostics");
const robotTargetEl = document.getElementById("robot-target");
const retryBtn = document.getElementById("connect-retry");

const STREAM_INTERVAL_MS = 180;
const IDLE_PING_INTERVAL_MS = 850;
const OFFLINE_THRESHOLD_MS = 3000;

let streamTimer = null;
let idleTimer = null;
let heldCmd = null;
let activePointerId = null;
let seq = 0;
let lastAckAt = 0;
let reconnectingSince = 0;
let lastSentSignature = "";

const trimSlash = (value) => value.replace(/\/+$/, "");

const getRobotBaseUrl = () => {
  const params = new URLSearchParams(window.location.search);
  const queryRobot = params.get("robot") || params.get("host") || params.get("robotHost");
  if (queryRobot) {
    const normalized = queryRobot.startsWith("http") ? queryRobot : `http://${queryRobot}`;
    return trimSlash(normalized);
  }

  const stored = window.localStorage.getItem("robotBaseUrl");
  if (stored) {
    return trimSlash(stored);
  }

  const currentHost = window.location.hostname;
  const privateIPv4Pattern = /^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)/;
  if (currentHost === "192.168.4.1" || privateIPv4Pattern.test(currentHost)) {
    return trimSlash(window.location.origin);
  }

  return "http://192.168.4.1";
};

const ROBOT_BASE_URL = getRobotBaseUrl();
window.localStorage.setItem("robotBaseUrl", ROBOT_BASE_URL);
if (robotTargetEl) {
  robotTargetEl.textContent = ROBOT_BASE_URL;
}

const updateStatus = (message) => {
  if (statusEl) {
    statusEl.textContent = message;
  }
};

const updateDiagnostics = (message) => {
  if (diagnosticsEl) {
    diagnosticsEl.textContent = `Diagnostics: ${message}`;
  }
};

const setConnectionState = (state) => {
  if (!connectionEl) {
    return;
  }

  connectionEl.dataset.state = state;
  connectionEl.textContent = state;
};

const nowTimestamp = () => Date.now();

const encodeCmdUrl = ({ cmd, speed, seq, timestamp }) => {
  const safeCmd = encodeURIComponent(cmd);
  return `${ROBOT_BASE_URL}/cmd/${safeCmd}/${Math.round(speed)}/${seq}/${timestamp}`;
};

const probeConnectivity = async ({ updateUi = true } = {}) => {
  const probeUrl = `${ROBOT_BASE_URL}/status?t=${Date.now()}`;

  try {
    const response = await fetch(probeUrl, { method: "GET", cache: "no-store" });
    if (!response.ok) {
      throw new Error(`status endpoint HTTP ${response.status}`);
    }

    const body = await response.text();
    if (updateUi) {
      setConnectionState("connected");
      updateDiagnostics(`reachable (${body || "status ok"})`);
      updateStatus("Robot link ready");
    }

    return true;
  } catch (statusError) {
    try {
      const heartbeatUrl = `${ROBOT_BASE_URL}/heartbeat?t=${Date.now()}`;
      const fallback = await fetch(heartbeatUrl, { method: "GET", cache: "no-store" });
      if (!fallback.ok) {
        throw new Error(`heartbeat HTTP ${fallback.status}`);
      }

      if (updateUi) {
        setConnectionState("connected");
        updateDiagnostics("reachable via /heartbeat (status endpoint unavailable)");
        updateStatus("Robot link ready");
      }
      return true;
    } catch (heartbeatError) {
      if (updateUi) {
        setConnectionState("offline");
        updateDiagnostics(`cannot reach robot host ${ROBOT_BASE_URL} (${heartbeatError.message})`);
        updateStatus("Waiting for robot connection");
      }
      return false;
    }
  }
};

const sendPacket = async ({ cmd, suppressStatus = false, force = false } = {}) => {
  const currentSpeed = speedEl ? Number(speedEl.value) : 50;
  const packet = {
    cmd,
    speed: Number.isFinite(currentSpeed) ? currentSpeed : 50,
    seq: seq,
    timestamp: nowTimestamp(),
  };

  const signature = `${packet.cmd}|${packet.speed}`;
  if (!force && signature === lastSentSignature && cmd !== "heartbeat") {
    return;
  }

  const url = encodeCmdUrl(packet);
  seq += 1;

  try {
    const response = await fetch(url, { method: "GET", cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    lastAckAt = Date.now();
    reconnectingSince = 0;
    lastSentSignature = signature;
    setConnectionState("connected");
    updateDiagnostics(`reachable at ${ROBOT_BASE_URL}`);

    if (!suppressStatus && cmd !== "heartbeat") {
      updateStatus(`Sent ${cmd} @ ${packet.speed}%`);
    }
  } catch (error) {
    const elapsedSinceAck = Date.now() - lastAckAt;
    const isOffline = elapsedSinceAck >= OFFLINE_THRESHOLD_MS;
    setConnectionState(isOffline ? "offline" : "reconnecting");
    if (!isOffline && reconnectingSince === 0) {
      reconnectingSince = Date.now();
    }
    updateDiagnostics(`cannot reach robot host ${ROBOT_BASE_URL} (${error.message})`);
    if (!suppressStatus) {
      updateStatus(`Command failed: ${error.message}`);
    }
  }
};

const clearHold = ({ sendStop = true } = {}) => {
  if (streamTimer !== null) {
    window.clearInterval(streamTimer);
    streamTimer = null;
  }

  heldCmd = null;
  activePointerId = null;

  if (sendStop) {
    sendPacket({ cmd: "stop", force: true });
  }

  ensureIdlePing();
};

const startCommandStream = (button, event) => {
  const cmd = button.getAttribute("data-cmd");
  if (!cmd) {
    return;
  }

  if (event.pointerType === "mouse" && event.button !== 0) {
    return;
  }

  event.preventDefault();
  if (activePointerId !== null && activePointerId !== event.pointerId) {
    clearHold({ sendStop: true });
  }

  activePointerId = event.pointerId;
  heldCmd = cmd;

  if (typeof button.setPointerCapture === "function") {
    try {
      button.setPointerCapture(event.pointerId);
    } catch (_err) {
      // no-op
    }
  }

  if (idleTimer !== null) {
    window.clearInterval(idleTimer);
    idleTimer = null;
  }

  sendPacket({ cmd, force: true });

  if (streamTimer !== null) {
    window.clearInterval(streamTimer);
  }

  streamTimer = window.setInterval(() => {
    if (heldCmd) {
      sendPacket({ cmd: heldCmd, suppressStatus: true, force: true });
    }
  }, STREAM_INTERVAL_MS);
};

const ensureIdlePing = () => {
  if (idleTimer !== null) {
    return;
  }

  idleTimer = window.setInterval(() => {
    if (document.hidden || heldCmd) {
      return;
    }

    sendPacket({ cmd: "heartbeat", suppressStatus: true, force: true });
  }, IDLE_PING_INTERVAL_MS);
};

for (const button of document.querySelectorAll("button[data-cmd]")) {
  const isDriveButton = button.classList.contains("control--drive") && button.getAttribute("data-cmd") !== "stop";

  if (isDriveButton) {
    button.addEventListener("pointerdown", (event) => startCommandStream(button, event));
    button.addEventListener("pointerup", () => clearHold({ sendStop: true }));
    button.addEventListener("pointercancel", () => clearHold({ sendStop: true }));
    button.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "mouse") {
        clearHold({ sendStop: true });
      }
    });
  } else {
    button.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse" && event.button !== 0) {
        return;
      }
      event.preventDefault();
      const cmd = button.getAttribute("data-cmd");
      if (cmd) {
        sendPacket({ cmd, force: true });
      }
    });
  }
}

if (retryBtn) {
  retryBtn.addEventListener("click", () => {
    updateStatus("Checking robot connectivity...");
    updateDiagnostics(`probing ${ROBOT_BASE_URL}...`);
    probeConnectivity({ updateUi: true });
  });
}

if (speedEl) {
  speedEl.addEventListener("change", () => {
    sendPacket({ cmd: heldCmd || "speed", force: true });
  });
}

document.addEventListener("pointerup", () => clearHold({ sendStop: true }));
document.addEventListener("pointercancel", () => clearHold({ sendStop: true }));
document.addEventListener("touchend", () => clearHold({ sendStop: true }), { passive: true });
document.addEventListener("touchcancel", () => clearHold({ sendStop: true }), { passive: true });
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearHold({ sendStop: true });
    setConnectionState("offline");
    return;
  }

  probeConnectivity({ updateUi: true });
  sendPacket({ cmd: "heartbeat", suppressStatus: true, force: true });
});
window.addEventListener("pagehide", () => clearHold({ sendStop: true }));

lastAckAt = Date.now();
setConnectionState("reconnecting");
updateDiagnostics(`probing ${ROBOT_BASE_URL}...`);
probeConnectivity({ updateUi: true });
sendPacket({ cmd: "heartbeat", suppressStatus: true, force: true });
ensureIdlePing();
