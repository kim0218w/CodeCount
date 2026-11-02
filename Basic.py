
#!/usr/bin/env python3

import math
import time
from gpiozero import OutputDevice

# ==============================================
# 1. GPIO Configuration (BCM Numbering)
# ==============================================

AXIS_PINS = {
    "X": {"PUL": 26, "DIR": 19, "ENA": 13},
    "Y": {"PUL": 21, "DIR": 20, "ENA": 16},
    "Z": {"PUL": 6,  "DIR": 5,  "ENA": 0},
}

# Enable polarity
# True  : HIGH = Enable
# False : LOW  = Enable
ENA_ACTIVE_HIGH = True

# ==============================================
# 2. Motor Speed and Acceleration
# ==============================================

MAX_STEP_RATE = {
    "X": 400.0,
    "Y": 400.0,
    "Z": 300.0
}

MAX_ACCEL = {
    "X": 500.0,
    "Y": 500.0,
    "Z": 350.0
}

PULSE_HIGH_S = 0.0002
CONTROL_INTERVAL_S = 0.001
MAX_COMMAND_STEPS = 20000

# ==============================================
# 3. S-Curve Position Calculation
# ==============================================

def profile_steps(elapsed, duration, steps):

    s = max(0.0, min(elapsed / duration, 1.0))

    smooth = (
        10 * s**3
        - 15 * s**4
        + 6 * s**5
    )

    return steps * smooth


# ==============================================
# 4. Move Duration Calculation
# ==============================================

def move_duration(axis, steps):

    return max(
        1.875 * steps / MAX_STEP_RATE[axis],
        math.sqrt(
            5.7735 * steps / MAX_ACCEL[axis]
        ),
        0.05
    )


# ==============================================
# 5. Main Program
# ==============================================

def main():

    motors = {}

    try:
        # Initialize GPIO
        for axis, pins in AXIS_PINS.items():

            motors[axis] = {
                "ENA": OutputDevice(
                    pins["ENA"],
                    active_high=ENA_ACTIVE_HIGH,
                    initial_value=False
                ),

                "DIR": OutputDevice(
                    pins["DIR"],
                    active_high=True,
                    initial_value=False
                ),

                "PUL": OutputDevice(
                    pins["PUL"],
                    active_high=True,
                    initial_value=False
                )
            }

        print("===================================")
        print(" Raspberry Pi 5")
        print(" XYZ Stepper Motor Test")
        print(" S-Curve ON / ZVD OFF")
        print("===================================")

        print("Command examples:")
        print("X H 100")
        print("X L 100")
        print("Y H 100")
        print("Z H 100")
        print("Exit: Q")

        while True:

            command = input(
                "\nEnter command > "
            ).strip().upper()

            parts = command.split()

            # Exit
            if parts == ["Q"]:
                break

            # Validate input
            if len(parts) != 3:
                print("Invalid input. Example: X H 100")
                continue

            axis, direction, steps_text = parts

            if axis not in motors:
                print("Valid axes: X, Y, Z")
                continue

            if direction not in ("H", "L"):
                print("Direction must be H or L.")
                continue

            try:
                steps = int(steps_text)

            except ValueError:
                print("Step count must be an integer.")
                continue

            if not 1 <= steps <= MAX_COMMAND_STEPS:
                print("Step count is out of range.")
                continue

            motor = motors[axis]

            duration = move_duration(
                axis, steps
            )

            print(
                f"\n[{axis} Axis] Direction: {direction}, "
                f"Steps: {steps}"
            )

            try:
                # Set direction
                if direction == "H":
                    motor["DIR"].on()
                else:
                    motor["DIR"].off()

                time.sleep(0.01)

                # Enable motor
                motor["ENA"].on()
                time.sleep(0.02)

                start = time.perf_counter()
                done = 0

                # Generate S-Curve step pulses
                while done < steps:

                    elapsed = (
                        time.perf_counter() - start
                    )

                    if elapsed >= duration:
                        target = steps

                    else:
                        target = min(
                            steps,
                            int(
                                profile_steps(
                                    elapsed,
                                    duration,
                                    steps
                                )
                            )
                        )

                    if target > done:

                        motor["PUL"].on()
                        time.sleep(PULSE_HIGH_S)
                        motor["PUL"].off()

                        done += 1

                    else:
                        time.sleep(
                            CONTROL_INTERVAL_S
                        )

                print(
                    f"[{axis} Axis] Move completed: "
                    f"{done} steps"
                )

            finally:
                motor["PUL"].off()
                motor["ENA"].off()

    except (KeyboardInterrupt, EOFError):
        print("\nProgram interrupted.")

    finally:

        # Disable all motors
        for motor in motors.values():

            motor["ENA"].off()

            for device in motor.values():
                device.close()

        print("GPIO resources released.")


if __name__ == "__main__":
    main()
