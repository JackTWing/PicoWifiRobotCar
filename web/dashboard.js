const statusEl = document.getElementById("status");
const speedEl = document.getElementById("speed");
const connectionEl = document.getElementById("connection");

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

const updateStatus = (message) => {
  if (statusEl) {
    statusEl.textContent = message;
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

const encodeCmdPath = ({ cmd, speed, seq, timestamp }) => {
  const safeCmd = encodeURIComponent(cmd);
  return `/cmd/${safeCmd}/${Math.round(speed)}/${seq}/${timestamp}`;
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

  const path = encodeCmdPath(packet);
  seq += 1;

  try {
    const response = await fetch(path, { method: "GET", cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    lastAckAt = Date.now();
    reconnectingSince = 0;
    lastSentSignature = signature;
    setConnectionState("connected");

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

  sendPacket({ cmd: "heartbeat", suppressStatus: true, force: true });
});
window.addEventListener("pagehide", () => clearHold({ sendStop: true }));

lastAckAt = Date.now();
setConnectionState("reconnecting");
sendPacket({ cmd: "heartbeat", suppressStatus: true, force: true });
ensureIdlePing();
