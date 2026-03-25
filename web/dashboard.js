const statusEl = document.getElementById("status");
const speedEl = document.getElementById("speed");

const updateStatus = (message) => {
  if (statusEl) {
    statusEl.textContent = message;
  }
};

const sendCommand = async (path) => {
  updateStatus(`Sending ${path}...`);

  try {
    const response = await fetch(path, { method: "GET" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    updateStatus(`Sent: ${path}`);
  } catch (error) {
    updateStatus(`Command failed: ${error.message}`);
  }
};

for (const button of document.querySelectorAll("button[data-path]")) {
  button.addEventListener("click", () => {
    const path = button.getAttribute("data-path");
    if (path) {
      sendCommand(path);
    }
  });
}

if (speedEl) {
  speedEl.addEventListener("change", () => {
    sendCommand(`/speed/${speedEl.value}`);
  });
}
