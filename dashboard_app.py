"""Desktop dashboard UI for controlling a Pico WiFi robot car.

This Tkinter app lets users:
- define button/slider controls at runtime,
- assign optional keyboard shortcuts,
- save/load control layouts as JSON,
- send resolved paths via ``RobotClient.send_path``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from pico_wifi_robot.client import RobotClient


@dataclass
class DashboardControl:
    control_type: str  # "button" | "slider"
    label: str
    path_template: str
    key_binding: Optional[str] = None
    default: float = 0.0
    min_value: float = 0.0
    max_value: float = 100.0
    step: float = 1.0

    def to_payload(self) -> dict:
        data = asdict(self)
        # Keep JSON tidy by omitting slider-only fields on button controls.
        if self.control_type == "button":
            for field in ("default", "min_value", "max_value", "step"):
                data.pop(field, None)
        return data

    @classmethod
    def from_payload(cls, data: dict) -> "DashboardControl":
        control_type = data.get("control_type")
        if control_type not in {"button", "slider"}:
            raise ValueError("control_type must be 'button' or 'slider'.")

        return cls(
            control_type=control_type,
            label=str(data.get("label", "")).strip(),
            path_template=str(data.get("path_template", "")).strip(),
            key_binding=(str(data["key_binding"]).strip() or None)
            if "key_binding" in data
            else None,
            default=float(data.get("default", 0.0)),
            min_value=float(data.get("min_value", 0.0)),
            max_value=float(data.get("max_value", 100.0)),
            step=float(data.get("step", 1.0)),
        )


class AddControlDialog(tk.Toplevel):
    def __init__(self, master: "DashboardApp") -> None:
        super().__init__(master)
        self.title("Add Control")
        self.resizable(False, False)
        self.result: Optional[DashboardControl] = None

        self.type_var = tk.StringVar(value="button")
        self.label_var = tk.StringVar()
        self.path_var = tk.StringVar(value="/arm/{value}")
        self.key_var = tk.StringVar()

        self.default_var = tk.StringVar(value="0")
        self.min_var = tk.StringVar(value="0")
        self.max_var = tk.StringVar(value="100")
        self.step_var = tk.StringVar(value="1")

        self._build_ui()
        self._toggle_slider_fields()

        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=10)
        frame.grid(sticky="nsew")

        ttk.Label(frame, text="Control Type").grid(row=0, column=0, sticky="w")
        type_box = ttk.Combobox(
            frame,
            textvariable=self.type_var,
            values=["button", "slider"],
            state="readonly",
            width=18,
        )
        type_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        type_box.bind("<<ComboboxSelected>>", lambda _e: self._toggle_slider_fields())

        ttk.Label(frame, text="Display Label").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.label_var, width=24).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )

        ttk.Label(frame, text="Path Template").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.path_var, width=24).grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )

        ttk.Label(frame, text="Key Binding").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.key_var, width=24).grid(
            row=3, column=1, sticky="ew", padx=(8, 0), pady=(6, 0)
        )

        self.slider_frame = ttk.LabelFrame(frame, text="Slider Settings", padding=8)
        self.slider_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        ttk.Label(self.slider_frame, text="Default").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.slider_frame, textvariable=self.default_var, width=10).grid(
            row=0, column=1, sticky="w", padx=(6, 12)
        )

        ttk.Label(self.slider_frame, text="Min").grid(row=0, column=2, sticky="w")
        ttk.Entry(self.slider_frame, textvariable=self.min_var, width=10).grid(
            row=0, column=3, sticky="w", padx=(6, 12)
        )

        ttk.Label(self.slider_frame, text="Max").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.slider_frame, textvariable=self.max_var, width=10).grid(
            row=1, column=1, sticky="w", padx=(6, 12), pady=(6, 0)
        )

        ttk.Label(self.slider_frame, text="Step").grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Entry(self.slider_frame, textvariable=self.step_var, width=10).grid(
            row=1, column=3, sticky="w", padx=(6, 12), pady=(6, 0)
        )

        actions = ttk.Frame(frame)
        actions.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(actions, text="Add", command=self._submit).grid(row=0, column=1)

    def _toggle_slider_fields(self) -> None:
        if self.type_var.get() == "slider":
            self.slider_frame.grid()
        else:
            self.slider_frame.grid_remove()

    def _submit(self) -> None:
        try:
            control = self._collect()
        except ValueError as exc:
            messagebox.showerror("Invalid Control", str(exc), parent=self)
            return

        self.result = control
        self.destroy()

    def _collect(self) -> DashboardControl:
        label = self.label_var.get().strip()
        if not label:
            raise ValueError("Display label is required.")

        template = self.path_var.get().strip()
        if not template:
            raise ValueError("Path template is required.")

        key = self.key_var.get().strip() or None
        if key is not None and len(key) != 1:
            raise ValueError("Key binding must be a single character.")

        control_type = self.type_var.get()

        if control_type == "button":
            return DashboardControl(
                control_type="button",
                label=label,
                path_template=template,
                key_binding=key.lower() if key else None,
            )

        min_value = float(self.min_var.get())
        max_value = float(self.max_var.get())
        step = float(self.step_var.get())
        default = float(self.default_var.get())

        if min_value >= max_value:
            raise ValueError("Slider min must be less than max.")
        if step <= 0:
            raise ValueError("Slider step must be > 0.")
        if not (min_value <= default <= max_value):
            raise ValueError("Slider default must be between min and max.")

        return DashboardControl(
            control_type="slider",
            label=label,
            path_template=template,
            key_binding=key.lower() if key else None,
            default=default,
            min_value=min_value,
            max_value=max_value,
            step=step,
        )


class DashboardApp(tk.Tk):
    def __init__(self, base_url: str = "http://192.168.4.1") -> None:
        super().__init__()
        self.title("Pico WiFi Robot Dashboard")
        self.geometry("920x560")

        self.client = RobotClient(base_url)
        self.controls: list[DashboardControl] = []
        self._controls_frame: Optional[ttk.Frame] = None
        self.status_var = tk.StringVar(value="Ready")

        self._build_layout()
        self.bind_all("<KeyPress>", self._on_key_press)

    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=10)
        left.grid(row=0, column=0, sticky="ns")

        ttk.Label(left, text="Controls", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.control_list = tk.Listbox(left, width=30, height=22)
        self.control_list.grid(row=1, column=0, sticky="ns", pady=(8, 0))

        btns = ttk.Frame(left)
        btns.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="Add Control", command=self._open_add_dialog).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(btns, text="Remove Selected", command=self._remove_selected).grid(
            row=1, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Button(btns, text="Save Config", command=self._save_config).grid(
            row=2, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Button(btns, text="Load Config", command=self._load_config).grid(
            row=3, column=0, sticky="ew", pady=(6, 0)
        )

        right = ttk.Frame(self, padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(right, text="Live Controls", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self._controls_frame = ttk.Frame(right)
        self._controls_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        status = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w")
        status.grid(row=1, column=0, columnspan=2, sticky="ew")

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _open_add_dialog(self) -> None:
        dialog = AddControlDialog(self)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        valid, error = self._validate_control(dialog.result)
        if not valid:
            self._show_validation(error)
            return

        self.controls.append(dialog.result)
        self._refresh_ui()
        self._set_status(f"Added control '{dialog.result.label}'.")

    def _remove_selected(self) -> None:
        selected = self.control_list.curselection()
        if not selected:
            self._show_validation("Select a control to remove.")
            return

        idx = selected[0]
        removed = self.controls.pop(idx)
        self._refresh_ui()
        self._set_status(f"Removed control '{removed.label}'.")

    def _refresh_ui(self) -> None:
        self.control_list.delete(0, tk.END)
        for c in self.controls:
            key = f" [{c.key_binding}]" if c.key_binding else ""
            self.control_list.insert(tk.END, f"{c.control_type}: {c.label} -> {c.path_template}{key}")

        if self._controls_frame is None:
            return

        for widget in self._controls_frame.winfo_children():
            widget.destroy()

        for row, control in enumerate(self.controls):
            if control.control_type == "button":
                ttk.Button(
                    self._controls_frame,
                    text=control.label,
                    command=lambda c=control: self._send_for_control(c),
                ).grid(row=row, column=0, sticky="ew", pady=4)
            else:
                self._render_slider(row, control)

        self._controls_frame.columnconfigure(0, weight=1)

    def _render_slider(self, row: int, control: DashboardControl) -> None:
        frame = ttk.Frame(self._controls_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=4)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text=control.label).grid(row=0, column=0, sticky="w", padx=(0, 8))

        value_var = tk.DoubleVar(value=control.default)
        slider = ttk.Scale(
            frame,
            from_=control.min_value,
            to=control.max_value,
            orient="horizontal",
            variable=value_var,
        )
        slider.grid(row=0, column=1, sticky="ew")

        value_label = ttk.Label(frame, width=8, anchor="e")
        value_label.grid(row=0, column=2, padx=(8, 8))

        def quantized_value(raw: float) -> float:
            steps = round((raw - control.min_value) / control.step)
            quantized = control.min_value + (steps * control.step)
            return min(control.max_value, max(control.min_value, quantized))

        def update_label(_event: object = None) -> None:
            snapped = quantized_value(value_var.get())
            value_label.config(text=f"{snapped:.2f}".rstrip("0").rstrip("."))

        update_label()
        slider.bind("<ButtonRelease-1>", lambda _e: self._send_for_control(control, quantized_value(value_var.get())))
        slider.bind("<KeyRelease>", lambda _e: self._send_for_control(control, quantized_value(value_var.get())))
        slider.bind("<B1-Motion>", lambda _e: update_label())

        ttk.Button(
            frame,
            text="Send",
            command=lambda c=control: self._send_for_control(c, quantized_value(value_var.get())),
        ).grid(row=0, column=3)

    def _on_key_press(self, event: tk.Event) -> None:
        key = (event.char or "").strip().lower()
        if not key:
            return

        for control in self.controls:
            if control.key_binding == key:
                value = control.default if control.control_type == "slider" else None
                self._send_for_control(control, value)
                return

    def _send_for_control(self, control: DashboardControl, value: object = None) -> None:
        valid, error = self._validate_template(control.path_template)
        if not valid:
            self._show_validation(f"{control.label}: {error}")
            return

        try:
            resolved = control.path_template.format(value=value)
        except Exception as exc:
            self._show_validation(f"Failed to resolve path template: {exc}")
            return

        if not resolved.startswith("/"):
            self._show_validation("Resolved path must start with '/'.")
            return

        try:
            response = self.client.send_path(resolved)
            self._set_status(f"Sent {resolved} -> HTTP {response.status_code}")
        except Exception as exc:
            self._show_validation(f"Request failed: {exc}")

    def _validate_template(self, template: str) -> tuple[bool, str]:
        if not template.startswith("/"):
            return False, "Path template must start with '/'."

        try:
            _ = template.format(value=0)
        except KeyError as exc:
            return False, f"Template uses unsupported placeholder: {exc}. Only {{value}} is allowed."
        except Exception as exc:
            return False, f"Invalid template format: {exc}"

        return True, ""

    def _validate_control(self, control: DashboardControl) -> tuple[bool, str]:
        valid, error = self._validate_template(control.path_template)
        if not valid:
            return False, error

        if control.key_binding:
            for existing in self.controls:
                if existing.key_binding == control.key_binding:
                    return (
                        False,
                        f"Duplicate key binding '{control.key_binding}' (already used by {existing.label}).",
                    )

        return True, ""

    def _show_validation(self, message: str) -> None:
        self._set_status(f"Validation: {message}")
        messagebox.showerror("Validation", message, parent=self)

    def _save_config(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save dashboard config",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return

        payload = {"controls": [c.to_payload() for c in self.controls]}
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._set_status(f"Saved {len(self.controls)} controls to {path}.")

    def _load_config(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Load dashboard config",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return

        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            loaded = [DashboardControl.from_payload(item) for item in data.get("controls", [])]
        except Exception as exc:
            self._show_validation(f"Failed to load config: {exc}")
            return

        seen_keys: set[str] = set()
        for control in loaded:
            valid, error = self._validate_template(control.path_template)
            if not valid:
                self._show_validation(f"{control.label}: {error}")
                return

            key = control.key_binding
            if key:
                if key in seen_keys:
                    self._show_validation(f"Config has duplicate key binding '{key}'.")
                    return
                seen_keys.add(key)

        self.controls = loaded
        self._refresh_ui()
        self._set_status(f"Loaded {len(self.controls)} controls from {path}.")


if __name__ == "__main__":
    app = DashboardApp()
    app.mainloop()
