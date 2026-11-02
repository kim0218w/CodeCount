
import math
import time

from gpiozero import Button, OutputDevice

# ============================================
# 1. GPIO Configuration
# ============================================

AXIS_PINS = {
    "X": {"PUL": 26, "DIR": 19, "ENA": 13, "HOME": 2},
    "Y": {"PUL": 21, "DIR": 20, "ENA": 16, "HOME": 4},
    "Z": {"PUL": 6, "DIR": 5, "ENA": 0, "HOME": 3}
}

ENA_ACTIVE_HIGH = True

# ============================================
# 2. Motion Configuration
# ============================================

MAX_STEP_RATE = {
    "X": 8400.0,
    "Y": 8400.0,
    "Z": 8400.0
}

MAX_ACCEL = {
    "X": 1600.0,
    "Y": 1600.0,
    "Z": 800.0
}

PULSES_PER_MM = {
    "X": 794.70,
    "Y": 843.59,
    "Z": 765.55
}

PULSE_HIGH_S = 0.0002
CONTROL_INTERVAL_S = 0.001
MAX_COMMAND_STEPS = 200000

# ============================================
# 3. Homing Configuration
# ============================================

HOME_DIRECTION = {
    "X": "H",
    "Y": "H",
    "Z": "H"
}

HOMING_ORDER = ["Z", "X", "Y"]

HOMING_STEP_RATE = 500.0
HOMING_TIMEOUT = 120.0

# Adjust to actual mechanical travel limits.
MAX_HOMING_STEPS = {
    "X": 60000,
    "Y": 60000,
    "Z": 60000
}

# The existing switch test reported reversed states.
HOME_SIGNAL_INVERTED = True

# ============================================
# 4. Position 1 Configuration
# ============================================

# Distance from each homing reference in mm.
# Positive coordinates move away from the home switch.
# Set all three values before automatic movement.

POSITION_1_MM = {
    "X": None,
    "Y": None,
    "Z": None
}

# ============================================
# 5. S-Curve Functions
# ============================================

def profile_steps(elapsed, duration, steps):

    s = max(0.0, min(elapsed / duration, 1.0))

    smooth = (
        10 * s**3
        - 15 * s**4
        + 6 * s**5
    )

    return steps * smooth


def move_duration(axis, steps):

    return max(
        1.875 * steps / MAX_STEP_RATE[axis],
        math.sqrt(
            5.7735 * steps / MAX_ACCEL[axis]
        ),
        0.05
    )


# ============================================
# 6. GPIO Initialization
# ============================================

motors = {}
sensors = {}

position_steps = {
    "X": None,
    "Y": None,
    "Z": None
}


def initialize_gpio():

    for axis, pins in AXIS_PINS.items():

        motors[axis] = {
            "ENA": OutputDevice(
                pins["ENA"],
                active_high=ENA_ACTIVE_HIGH,
                initial_value=False
            ),

            "DIR": OutputDevice(
                pins["DIR"],
                initial_value=False
            ),

            "PUL": OutputDevice(
                pins["PUL"],
                initial_value=False
            )
        }

        sensors[axis] = Button(
            pin=pins["HOME"],
            pull_up=True,
            bounce_time=0.05
        )


def home_pressed(axis):

    raw_state = sensors[axis].is_pressed

    if HOME_SIGNAL_INVERTED:
        return not raw_state

    return raw_state


def set_direction(axis, direction):

    if direction == "H":
        motors[axis]["DIR"].on()

    elif direction == "L":
        motors[axis]["DIR"].off()

    else:
        raise ValueError("Invalid direction")


def pulse(axis):

    motors[axis]["PUL"].on()
    time.sleep(PULSE_HIGH_S)
    motors[axis]["PUL"].off()


def disable_all():

    for motor in motors.values():
        motor["ENA"].off()


# ============================================
# 7. Homing
# ============================================

def home_axis(axis):

    print(f"\n[{axis}] Homing started")

    # Refuse to move if the sensor is already active.
    if home_pressed(axis):
        raise RuntimeError(
            f"{axis}: Home switch already active"
        )

    motor = motors[axis]

    set_direction(axis, HOME_DIRECTION[axis])
    time.sleep(0.02)

    motor["ENA"].on()
    time.sleep(0.02)

    start_time = time.perf_counter()
    emitted_steps = 0

    # GPIO software pulse timing is not deterministic.
    step_interval = 1.0 / HOMING_STEP_RATE

    try:

        while True:

            # Stop immediately when the switch is detected.
            if home_pressed(axis):
                position_steps[axis] = 0

                print(
                    f"[{axis}] HOME DETECTED "
                    f"({emitted_steps} steps)"
                )

                return

            elapsed = time.perf_counter() - start_time

            if elapsed >= HOMING_TIMEOUT:
                raise TimeoutError(
                    f"{axis}: Homing timeout"
                )

            if emitted_steps >= MAX_HOMING_STEPS[axis]:
                raise RuntimeError(
                    f"{axis}: Homing step limit reached"
                )

            step_start = time.perf_counter()

            pulse(axis)
            emitted_steps += 1

            # Wait only for remaining step interval.
            remaining = (
                step_interval
                - (time.perf_counter() - step_start)
            )

            if remaining > 0:
                time.sleep(remaining)

    finally:

        motor["PUL"].off()
        motor["ENA"].off()


def home_all():

    print("\n===================================")
    print(" XYZ Homing Sequence")
    print("===================================")

    # Check all switches before starting.
    for axis in AXIS_PINS:
        if home_pressed(axis):
            raise RuntimeError(
                f"{axis}: Switch active before homing"
            )

    # Reset position validity.
    for axis in position_steps:
        position_steps[axis] = None

    # Sequential homing for initial safety testing.
    for axis in HOMING_ORDER:
        home_axis(axis)

    print("\nAll axes homed successfully")
    print("Home position: X=0, Y=0, Z=0")


# ============================================
# 8. S-Curve Motor Movement
# ============================================

def move_motor(axis, direction, steps):

    if steps <= 0:
        return

    if steps > MAX_COMMAND_STEPS:
        raise ValueError(
            f"{axis}: Step limit exceeded"
        )

    if position_steps[axis] is None:
        raise RuntimeError(
            f"{axis}: Axis is not homed"
        )

    # Do not move toward an already active home switch.
    if direction == "H" and home_pressed(axis):
        raise RuntimeError(
            f"{axis}: Home switch is active"
        )

    motor = motors[axis]

    set_direction(axis, direction)
    time.sleep(0.01)

    motor["ENA"].on()
    time.sleep(0.02)

    duration = move_duration(axis, steps)

    start_time = time.perf_counter()
    done = 0

    print(
        f"[{axis}] Move {direction}, {steps} steps"
    )

    try:

        while done < steps:

            # Prevent further movement into the home switch.
            if direction == "H" and home_pressed(axis):
                position_steps[axis] = None
                raise RuntimeError(
                    f"{axis}: Home limit triggered"
                )

            elapsed = time.perf_counter() - start_time

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
                pulse(axis)
                done += 1

                if direction == "H":
                    position_steps[axis] -= 1
                else:
                    position_steps[axis] += 1

            else:
                time.sleep(CONTROL_INTERVAL_S)

        print(f"[{axis}] Move completed")

    except BaseException:

        # Position is untrusted after an interrupted move.
        position_steps[axis] = None
        raise

    finally:

        motor["PUL"].off()
        motor["ENA"].off()


# ============================================
# 9. Move to Position 1
# ============================================

def move_to_position_1():

    if any(
        value is None
        for value in POSITION_1_MM.values()
    ):
        print(
            "\nPosition 1 is not configured."
        )
        print(
            "Set X, Y, Z coordinates in POSITION_1_MM."
        )
        return

    print("\nMoving to Position 1")

    for axis in ["X", "Y", "Z"]:

        target_mm = POSITION_1_MM[axis]

        if target_mm < 0:
            raise ValueError(
                f"{axis}: Negative position is not allowed"
            )

        target_steps = round(
            target_mm * PULSES_PER_MM[axis]
        )

        current_steps = position_steps[axis]

        if current_steps is None:
            raise RuntimeError(
                f"{axis}: Position is unknown"
            )

        delta = target_steps - current_steps

        if delta > 0:
            direction = "L"

        elif delta < 0:
            direction = "H"

        else:
            continue

        move_motor(
            axis,
            direction,
            abs(delta)
        )

    print("\nPosition 1 movement completed")


# ============================================
# 10. Main
# ============================================

def main():

    try:

        initialize_gpio()

        print("===================================")
        print(" Raspberry Pi 5 XYZ Controller")
        print(" Homing + S-Curve")
        print("===================================")

        print("\nHome sensor states:")

        for axis in AXIS_PINS:
            print(
                f"{axis}: "
                f"{'PRESSED' if home_pressed(axis) else 'RELEASED'}"
            )

        print("\nType HOME to start homing.")
        command = input("Command > ").strip().upper()

        if command != "HOME":
            print("Homing cancelled")
            return

        home_all()

        move_to_position_1()

    except KeyboardInterrupt:
        print("\nEmergency user interruption")

    except Exception as e:
        print(f"\nERROR: {e}")

    finally:

        disable_all()

        for motor in motors.values():
            for device in motor.values():
                device.close()

        for sensor in sensors.values():
            sensor.close()

        print("GPIO resources released")


if __name__ == "__main__":
    main()
