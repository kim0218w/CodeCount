
import time
from gpiozero import Button

# ==============================================
# 1. Homing Sensor GPIO Configuration
# ==============================================

HOME_PINS = {
    "X": 2,
    "Y": 3,
    "Z": 4
}

# True: COM + NO, switch connected to GND
# False: COM + NC, switch connected to GND
USE_NO_SWITCH = True

sensors = {}

# ==============================================
# 2. Sensor Event Handlers
# ==============================================

def sensor_pressed(axis):
    print(f"[{axis}] PRESSED", flush=True)


def sensor_released(axis):
    print(f"[{axis}] RELEASED", flush=True)


# ==============================================
# 3. Main
# ==============================================

try:
    for axis, pin in HOME_PINS.items():

        sensor = Button(
            pin=pin,
            pull_up=True,
            active_state=None,
            bounce_time=0.05
        )

        sensors[axis] = sensor

        sensor.when_pressed = (
            lambda axis=axis: sensor_pressed(axis)
        )

        sensor.when_released = (
            lambda axis=axis: sensor_released(axis)
        )

    print("===================================")
    print(" XYZ Homing Sensor Test")
    print("===================================")

    print("X : GPIO 2")
    print("Y : GPIO 3")
    print("Z : GPIO 4")
    print()

    print("Press each homing switch.")
    print("Press Ctrl+C to exit.")
    print()

    for axis, sensor in sensors.items():
        state = "PRESSED" if sensor.is_pressed else "RELEASED"
        print(f"[{axis}] Initial state: {state}")

    while True:
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nTest stopped.")

finally:
    for sensor in sensors.values():
        sensor.close()

    print("GPIO resources released.")
