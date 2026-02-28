import customtkinter as ctk
import random

app = ctk.CTk()
app.title("System UI")
app.geometry("600x400")

state = "IDLE"

running = False
fault = False
connected = True  # placeholder for now
current = 1.20     # placeholder
temperature = 200.0 # placeholder
voltage = 4.6

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

def update_telemetry():
    global voltage, current, temperature, running, connected, fault

    if running and connected and (not fault):
        voltage += random.uniform(-0.02, 0.02)
        current += random.uniform(-0.05, 0.05)
        temperature += random.uniform(-0.08, 0.08)

        voltage_label.configure(text=f"Voltage: {voltage:.3f} V")
        current_label.configure(text=f"Current: {current:.3f} A")
        temp_label.configure(text=f"Temperature: {temperature:.2f} °C")
    else:
        voltage_label.configure(text="Voltage: --- V")
        current_label.configure(text="Current: --- A")
        temp_label.configure(text="Temperature: --- °C")

    app.after(200, update_telemetry)

def start_system():
    global running, fault, connected
    if fault or (not connected):
        return
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


def stop_system():
    global running
    running = False
    state_label.configure(text="SYSTEM STATE: STOPPED")
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
    global fault, running
    fault = False
    running = False
    state_label.configure(text="SYSTEM STATE: IDLE")

reset_button = ctk.CTkButton(
    app,
    text="RESET FAULT",
    fg_color="#c99700",
    hover_color="#a67f00",
    command=reset_fault
)
reset_button.pack(pady=10)


update_telemetry()

app.mainloop()