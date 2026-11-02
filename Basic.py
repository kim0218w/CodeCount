
import math
import time
from gpiozero import Button, OutputDevice

# ============================================
# 1. GPIO Configuration
# ============================================

PINS = {
    "X": {"PUL": 26, "DIR": 19, "ENA": 13, "HOME": 2},
    "Y": {"PUL": 21, "DIR": 20, "ENA": 16, "HOME": 4},
    "Z": {"PUL": 6, "DIR": 5, "ENA": 0, "HOME": 3}
}

ENA_ACTIVE_HIGH = True
HOME_SIGNAL_INVERTED = True

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

PULSE_HIGH_S = 0.0002
CONTROL_INTERVAL_S = 0.001

# ============================================
# 3. Homing Configuration
# ============================================

HOME_ORDER = ["Z", "X", "Y"]
HOME_RATE = 1500.0
MAX_HOME_SECONDS = 240.0

# Verify these limits against actual travel.
MAX_HOME_STEPS = {
    "X": 200000,
    "Y": 200000,
    "Z": 220000
}

# Temporary absolute position limits.
MAX_POSITION_STEPS = {
    "X": 200000,
    "Y": 200000,
    "Z": 220000
}

# ============================================
# 4. Saved Positions
# ============================================

POSITION_1 = {
    "X": 100750,
    "Y": 12250,
    "Z": 203000
}

POSITION_2 = {
    "X": 102000,
    "Y": 139250,
    "Z": 202500
}

Z_LIFT_STEPS = 4000

PULSES_PER_MM = {
    "X": 794.70,
    "Y": 843.59,
    "Z": 765.55
}

# ============================================
# 5. State
# ============================================

motors = {}
sensors = {}

position_steps = {
    "X": None,
    "Y": None,
    "Z": None
}

# ============================================
# 6. GPIO Functions
# ============================================

def initialize_gpio():

    for axis, p in PINS.items():

        motors[axis] = {
            "ENA": OutputDevice(
                p["ENA"],
                active_high=ENA_ACTIVE_HIGH,
                initial_value=False
            ),
            "DIR": OutputDevice(
                p["DIR"],
                initial_value=False
            ),
            "PUL": OutputDevice(
                p["PUL"],
                initial_value=False
            )
        }

        sensors[axis] = Button(
            p["HOME"],
            pull_up=True,
            bounce_time=0.05
        )


def home_pressed(axis):

    state = sensors[axis].is_pressed

    return not state if HOME_SIGNAL_INVERTED else state


def set_direction(axis, direction):

    if direction == "H":
        motors[axis]["DIR"].on()
    elif direction == "L":
        motors[axis]["DIR"].off()
    else:
        raise ValueError("Invalid direction")

    time.sleep(0.01)


def pulse(axis):

    motor = motors[axis]

    motor["PUL"].on()
    time.sleep(PULSE_HIGH_S)
    motor["PUL"].off()


def disable_all():

    for motor in motors.values():
        motor["ENA"].off()


def invalidate_positions():

    for axis in position_steps:
        position_steps[axis] = None


# ============================================
# 7. Homing
# ============================================

def home_axis(axis):

    if home_pressed(axis):
        raise RuntimeError(
            f"{axis}: Home switch already pressed"
        )

    print(f"[{axis}] Homing towards H...")

    motor = motors[axis]

    set_direction(axis, "H")
    motor["ENA"].on()
    time.sleep(0.02)

    count = 0
    start = time.perf_counter()
    interval = 1.0 / HOME_RATE

    try:

        while not home_pressed(axis):

            if time.perf_counter() - start >= MAX_HOME_SECONDS:
                raise TimeoutError(
                    f"{axis}: Homing timeout"
                )

            if count >= MAX_HOME_STEPS[axis]:
                raise RuntimeError(
                    f"{axis}: Home step limit"
                )

            t0 = time.perf_counter()

            pulse(axis)
            count += 1

            remaining = interval - (
                time.perf_counter() - t0
            )

            if remaining > 0:
                time.sleep(remaining)

        position_steps[axis] = 0

        print(
            f"[{axis}] Home detected. "
            f"Position = 0"
        )

    finally:
        motor["PUL"].off()
        motor["ENA"].off()


def home_all():

    print("\nStarting XYZ homing")

    invalidate_positions()

    for axis in PINS:
        if home_pressed(axis):
            raise RuntimeError(
                f"{axis}: Switch already active"
            )

    try:
        for axis in HOME_ORDER:
            home_axis(axis)

    except BaseException:
        invalidate_positions()
        raise

    print("Homing completed")
    show_position()


# ============================================
# 8. S-Curve Motion
# ============================================

def move_duration(axis, steps):

    return max(
        1.875 * steps / MAX_STEP_RATE[axis],
        math.sqrt(
            5.7735 * steps / MAX_ACCEL[axis]
        ),
        0.05
    )


def s_curve_position(t, duration, steps):

    s = min(1.0, max(0.0, t / duration))

    smooth = (
        10 * s**3
        - 15 * s**4
        + 6 * s**5
    )

    return steps * smooth


def move_axis(axis, target):

    current = position_steps[axis]

    if current is None:
        raise RuntimeError(
            f"{axis}: Home required"
        )

    if not 0 <= target <= MAX_POSITION_STEPS[axis]:
        raise ValueError(
            f"{axis}: Target exceeds position limit"
        )

    delta = target - current

    if delta == 0:
        return

    direction = "L" if delta > 0 else "H"
    steps = abs(delta)

    if direction == "H" and home_pressed(axis):
        raise RuntimeError(
            f"{axis}: Home switch active"
        )

    motor = motors[axis]

    set_direction(axis, direction)
    motor["ENA"].on()
    time.sleep(0.02)

    duration = move_duration(axis, steps)
    start = time.perf_counter()
    done = 0

    print(
        f"[{axis}] {direction}: "
        f"{current} -> {target}"
    )

    try:

        while done < steps:

            if direction == "H" and home_pressed(axis):
                raise RuntimeError(
                    f"{axis}: Home switch triggered"
                )

            elapsed = time.perf_counter() - start

            if elapsed >= duration:
                expected = steps
            else:
                expected = min(
                    steps,
                    int(
                        s_curve_position(
                            elapsed, duration, steps
                        )
                    )
                )

            if done < expected:

                pulse(axis)
                done += 1

                if direction == "L":
                    position_steps[axis] += 1
                else:
                    position_steps[axis] -= 1

            else:
                time.sleep(CONTROL_INTERVAL_S)

        print(f"[{axis}] Move completed")

    except BaseException:
        invalidate_positions()
        raise

    finally:
        motor["PUL"].off()
        motor["ENA"].off()


# ============================================
# 9. Position Display
# ============================================

def show_position():

    print("\nCurrent position:")

    for axis in PINS:

        steps = position_steps[axis]

        if steps is None:
            print(f"{axis}: UNKNOWN")
        else:
            mm = steps / PULSES_PER_MM[axis]

            print(
                f"{axis}: {steps} steps "
                f"({mm:.3f} mm)"
            )


# ============================================
# 10. Position 1 Movement
# ============================================

def go_position_1():

    if any(
        position_steps[axis] is None
        for axis in PINS
    ):
        raise RuntimeError("Homing required")

    print("\nMoving to Position 1")

    # Raise Z first if necessary.
    safe_z = min(
        position_steps["Z"],
        POSITION_1["Z"] - Z_LIFT_STEPS
    )

    if safe_z < 0:
        raise RuntimeError("Invalid safe Z position")

    move_axis("Z", safe_z)

    move_axis("X", POSITION_1["X"])
    move_axis("Y", POSITION_1["Y"])

    move_axis("Z", POSITION_1["Z"])

    print("\nPosition 1 reached")
    show_position()


# ============================================
# 11. Position 1 -> Position 2
# ============================================

def go_position_2():

    if any(
        position_steps[axis] is None
        for axis in PINS
    ):
        raise RuntimeError("Homing required")

    if any(
        position_steps[axis] != POSITION_1[axis]
        for axis in PINS
    ):
        raise RuntimeError(
            "Robot must be at Position 1"
        )

    print("\nMoving Position 1 -> Position 2")

    lift_z = POSITION_1["Z"] - Z_LIFT_STEPS

    # Lift Z before horizontal movement.
    move_axis("Z", lift_z)

    # Move to Position 2 in XY.
    move_axis("X", POSITION_2["X"])
    move_axis("Y", POSITION_2["Y"])

    # Lower Z to Position 2.
    move_axis("Z", POSITION_2["Z"])

    print("\nPosition 2 reached")
    show_position()


# ============================================
# 12. Main
# ============================================

def main():

    try:

        initialize_gpio()

        print("===================================")
        print(" Raspberry Pi 5 XYZ Auto Move")
        print(" S-Curve + Homing")
        print("===================================")

        print("Commands:")
        print("HOME  - Home all axes")
        print("GO 1  - Move to Position 1")
        print("GO 2  - Move Position 1 to 2")
        print("POS   - Show current position")
        print("Q     - Exit")

        print("\nHome sensor states:")

        for axis in PINS:
            state = (
                "PRESSED"
                if home_pressed(axis)
                else "RELEASED"
            )
            print(f"{axis}: {state}")

        while True:

            command = input(
                "\nCommand > "
            ).strip().upper()

            try:

                if command == "Q":
                    break

                elif command == "HOME":
                    home_all()

                elif command == "GO 1":
                    go_position_1()

                elif command == "GO 2":
                    go_position_2()

                elif command == "POS":
                    show_position()

                else:
                    print("Invalid command")

            except Exception as e:
                print(f"ERROR: {e}")
                print(
                    "Check position and home again "
                    "if position is unknown."
                )

    except (KeyboardInterrupt, EOFError):
        print("\nProgram interrupted")

    finally:

        disable_all()

        for motor in motors.values():
            motor["PUL"].off()

            for device in motor.values():
                device.close()

        for sensor in sensors.values():
            sensor.close()

        print("GPIO released")


if __name__ == "__main__":
    main()
