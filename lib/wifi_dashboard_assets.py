"""Embedded dashboard assets for WifiCommandServer.

Keeping HTML/CSS/JS in Python strings avoids filesystem complexity on the Pico and
keeps deployment to just code.py + lib/.
"""

HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Pico Robot Dashboard</title>
  <link rel=\"stylesheet\" href=\"/app.css\">
</head>
<body>
  <main class=\"app\">
    <header class=\"panel\">
      <h1 id=\"title\">Robot Dashboard</h1>
      <p class=\"status\">Connection: <span id=\"connection\" data-state=\"connecting\">connecting</span></p>
      <p id=\"message\" class=\"message\">Loading schema…</p>
    </header>

    <section class=\"panel\">
      <h2>Controls</h2>
      <div id=\"controls\" class=\"controls\"></div>
    </section>

    <section class=\"panel\">
      <h2>Telemetry</h2>
      <div id=\"telemetry\" class=\"telemetry\"></div>
    </section>
  </main>

  <button id=\"emergency-stop\" class=\"danger\" type=\"button\">EMERGENCY STOP</button>
  <script src=\"/app.js\"></script>
</body>
</html>
"""

CSS = """:root {
  color-scheme: dark;
  --bg: #0f172a;
  --panel: #1e293b;
  --accent: #22d3ee;
  --danger: #ef4444;
  --text: #e2e8f0;
  --muted: #94a3b8;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
}
.app {
  max-width: 720px;
  margin: 0 auto;
  padding: 1rem;
  padding-bottom: 6rem;
  display: grid;
  gap: 1rem;
}
.panel {
  background: var(--panel);
  border-radius: 0.9rem;
  padding: 1rem;
}
h1, h2 { margin: 0 0 0.6rem; }
.status, .message { margin: 0.4rem 0 0; color: var(--muted); }
#connection[data-state=\"connected\"] { color: #34d399; }
#connection[data-state=\"offline\"] { color: var(--danger); }
.controls { display: grid; gap: 0.6rem; }
button, input[type=range] { width: 100%; min-height: 48px; }
button {
  border: 0;
  border-radius: 0.7rem;
  font-weight: 700;
  padding: 0.75rem;
  background: var(--accent);
  color: #001018;
}
button:active { filter: brightness(0.92); }
.control-row { display: grid; gap: 0.3rem; }
label { color: var(--muted); font-size: 0.95rem; }
.telemetry { display: grid; gap: 0.45rem; }
.telemetry-row {
  display: flex;
  justify-content: space-between;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid #334155;
  border-radius: 0.6rem;
  padding: 0.55rem 0.7rem;
}
.danger {
  position: fixed;
  right: 1rem;
  bottom: 1rem;
  width: calc(100% - 2rem);
  max-width: 360px;
  background: var(--danger);
  color: #fff;
  z-index: 1000;
}
"""

JS = """(function () {
  const titleEl = document.getElementById('title');
  const connectionEl = document.getElementById('connection');
  const messageEl = document.getElementById('message');
  const controlsEl = document.getElementById('controls');
  const telemetryEl = document.getElementById('telemetry');
  const stopEl = document.getElementById('emergency-stop');

  let schema = null;
  let telemetryFields = [];

  function setConnection(state, msg) {
    connectionEl.dataset.state = state;
    connectionEl.textContent = state;
    if (msg) messageEl.textContent = msg;
  }

  async function getJson(url) {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return await res.json();
  }

  async function postJson(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    return await res.json().catch(() => ({}));
  }

  function addButton(control) {
    const row = document.createElement('div');
    row.className = 'control-row';
    const btn = document.createElement('button');
    btn.textContent = control.label || control.id;

    const press = async () => {
      try {
        await postJson('/api/command', { id: control.id, event: 'press' });
      } catch (_) {
        setConnection('offline', 'Command send failed');
      }
    };
    const release = async () => {
      if (!control.on_release) return;
      try {
        await postJson('/api/command', { id: control.id, event: 'release' });
      } catch (_) {
        setConnection('offline', 'Release send failed');
      }
    };

    btn.addEventListener('click', press);
    btn.addEventListener('pointerdown', press);
    btn.addEventListener('pointerup', release);
    btn.addEventListener('pointercancel', release);
    row.appendChild(btn);
    controlsEl.appendChild(row);
  }

  function addSlider(control) {
    const row = document.createElement('div');
    row.className = 'control-row';

    const label = document.createElement('label');
    label.textContent = (control.label || control.id) + ': ';

    const value = document.createElement('span');
    value.textContent = String(control.default || 0);
    label.appendChild(value);

    const input = document.createElement('input');
    input.type = 'range';
    input.min = String(control.min == null ? 0 : control.min);
    input.max = String(control.max == null ? 100 : control.max);
    input.step = String(control.step == null ? 1 : control.step);
    input.value = String(control.default == null ? input.min : control.default);

    const send = async () => {
      value.textContent = input.value;
      try {
        await postJson('/api/set', { id: control.id, value: Number(input.value) });
      } catch (_) {
        setConnection('offline', 'Slider send failed');
      }
    };

    input.addEventListener('input', send);
    input.addEventListener('change', send);

    row.appendChild(label);
    row.appendChild(input);
    controlsEl.appendChild(row);
  }

  function renderTelemetry() {
    telemetryEl.textContent = '';
    for (const field of telemetryFields) {
      const row = document.createElement('div');
      row.className = 'telemetry-row';
      const label = document.createElement('span');
      label.textContent = field.label || field.id;
      const val = document.createElement('span');
      val.id = 'telemetry-' + field.id;
      val.textContent = '--';
      row.appendChild(label);
      row.appendChild(val);
      telemetryEl.appendChild(row);
    }
  }

  async function loadSchema() {
    schema = await getJson('/api/schema');
    titleEl.textContent = schema.title || 'Robot Dashboard';
    controlsEl.textContent = '';

    telemetryFields = Array.isArray(schema.telemetry) ? schema.telemetry : [];
    const controls = Array.isArray(schema.controls) ? schema.controls : [];

    controls.forEach((control) => {
      if (control.type === 'slider') addSlider(control);
      else addButton(control);
    });

    renderTelemetry();
    setConnection('connected', 'Connected to robot');
  }

  async function pollState() {
    try {
      const state = await getJson('/api/state');
      telemetryFields.forEach((field) => {
        const el = document.getElementById('telemetry-' + field.id);
        if (!el) return;
        const next = state[field.id];
        el.textContent = next == null ? '--' : String(next);
      });
      setConnection('connected');
    } catch (_) {
      setConnection('offline', 'Waiting for robot…');
    }
  }

  stopEl.addEventListener('click', async () => {
    try {
      await postJson('/api/emergency_stop', {});
      setConnection('connected', 'Emergency stop sent');
    } catch (_) {
      setConnection('offline', 'Emergency stop failed');
    }
  });

  loadSchema().catch(() => setConnection('offline', 'Failed to load schema'));
  setInterval(pollState, 800);
})();
"""
