
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

ALPHA_PINS = {
    "PUL": 11,
    "DIR": 9,
    "ENA": 10
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

PULSES_PER_MM = {
    "X": 794.70,
    "Y": 843.59,
    "Z": 765.55
}

# ============================================
# 3. ZVD Input Shaping
# ============================================

INPUT_SHAPING = True

RESONANCE_FREQ = {
    "X": 40.0,
    "Y": 40.0,
    "Z": 40.0
}

DAMPING_RATIO = {
    "X": 0.05,
    "Y": 0.05,
    "Z": 0.05
}

# ============================================
# 4. Homing Configuration
# ============================================

HOME_ORDER = ["Z", "X", "Y"]
HOME_RATE = 1500.0
MAX_HOME_SECONDS = 240.0

MAX_HOME_STEPS = {
    "X": 200000,
    "Y": 200000,
    "Z": 220000
}

MAX_POSITION_STEPS = {
    "X": 200000,
    "Y": 200000,
    "Z": 220000
}

# ============================================
# 5. Saved Positions
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

# ============================================
# 6. Alpha Configuration
# ============================================

ALPHA_STEPS = 1050

ALPHA_OPEN_DIRECTION = "L"
ALPHA_CLOSE_DIRECTION = "H"

ALPHA_PULSE_HIGH_S = 0.0002
ALPHA_PULSE_LOW_S = 0.001

PICKUP_WAIT_S = 1.0
RELEASE_WAIT_S = 1.0

# ============================================
# 7. Global State
# ============================================

motors = {}
sensors = {}
alpha = {}

position_steps = {
    "X": None,
    "Y": None,
    "Z": None
}

alpha_state = "UNKNOWN"

# ============================================
# 8. GPIO Initialization
# ============================================

def make_motor(pins):

    return {
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


def initialize_gpio():

    global alpha

    for axis, pins in PINS.items():

        motors[axis] = make_motor(pins)

        sensors[axis] = Button(
            pins["HOME"],
            pull_up=True,
            bounce_time=0.05
        )

    alpha = make_motor(ALPHA_PINS)


def home_pressed(axis):

    state = sensors[axis].is_pressed

    return not state if HOME_SIGNAL_INVERTED else state


def set_direction(motor, direction):

    if direction == "H":
        motor["DIR"].on()

    elif direction == "L":
        motor["DIR"].off()

    else:
        raise ValueError("Invalid direction")

    time.sleep(0.01)


def pulse(motor, high_time):

    motor["PUL"].on()
    time.sleep(high_time)
    motor["PUL"].off()


def invalidate_positions():

    for axis in position_steps:
        position_steps[axis] = None


# ============================================
# 9. Homing Functions
# ============================================

def home_axis(axis):

    if home_pressed(axis):
        raise RuntimeError(
            f"{axis}: Home switch already pressed"
        )

    motor = motors[axis]

    print(f"[{axis}] Homing towards H")

    set_direction(motor, "H")

    motor["ENA"].on()
    time.sleep(0.02)

    start = time.perf_counter()
    count = 0
    interval = 1.0 / HOME_RATE

    try:

        while not home_pressed(axis):

            if time.perf_counter() - start >= MAX_HOME_SECONDS:
                raise TimeoutError(
                    f"{axis}: Homing timeout"
                )

            if count >= MAX_HOME_STEPS[axis]:
                raise RuntimeError(
                    f"{axis}: Homing step limit"
                )

            t0 = time.perf_counter()

            pulse(motor, PULSE_HIGH_S)
            count += 1

            remaining = interval - (
                time.perf_counter() - t0
            )

            if remaining > 0:
                time.sleep(remaining)

        position_steps[axis] = 0

        print(f"[{axis}] HOME detected")

    finally:

        motor["PUL"].off()
        motor["ENA"].off()


def home_all():

    for axis in PINS:

        if home_pressed(axis):
            raise RuntimeError(
                f"{axis}: Home switch already active"
            )

    invalidate_positions()

    try:

        for axis in HOME_ORDER:
            home_axis(axis)

    except BaseException:

        invalidate_positions()
        raise

    print("XYZ homing completed")
    show_position()


# ============================================
# 10. S-Curve Functions
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

    if t <= 0:
        return 0.0

    if t >= duration:
        return float(steps)

    s = t / duration

    smooth = (
        10 * s**3
        - 15 * s**4
        + 6 * s**5
    )

    return steps * smooth


# ============================================
# 11. ZVD Input Shaper
# ============================================

def get_zvd_shaper(axis):

    freq = RESONANCE_FREQ[axis]
    zeta = DAMPING_RATIO[axis]

    if freq <= 0:
        raise ValueError("Invalid resonance frequency")

    zeta = max(0.0, min(zeta, 0.99))

    sqrt_term = math.sqrt(1.0 - zeta * zeta)

    K = math.exp(
        (-zeta * math.pi) / sqrt_term
    )

    Td = 1.0 / (
        2.0 * freq * sqrt_term
    )

    A1 = 1.0 / ((1.0 + K) ** 2)
    A2 = 2.0 * K / ((1.0 + K) ** 2)
    A3 = (K ** 2) / ((1.0 + K) ** 2)

    return [
        (0.0, A1),
        (Td, A2),
        (2.0 * Td, A3)
    ]


def shaped_position(axis, t, duration, steps):

    if not INPUT_SHAPING:

        return s_curve_position(
            t, duration, steps
        )

    result = 0.0

    for delay, amplitude in get_zvd_shaper(axis):

        result += (
            amplitude
            * s_curve_position(
                t - delay,
                duration,
                steps
            )
        )

    return result


# ============================================
# 12. XYZ Axis Movement
# ============================================

def move_axis(axis, target):

    current = position_steps[axis]

    if current is None:
        raise RuntimeError(
            f"{axis}: Homing required"
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

    set_direction(motor, direction)

    motor["ENA"].on()
    time.sleep(0.02)

    duration = move_duration(axis, steps)

    if INPUT_SHAPING:
        final_delay = get_zvd_shaper(axis)[-1][0]
    else:
        final_delay = 0.0

    total_time = duration + final_delay

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

            if elapsed >= total_time:
                expected = steps

            else:
                expected = min(
                    steps,
                    int(
                        shaped_position(
                            axis,
                            elapsed,
                            duration,
                            steps
                        )
                    )
                )

            # One pulse per iteration to avoid large bursts.
            if done < expected:

                pulse(motor, PULSE_HIGH_S)
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
# 13. Alpha Motor Control
# ============================================

def move_alpha(direction, steps):

    motor = alpha

    set_direction(motor, direction)

    motor["ENA"].on()
    time.sleep(0.02)

    try:

        for _ in range(steps):

            pulse(
                motor,
                ALPHA_PULSE_HIGH_S
            )

            time.sleep(
                ALPHA_PULSE_LOW_S
            )

    finally:

        motor["PUL"].off()
        motor["ENA"].off()


def alpha_open():

    global alpha_state

    if alpha_state == "OPEN":
        return

    if alpha_state != "CLOSED":
        raise RuntimeError(
            "Alpha state unknown"
        )

    print("[ALPHA] Opening - G3")

    alpha_state = "UNKNOWN"

    move_alpha(
        ALPHA_OPEN_DIRECTION,
        ALPHA_STEPS
    )

    alpha_state = "OPEN"

    print("[ALPHA] Open completed")


def alpha_close():

    global alpha_state

    if alpha_state == "CLOSED":
        return

    if alpha_state != "OPEN":
        raise RuntimeError(
            "Alpha state unknown"
        )

    print("[ALPHA] Closing - G9")

    alpha_state = "UNKNOWN"

    move_alpha(
        ALPHA_CLOSE_DIRECTION,
        ALPHA_STEPS
    )

    alpha_state = "CLOSED"

    print("[ALPHA] Close completed")


# ============================================
# 14. Position Display
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

    print(f"Alpha: {alpha_state}")


# ============================================
# 15. Position 1 Movement
# ============================================

def go_position_1():

    print("\nMoving to Position 1")

    safe_z = min(
        position_steps["Z"],
        POSITION_1["Z"] - Z_LIFT_STEPS
    )

    if safe_z < 0:
        raise RuntimeError("Invalid safe Z")

    move_axis("Z", safe_z)

    move_axis("X", POSITION_1["X"])
    move_axis("Y", POSITION_1["Y"])

    move_axis("Z", POSITION_1["Z"])

    print("Position 1 reached")


# ============================================
# 16. Automatic Transfer
# ============================================

def start_transfer():

    if any(
        position_steps[axis] is None
        for axis in PINS
    ):
        raise RuntimeError(
            "XYZ homing required"
        )

    if alpha_state != "CLOSED":
        raise RuntimeError(
            "Alpha must be confirmed closed"
        )

    print("\n===================================")
    print(" Automatic Transfer START")
    print("===================================")

    # Step 1: Move to Position 1
    go_position_1()

    # Step 2: Open Alpha
    alpha_open()
    time.sleep(PICKUP_WAIT_S)

    # Step 3: Lift Z
    lift_z = POSITION_1["Z"] - Z_LIFT_STEPS
    move_axis("Z", lift_z)

    # Step 4: Move XY to Position 2
    move_axis("X", POSITION_2["X"])
    move_axis("Y", POSITION_2["Y"])

    # Step 5: Lower Z
    move_axis("Z", POSITION_2["Z"])

    # Step 6: Close Alpha
    alpha_close()
    time.sleep(RELEASE_WAIT_S)

    print("\nAutomatic transfer completed")
    show_position()


# ============================================
# 17. Main
# ============================================

def main():

    global alpha_state

    try:

        initialize_gpio()

        print("===================================")
        print(" Raspberry Pi 5 XYZ + Alpha")
        print(" S-Curve + ZVD Input Shaping")
        print("===================================")

        print("Commands:")
        print("HOME        - Home XYZ")
        print("START       - Full automatic transfer")
        print("G3          - Open Alpha")
        print("G9          - Close Alpha")
        print("SET CLOSED  - Confirm Alpha closed")
        print("SET OPEN    - Confirm Alpha open")
        print("POS         - Show position")
        print("Q           - Exit")

        while True:

            command = input(
                "\nCommand > "
            ).strip().upper()

            try:

                if command == "Q":
                    break

                elif command == "HOME":
                    home_all()

                elif command == "START":
                    start_transfer()

                elif command == "G3":
                    alpha_open()

                elif command == "G9":
                    alpha_close()

                elif command == "SET CLOSED":
                    alpha_state = "CLOSED"
                    print("Alpha confirmed CLOSED")

                elif command == "SET OPEN":
                    alpha_state = "OPEN"
                    print("Alpha confirmed OPEN")

                elif command == "POS":
                    show_position()

                else:
                    print("Invalid command")

            except Exception as e:

                print(f"ERROR: {e}")
                print("Verify hardware before continuing")

    except (KeyboardInterrupt, EOFError):

        print("\nProgram interrupted")

    finally:

        all_motors = list(motors.values())

        if alpha:
            all_motors.append(alpha)

        for motor in all_motors:

            motor["PUL"].off()
            motor["ENA"].off()

            for device in motor.values():
                device.close()

        for sensor in sensors.values():
            sensor.close()

        print("GPIO released")


if __name__ == "__main__":
    main()
