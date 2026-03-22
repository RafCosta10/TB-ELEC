import json
import os
from pathlib import Path
import socket
import time
import customtkinter as ctk

HOST = "127.0.0.1"
PORT = 5555

IDLE = "IDLE"
ARMED = "ARMED"
RUNNING = "RUNNING"
FAULT = "FAULT"
SHUTDOWN = "SHUTDOWN"


POWER_ON_COMMAND = "p"

if os.name == "posix" and not os.environ.get("DISPLAY"):
    # Allow launching from SSH into the active local Pi desktop session.
    if Path("/tmp/.X11-unix/X0").exists():
        os.environ["DISPLAY"] = ":0"
        os.environ.setdefault("XAUTHORITY", str(Path.home() / ".Xauthority"))

try:
    app = ctk.CTk()
except Exception as exc:
    raise RuntimeError(
        "No graphical display is available. Run from Pi desktop, or use DISPLAY=:0/X11 forwarding."
    ) from exc

app.title("TBM System UI")
app.geometry("700x620")

current_state = IDLE
connected = False

auger_rpm = 0.0
target_rpm = 0.0
temperature = 25.0
chainage = 0.0
voltage = 0.0
current = 0.0
load_factor = 1.0
e_stop_pressed = False

temp_flash_on = False
last_flash_time = 0.0

sock = None
rx_buffer = ""

power_on_in_progress = False
power_on_deadline = 0.0
power_on_attempts_remaining = 0

system_powered_on = False

state_label = ctk.CTkLabel(
    app,
    text="SYSTEM STATE: IDLE",
    font=ctk.CTkFont(size=32, weight="bold")
)
state_label.pack(pady=40)

conn_label = ctk.CTkLabel(
    app,
    text="Connected to controller: NO",
    font=ctk.CTkFont(size=18)
)
conn_label.pack(pady=(0, 20))

voltage_label = ctk.CTkLabel(
    app,
    text="Voltage: --- V",
    font=ctk.CTkFont(size=20)
)
voltage_label.pack(pady=10)

current_label = ctk.CTkLabel(
    app,
    text="Current: --- A",
    font=ctk.CTkFont(size=20)
)
current_label.pack(pady=10)

temp_label = ctk.CTkLabel(
    app,
    text="Temperature: --- C",
    font=ctk.CTkFont(size=20)
)
temp_label.pack(pady=10)

rpm_label = ctk.CTkLabel(
    app,
    text="RPM: --- / ---",
    font=ctk.CTkFont(size=20)
)
rpm_label.pack(pady=10)

estop_label = ctk.CTkLabel(
    app,
    text="E-STOP: Released",
    font=ctk.CTkFont(size=18)
)
estop_label.pack(pady=8)


def set_state(new_state: str):
    global current_state
    current_state = new_state
    state_label.configure(text=f"SYSTEM STATE: {new_state}")


def set_controls_enabled(enabled: bool):
    button_state = "normal" if enabled else "disabled"

    arm_button.configure(state=button_state)
    disarm_button.configure(state=button_state)
    start_button.configure(state=button_state)
    increase_rpm_button.configure(state=button_state)
    decrease_rpm_button.configure(state=button_state)
    simulate_overheat_button.configure(state=button_state)
    release_estop_button.configure(state=button_state)
    reset_button.configure(state=button_state)
    emergency_stop_button.configure(state=button_state)
    shutdown_button.configure(state=button_state)

    # Fix: POWER ON should only be pressable when system is off
    power_on_button.configure(state="disabled" if enabled else "normal")


def disconnect_firmware():
    global sock, connected, rx_buffer

    connected = False
    rx_buffer = ""
    if sock is not None:
        try:
            sock.close()
        except OSError:
            pass
        sock = None


def connect_firmware():
    global sock, connected

    if connected:
        return

    try:
        new_sock = socket.create_connection((HOST, PORT), timeout=0.15)
        new_sock.setblocking(False)
    except OSError:
        connected = False
        return

    sock = new_sock
    connected = True


def send_command(cmd: str):
    if not connected or sock is None:
        print(f"[GUI] send_command skipped; not connected. cmd={cmd!r}")
        return

    try:
        print(f"[GUI] send_command -> {cmd!r}")
        sock.sendall((cmd + "\n").encode("ascii"))
    except OSError:
        disconnect_firmware()


def apply_telemetry(payload: dict):
    global auger_rpm, target_rpm, temperature, chainage
    global voltage, current, load_factor, e_stop_pressed
    global power_on_in_progress, power_on_deadline, system_powered_on

    incoming_state = payload.get("state", current_state)

    if power_on_in_progress:
        if incoming_state == SHUTDOWN and time.monotonic() < power_on_deadline:
            incoming_state = current_state
        else:
            power_on_in_progress = False

    set_state(incoming_state)

    if incoming_state == SHUTDOWN:
        system_powered_on = False
    else:
        system_powered_on = True

    voltage = float(payload.get("voltage", voltage))
    current = float(payload.get("current", current))
    temperature = float(payload.get("temperature", temperature))
    auger_rpm = float(payload.get("auger_rpm", auger_rpm))
    target_rpm = float(payload.get("target_rpm", target_rpm))
    load_factor = float(payload.get("load_factor", load_factor))
    chainage = float(payload.get("chainage", chainage))
    e_stop_pressed = bool(payload.get("e_stop_pressed", e_stop_pressed))


def poll_firmware():
    global rx_buffer

    if not connected or sock is None:
        return

    while True:
        try:
            chunk = sock.recv(4096)
        except BlockingIOError:
            return
        except OSError:
            disconnect_firmware()
            return

        if not chunk:
            disconnect_firmware()
            return

        rx_buffer += chunk.decode("utf-8", errors="ignore")

        while "\n" in rx_buffer:
            line, rx_buffer = rx_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            apply_telemetry(payload)


def update_view():
    global temp_flash_on, last_flash_time

    conn_label.configure(text=f"Connected to controller: {'YES' if connected else 'NO'}")
    voltage_label.configure(text=f"Voltage: {voltage:.3f} V" if connected else "Voltage: --- V")
    current_label.configure(text=f"Current: {current:.3f} A" if connected else "Current: --- A")
    rpm_label.configure(text=f"RPM: {auger_rpm:.0f} / {target_rpm:.0f}" if connected else "RPM: --- / ---")
    estop_label.configure(text=f"E-STOP: {'PRESSED' if e_stop_pressed else 'Released'}")

    if not connected:
        temp_label.configure(
            text="Temperature: --- C",
            fg_color="transparent",
            text_color="white"
        )
        return

    if temperature > 80:
        now = time.monotonic()
        if now - last_flash_time > 0.3:
            temp_flash_on = not temp_flash_on
            last_flash_time = now

        if temp_flash_on:
            temp_label.configure(
                text=f"TEMPERATURE CRITICAL: {temperature:.1f} C",
                fg_color="red",
                text_color="white"
            )
        else:
            temp_label.configure(
                text=f"TEMPERATURE CRITICAL: {temperature:.1f} C",
                fg_color="transparent",
                text_color="red"
            )

    elif temperature > 75:
        temp_label.configure(
            text=f"Temperature Warning: {temperature:.2f} C",
            fg_color="transparent",
            text_color="orange"
        )

    else:
        temp_flash_on = False
        temp_label.configure(
            text=f"Temperature: {temperature:.2f} C",
            fg_color="transparent",
            text_color="white"
        )


def attempt_power_on_reconnect():
    global power_on_attempts_remaining

    if current_state == SHUTDOWN and not system_powered_on:
        return

    if connected:
        if POWER_ON_COMMAND:
            send_command(POWER_ON_COMMAND)
        return

    if power_on_attempts_remaining <= 0:
        print("[GUI] power on reconnect attempts exhausted")
        return

    print(f"[GUI] power on reconnect attempt; remaining={power_on_attempts_remaining}")
    connect_firmware()
    power_on_attempts_remaining -= 1

    if connected:
        if POWER_ON_COMMAND:
            send_command(POWER_ON_COMMAND)
        update_view()
        return

    app.after(250, attempt_power_on_reconnect)


def telemetry_tick():
    global power_on_in_progress

    if not connected and system_powered_on:
        connect_firmware()

    poll_firmware()

    if power_on_in_progress and time.monotonic() >= power_on_deadline:
        power_on_in_progress = False

    if system_powered_on:
        set_controls_enabled(True)
    else:
        set_controls_enabled(False)

    update_view()
    app.after(100, telemetry_tick)


def arm_or_disarm_system():
    send_command("a")


command_frame = ctk.CTkFrame(app)
command_frame.pack(pady=12, padx=20, fill="x")

for col in range(3):
    command_frame.grid_columnconfigure(col, weight=1)


arm_button = ctk.CTkButton(
    command_frame,
    text="ARM (a)",
    fg_color="orange",
    hover_color="#b56d00",
    command=arm_or_disarm_system
)
arm_button.grid(row=0, column=0, padx=6, pady=6, sticky="ew")


def disarm_system():
    send_command("d")


disarm_button = ctk.CTkButton(
    command_frame,
    text="DISARM (d)",
    fg_color="#8a8a8a",
    hover_color="#6f6f6f",
    command=disarm_system
)
disarm_button.grid(row=0, column=1, padx=6, pady=6, sticky="ew")


def start_system():
    send_command("s")


start_button = ctk.CTkButton(
    command_frame,
    text="START (s)",
    fg_color="green",
    hover_color="dark green",
    command=start_system
)
start_button.grid(row=0, column=2, padx=6, pady=6, sticky="ew")


def increase_rpm():
    send_command("+")


def decrease_rpm():
    send_command("-")


increase_rpm_button = ctk.CTkButton(
    command_frame,
    text="RPM + (+)",
    command=increase_rpm
)
increase_rpm_button.grid(row=1, column=0, padx=6, pady=6, sticky="ew")

decrease_rpm_button = ctk.CTkButton(
    command_frame,
    text="RPM - (-)",
    command=decrease_rpm
)
decrease_rpm_button.grid(row=1, column=1, padx=6, pady=6, sticky="ew")


def simulate_overheat():
    send_command("t")


simulate_overheat_button = ctk.CTkButton(
    command_frame,
    text="SIM OVERHEAT (t)",
    fg_color="#d26700",
    hover_color="#a34f00",
    command=simulate_overheat
)
simulate_overheat_button.grid(row=1, column=2, padx=6, pady=6, sticky="ew")


def trigger_estop():
    send_command("e")


def release_estop():
    send_command("u")


emergency_stop_button = ctk.CTkButton(
    command_frame,
    text="EMERGENCY STOP (e)",
    width=170,
    height=44,
    corner_radius=8,
    fg_color="red",
    hover_color="#a80000",
    command=trigger_estop
)
emergency_stop_button.grid(row=2, column=0, padx=6, pady=6, sticky="ew")


release_estop_button = ctk.CTkButton(
    command_frame,
    text="RELEASE E-STOP (u)",
    fg_color="#3f7a40",
    hover_color="#2f5c30",
    command=release_estop
)
release_estop_button.grid(row=2, column=1, padx=6, pady=6, sticky="ew")


def reset_fault():
    send_command("r")


reset_button = ctk.CTkButton(
    command_frame,
    text="RESET FAULT (r)",
    fg_color="#c99700",
    hover_color="#a67f00",
    command=reset_fault
)
reset_button.grid(row=2, column=2, padx=6, pady=6, sticky="ew")


def shutdown_system():
    global power_on_in_progress, power_on_deadline, power_on_attempts_remaining
    global system_powered_on

    print("[GUI] shutdown button pressed")
    power_on_in_progress = False
    power_on_deadline = 0.0
    power_on_attempts_remaining = 0

    system_powered_on = False
    set_state(SHUTDOWN)
    send_command("x")
    disconnect_firmware()
    set_controls_enabled(False)
    update_view()


def power_on_system():
    global power_on_in_progress, power_on_deadline, power_on_attempts_remaining
    global system_powered_on

    print("[GUI] power on button pressed")

    power_on_in_progress = True
    power_on_deadline = time.monotonic() + 2.0
    power_on_attempts_remaining = 8

    system_powered_on = True

    disconnect_firmware()
    set_state(IDLE)
    connect_firmware()

    if connected and POWER_ON_COMMAND:
        send_command(POWER_ON_COMMAND)
    else:
        app.after(250, attempt_power_on_reconnect)

    set_controls_enabled(True)
    update_view()


shutdown_button = ctk.CTkButton(
    command_frame,
    text="SHUTDOWN (x)",
    fg_color="#444444",
    hover_color="#333333",
    command=shutdown_system
)
shutdown_button.grid(row=3, column=0, padx=6, pady=(6, 10), sticky="ew")

power_on_button = ctk.CTkButton(
    command_frame,
    text="POWER ON",
    command=power_on_system
)
power_on_button.grid(row=3, column=1, columnspan=2, padx=6, pady=(6, 10), sticky="ew")


set_controls_enabled(False)
update_view()
telemetry_tick()

app.mainloop()