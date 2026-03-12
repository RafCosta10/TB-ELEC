#!/usr/bin/env python3
"""
Motor and Ultrasonic Sensor Test for Raspberry Pi 5

GPIO Configuration:
- Motor (via MOSFET): GPIO 23
- Ultrasonic Echo: GPIO 25
- Ultrasonic Trig: GPIO 16

Controls:
- Press 's' to start motor
- Press 'x' to stop motor
- Press 'q' to quit program
"""

import time
import sys
import select
import termios
import tty

# Use lgpio for Raspberry Pi 5 (works with RP1 chip)
try:
    import lgpio
except ImportError:
    print("Error: lgpio library not found.")
    print("Install with: sudo apt install python3-lgpio")
    sys.exit(1)

# GPIO Pin Configuration
MOTOR_PIN = 23      # Motor control via MOSFET
ULTRASONIC_TRIG = 16  # Ultrasonic trigger pin
ULTRASONIC_ECHO = 25  # Ultrasonic echo pin

# GPIO chip for Raspberry Pi 5
GPIO_CHIP = 4  # RP1 chip on Pi 5 uses gpiochip4


class MotorController:
    """Controls motor via MOSFET on GPIO"""
    
    def __init__(self, chip_handle, pin):
        self.chip = chip_handle
        self.pin = pin
        self.is_running = False
        
        # Set up motor pin as output
        lgpio.gpio_claim_output(self.chip, self.pin, 0)
        print(f"Motor initialized on GPIO {self.pin}")
    
    def start(self):
        """Start the motor"""
        lgpio.gpio_write(self.chip, self.pin, 1)
        self.is_running = True
        print("Motor STARTED")
    
    def stop(self):
        """Stop the motor"""
        lgpio.gpio_write(self.chip, self.pin, 0)
        self.is_running = False
        print("Motor STOPPED")
    
    def get_status(self):
        """Get motor status"""
        return "Running" if self.is_running else "Stopped"


class UltrasonicSensor:
    """HC-SR04 Ultrasonic Distance Sensor"""
    
    def __init__(self, chip_handle, trig_pin, echo_pin):
        self.chip = chip_handle
        self.trig_pin = trig_pin
        self.echo_pin = echo_pin
        
        # Set up trigger pin as output
        lgpio.gpio_claim_output(self.chip, self.trig_pin, 0)
        
        # Set up echo pin as input
        lgpio.gpio_claim_input(self.chip, self.echo_pin)
        
        print(f"Ultrasonic sensor initialized - Trig: GPIO {self.trig_pin}, Echo: GPIO {self.echo_pin}")
        
        # Allow sensor to settle
        time.sleep(0.1)
    
    def get_distance(self):
        """
        Measure distance in centimeters
        Returns: distance in cm or -1 if timeout
        """
        # Ensure trigger is low
        lgpio.gpio_write(self.chip, self.trig_pin, 0)
        time.sleep(0.000002)  # 2 microseconds
        
        # Send 10us pulse to trigger
        lgpio.gpio_write(self.chip, self.trig_pin, 1)
        time.sleep(0.00001)  # 10 microseconds
        lgpio.gpio_write(self.chip, self.trig_pin, 0)
        
        # Wait for echo to go high (with timeout)
        timeout_start = time.time()
        while lgpio.gpio_read(self.chip, self.echo_pin) == 0:
            pulse_start = time.time()
            if pulse_start - timeout_start > 0.1:  # 100ms timeout
                return -1
        
        # Wait for echo to go low (with timeout)
        timeout_start = time.time()
        while lgpio.gpio_read(self.chip, self.echo_pin) == 1:
            pulse_end = time.time()
            if pulse_end - timeout_start > 0.1:  # 100ms timeout
                return -1
        
        # Calculate distance
        # Speed of sound = 343 m/s = 34300 cm/s
        # Distance = (time * speed) / 2 (divide by 2 for round trip)
        pulse_duration = pulse_end - pulse_start
        distance = (pulse_duration * 34300) / 2
        
        return round(distance, 2)


class KeyboardInput:
    """Non-blocking keyboard input handler"""
    
    def __init__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
    
    def __enter__(self):
        tty.setcbreak(sys.stdin.fileno())
        return self
    
    def __exit__(self, *args):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
    
    def get_key(self):
        """Get key press if available (non-blocking)"""
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None


def main():
    print("=" * 50)
    print("Motor & Ultrasonic Sensor Test - Raspberry Pi 5")
    print("=" * 50)
    print()
    print("Controls:")
    print("  's' - Start motor")
    print("  'x' - Stop motor")
    print("  'q' - Quit program")
    print()
    
    # Open GPIO chip
    try:
        chip = lgpio.gpiochip_open(GPIO_CHIP)
        print(f"Opened GPIO chip {GPIO_CHIP}")
    except Exception as e:
        print(f"Error opening GPIO chip: {e}")
        print("Make sure you're running on Raspberry Pi 5")
        print("You may need to run with sudo")
        sys.exit(1)
    
    try:
        # Initialize components
        motor = MotorController(chip, MOTOR_PIN)
        ultrasonic = UltrasonicSensor(chip, ULTRASONIC_TRIG, ULTRASONIC_ECHO)
        
        print()
        print("System ready! Press keys to control motor.")
        print("-" * 50)
        
        with KeyboardInput() as keyboard:
            while True:
                # Check for key press
                key = keyboard.get_key()
                
                if key:
                    if key.lower() == 's':
                        motor.start()
                    elif key.lower() == 'x':
                        motor.stop()
                    elif key.lower() == 'q':
                        print("\nQuitting...")
                        break
                
                # Read and display ultrasonic distance
                distance = ultrasonic.get_distance()
                
                if distance >= 0:
                    status = motor.get_status()
                    print(f"\rDistance: {distance:7.2f} cm | Motor: {status:8s}", end="", flush=True)
                else:
                    print(f"\rDistance: TIMEOUT     | Motor: {motor.get_status():8s}", end="", flush=True)
                
                # Small delay between readings
                time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    finally:
        # Cleanup
        print("Cleaning up GPIO...")
        motor.stop()
        lgpio.gpiochip_close(chip)
        print("Done!")


if __name__ == "__main__":
    main()
