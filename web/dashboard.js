const statusEl = document.getElementById("status");
const speedEl = document.getElementById("speed");

const HOLD_INTERVAL_MS = 150;
const HEARTBEAT_INTERVAL_MS = 500;

let holdTimer = null;
let heldPath = null;
let activePointerId = null;

const updateStatus = (message) => {
  if (statusEl) {
    statusEl.textContent = message;
  }
};

const sendCommand = async (path, { suppressStatus = false } = {}) => {
  if (!suppressStatus) {
    updateStatus(`Sending ${path}...`);
  }

  try {
    const response = await fetch(path, { method: "GET", cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    if (!suppressStatus) {
      updateStatus(`Sent: ${path}`);
    }
  } catch (error) {
    updateStatus(`Command failed: ${error.message}`);
  }
};

const clearHold = ({ sendStop = true } = {}) => {
  if (holdTimer !== null) {
    window.clearInterval(holdTimer);
    holdTimer = null;
  }

  heldPath = null;
  activePointerId = null;

  if (sendStop) {
    sendCommand("/stop");
  }
};

const startHold = (button, event) => {
  const path = button.getAttribute("data-path");
  if (!path) {
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
  heldPath = path;

  if (typeof button.setPointerCapture === "function") {
    try {
      button.setPointerCapture(event.pointerId);
    } catch (_err) {
      // no-op
    }
  }

  sendCommand(path);

  if (holdTimer !== null) {
    window.clearInterval(holdTimer);
  }

  holdTimer = window.setInterval(() => {
    if (heldPath) {
      sendCommand(heldPath, { suppressStatus: true });
    }
  }, HOLD_INTERVAL_MS);
};

for (const button of document.querySelectorAll("button[data-path]")) {
  const isDriveButton = button.classList.contains("control--drive") && button.getAttribute("data-path") !== "/stop";

  if (isDriveButton) {
    button.addEventListener("pointerdown", (event) => startHold(button, event));
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
      const path = button.getAttribute("data-path");
      if (path) {
        sendCommand(path);
      }
    });
  }
}

if (speedEl) {
  speedEl.addEventListener("change", () => {
    sendCommand(`/speed/${speedEl.value}`);
  });
}

document.addEventListener("pointerup", () => clearHold({ sendStop: true }));
document.addEventListener("pointercancel", () => clearHold({ sendStop: true }));
document.addEventListener("touchend", () => clearHold({ sendStop: true }), { passive: true });
document.addEventListener("touchcancel", () => clearHold({ sendStop: true }), { passive: true });
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearHold({ sendStop: true });
  }
});
window.addEventListener("pagehide", () => clearHold({ sendStop: true }));

window.setInterval(() => {
  if (!document.hidden) {
    sendCommand("/heartbeat", { suppressStatus: true });
  }
}, HEARTBEAT_INTERVAL_MS);
