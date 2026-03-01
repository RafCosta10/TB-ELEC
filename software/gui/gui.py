import customtkinter as ctk
import random

app = ctk.CTk()
app.title("System UI")
app.geometry("600x400")

state = "IDLE"

armed = False
running = False
fault = False
connected = True  # placeholder for now
shutdown = False
current = 1.20     # placeholder
temperature = 200.0 # placeholder
voltage = 4.6
augerRPM = 0
targetRPM = 0

state_label = ctk.CTkLabel(
    app,
    text="SYSTEM STATE: IDLE",
    font=ctk.CTkFont(size=32, weight="bold")
)
state_label.pack(pady=40)

conn_label = ctk.CTkLabel(
    app,
    text="Connected to controller: YES",
    font=ctk.CTkFont(size=18)
)
conn_label.pack(pady=(0, 20))

voltage_label = ctk.CTkLabel(
    app,
    text=f"Voltage: {voltage:.3f} V",
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
    text="Temperature: --- °C",
    font=ctk.CTkFont(size=20)
)
temp_label.pack(pady=10)

rpm_label = ctk.CTkLabel(
    app,
    text="RPM: --- / ---",
    font=ctk.CTkFont(size=20)
)
rpm_label.pack(pady=10)

def set_controls_enabled(enabled: bool):
    state = "normal" if enabled else "disabled"
    arm_button.configure(state=state)
    start_button.configure(state=state)
    increase_rpm_button.configure(state=state)
    decrease_rpm_button.configure(state=state)
    reset_button.configure(state=state)
    emergency_stop_button.configure(state=state)
    shutdown_button.configure(state=state)
    power_on_button.configure(state="normal")

def update_telemetry():
    global voltage, current, temperature, running, connected, fault, augerRPM, targetRPM

    if running and connected and (not fault):
        voltage += random.uniform(-0.02, 0.02)
        current += random.uniform(-0.05, 0.05)
        temperature += random.uniform(-0.08, 0.08)

        voltage_label.configure(text=f"Voltage: {voltage:.3f} V")
        current_label.configure(text=f"Current: {current:.3f} A")
        temp_label.configure(text=f"Temperature: {temperature:.2f} °C")
        rpm_label.configure(text=f"RPM: {augerRPM:.2f} / {targetRPM:.2f}")
    else:
        voltage_label.configure(text="Voltage: --- V")
        current_label.configure(text="Current: --- A")
        temp_label.configure(text="Temperature: --- °C")
        rpm_label.configure(text=f"RPM: --- / ---")

    app.after(200, update_telemetry)


def armed_system():
    global armed, fault

    if fault or (not connected):
        return

    if not armed:
        armed = True
        state_label.configure(text="SYSTEM STATE: ARMED")
        arm_button.configure(text="DISARM")
    else:
        armed = False
        state_label.configure(text="SYSTEM STATE: IDLE")
        arm_button.configure(text="ARM")

arm_button = ctk.CTkButton(
    app,
    text="ARM",
    fg_color="orange",
    hover_color="dark orange",
    command=armed_system
)
arm_button.pack(pady=20)


def start_system():
    global running, fault, connected, armed
    if fault or (not connected):
        return
    if armed:
        running = True
        state_label.configure(text="SYSTEM STATE: RUNNING")
        update_telemetry()


start_button = ctk.CTkButton(
    app,
    text="START",
    fg_color="green",
    hover_color="dark green",
    command=start_system
)
start_button.pack(pady=20)

def increase_rpm():
    global targetRPM
    targetRPM += 100
    rpm_label.configure(text=f"RPM: {augerRPM} / {targetRPM}")

def decrease_rpm():
    global targetRPM
    targetRPM = max(0, targetRPM - 100)
    rpm_label.configure(text=f"RPM: {augerRPM} / {targetRPM}")

increase_rpm_button = ctk.CTkButton(
    app,
    text="RPM +",
    command=increase_rpm
)
increase_rpm_button.pack(pady=5)

decrease_rpm_button = ctk.CTkButton(
    app,
    text="RPM -",
    command=decrease_rpm
)
decrease_rpm_button.pack(pady=5)

def stop_system():
    global running, fault, armed, targetRPM
    running = False
    fault = True
    armed = False
    arm_button.configure(text="ARM")
    targetRPM = 0
    state_label.configure(text="SYSTEM STATE: FAULT")
    voltage_label.configure(text="Voltage: 0 V")

emergency_stop_button = ctk.CTkButton(
    app,
    text="EMERGENCY STOP",
    width=75,
    height=75,
    corner_radius=50,
    fg_color="red",
    hover_color="dark red",
    command=stop_system
)
emergency_stop_button.pack(pady=20)

def reset_fault():
    global fault, running, armed
    if fault:
        fault = False
        running = False
        armed = False
        arm_button.configure(text="ARM")
        state_label.configure(text="SYSTEM STATE: IDLE")


reset_button = ctk.CTkButton(
    app,
    text="RESET FAULT",
    fg_color="#c99700",
    hover_color="#a67f00",
    command=reset_fault
)
reset_button.pack(pady=10)

def shutdown_system():
    global shutdown, running, armed, fault, targetRPM

    shutdown = True

    running = False
    armed = False
    fault = False
    targetRPM = 0

    arm_button.configure(text="ARM")
    state_label.configure(text="SYSTEM STATE: SHUTDOWN")

    # disable all controls except POWER ON
    set_controls_enabled(False)


def power_on_system():
    global shutdown, running, armed, fault

    shutdown = False
    running = False
    armed = False
    fault = False

    state_label.configure(text="SYSTEM STATE: IDLE")
    arm_button.configure(text="ARM")

    # re-enable controls
    set_controls_enabled(True)


shutdown_button = ctk.CTkButton(
    app,
    text="SHUTDOWN",
    fg_color="#444444",
    hover_color="#333333",
    command=shutdown_system
)
shutdown_button.pack(pady=8)

power_on_button = ctk.CTkButton(
    app,
    text="POWER ON",
    command=power_on_system
)
power_on_button.pack(pady=8)


update_telemetry()

app.mainloop()