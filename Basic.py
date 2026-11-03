
import json
import math
import time
from pathlib import Path
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
# 2. XYZ Motion Configuration
# ============================================

PULSES_PER_MM = {
    "X": 794.70,
    "Y": 843.59,
    "Z": 765.55
}

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

MAX_JOG_STEPS = 250000

MAX_POSITION_STEPS = {
    "X": 200000,
    "Y": 200000,
    "Z": 250000
}

# ============================================
# 3. Homing Configuration
# ============================================

HOME_ORDER = ["Z", "X", "Y"]

HOME_RATE = 3500.0
MAX_HOME_SECONDS = 240.0

MAX_HOME_STEPS = {
    "X": 200000,
    "Y": 200000,
    "Z": 220000
}

# ============================================
# 4. Alpha Configuration
# ============================================

ALPHA_STEPS = 1050

ALPHA_OPEN_DIRECTION = "L"
ALPHA_CLOSE_DIRECTION = "H"

ALPHA_PULSE_HIGH_S = 0.0002
ALPHA_PULSE_LOW_S = 0.001

MAX_ALPHA_JOG_STEPS = 1050

# ============================================
# 5. Position Storage
# ============================================

SAVE_FILE = Path(__file__).with_name(
    "robot_positions.json"
)

motors = {}
sensors = {}
alpha = {}

position_steps = {
    "X": None,
    "Y": None,
    "Z": None
}

saved_positions = {}

alpha_state = "UNKNOWN"

# ============================================
# 6. GPIO Initialization
# ============================================

def make_motor(p):

    return {
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


def init_gpio():

    global alpha

    for axis, p in PINS.items():

        motors[axis] = make_motor(p)

        sensors[axis] = Button(
            p["HOME"],
            pull_up=True,
            bounce_time=0.05
        )

    alpha = make_motor(ALPHA_PINS)


def switch_pressed(axis):

    raw = sensors[axis].is_pressed

    if HOME_SIGNAL_INVERTED:
        return not raw

    return raw


def set_direction(motor, dir_text):

    if dir_text == "H":
        motor["DIR"].on()

    elif dir_text == "L":
        motor["DIR"].off()

    else:
        raise ValueError("Invalid direction")

    time.sleep(0.01)


def pulse(motor, high_time):

    motor["PUL"].on()
    time.sleep(high_time)
    motor["PUL"].off()


# ============================================
# 7. Position File Functions
# ============================================

def load_positions():

    if not SAVE_FILE.exists():
        return

    with SAVE_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    for number in ("1", "2"):

        saved = data.get(number)

        if not isinstance(saved, dict):
            continue

        if all(
            type(saved.get(axis)) is int
            for axis in PINS
        ):
            saved_positions[number] = {
                axis: saved[axis]
                for axis in PINS
            }


def show_position(steps):

    for axis in PINS:

        count = steps[axis]

        if count is None:
            print(f"{axis}: UNKNOWN")

        else:

            mm = count / PULSES_PER_MM[axis]

            print(
                f"{axis}: {count} steps "
                f"({mm:.3f} mm)"
            )


def save_position(number):

    if any(
        value is None
        for value in position_steps.values()
    ):
        print("ERROR: Homing required")
        return

    saved_positions[number] = position_steps.copy()

    with SAVE_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            saved_positions,
            f,
            indent=2
        )

    print(f"Position {number} saved")

    show_position(saved_positions[number])


def show_saved_positions():

    for number in ("1", "2"):

        print(f"\nPosition {number}:")

        if number in saved_positions:
            show_position(saved_positions[number])

        else:
            print("NOT SAVED")


# ============================================
# 8. Homing Functions
# ============================================

def home_axis(axis):

    if switch_pressed(axis):
        raise RuntimeError(
            f"{axis}: Home switch already active"
        )

    motor = motors[axis]

    print(f"[{axis}] Homing towards H...")

    set_direction(motor, "H")

    motor["ENA"].on()

    count = 0
    start = time.perf_counter()

    try:

        while not switch_pressed(axis):

            if (
                time.perf_counter() - start
                >= MAX_HOME_SECONDS
            ):
                raise TimeoutError(
                    f"{axis}: Homing timeout"
                )

            if count >= MAX_HOME_STEPS[axis]:
                raise RuntimeError(
                    f"{axis}: Home step limit"
                )

            t0 = time.perf_counter()

            pulse(motor, PULSE_HIGH_S)

            count += 1

            remaining = (
                1.0 / HOME_RATE
                - (time.perf_counter() - t0)
            )

            if remaining > 0:
                time.sleep(remaining)

        position_steps[axis] = 0

        print(f"[{axis}] HOME reached")

    finally:

        motor["PUL"].off()
        motor["ENA"].off()


def home_all():

    for axis in PINS:

        if switch_pressed(axis):
            print(
                f"ERROR: {axis} home switch active"
            )
            return

    for axis in PINS:
        position_steps[axis] = None

    try:

        for axis in HOME_ORDER:
            home_axis(axis)

    except BaseException:

        for axis in PINS:
            position_steps[axis] = None

        raise

    print("\nXYZ homing completed")

    show_position(position_steps)


# ============================================
# 9. S-Curve Functions
# ============================================

def move_duration(axis, steps):

    return max(
        1.875 * steps / MAX_STEP_RATE[axis],
        math.sqrt(
            5.7735 * steps / MAX_ACCEL[axis]
        ),
        0.05
    )


def shaped_steps(elapsed, total_time, steps):

    s = min(
        1.0,
        max(0.0, elapsed / total_time)
    )

    return steps * (
        10 * s**3
        - 15 * s**4
        + 6 * s**5
    )


# ============================================
# 10. XYZ Manual Jog
# ============================================

def jog(axis, dir_text, steps):

    if position_steps[axis] is None:
        print("ERROR: Homing required")
        return

    if not 1 <= steps <= MAX_JOG_STEPS:
        print("ERROR: Invalid jog step count")
        return

    toward_home = dir_text == "H"

    current = position_steps[axis]

    if toward_home:
        target = current - steps
    else:
        target = current + steps

    if not 0 <= target <= MAX_POSITION_STEPS[axis]:
        print("ERROR: Position limit exceeded")
        return

    if toward_home and switch_pressed(axis):
        print("ERROR: Home switch active")
        return

    motor = motors[axis]

    set_direction(motor, dir_text)

    motor["ENA"].on()

    done = 0
    total_time = move_duration(axis, steps)
    start = time.perf_counter()

    try:

        while done < steps:

            if toward_home and switch_pressed(axis):
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
                        shaped_steps(
                            elapsed,
                            total_time,
                            steps
                        )
                    )
                )

            if done < expected:

                pulse(motor, PULSE_HIGH_S)

                done += 1

                if toward_home:
                    position_steps[axis] -= 1
                else:
                    position_steps[axis] += 1

            else:
                time.sleep(CONTROL_INTERVAL_S)

        print(
            f"[{axis}] Moved {done} steps ({dir_text})"
        )

        show_position(position_steps)

    except BaseException:

        position_steps[axis] = None
        raise

    finally:

        motor["PUL"].off()
        motor["ENA"].off()


# ============================================
# 11. Alpha Manual Control
# ============================================

def move_alpha(dir_text, steps):

    global alpha_state

    if dir_text not in ("H", "L"):
        print("ERROR: Invalid alpha direction")
        return False

    if not 1 <= steps <= MAX_ALPHA_JOG_STEPS:
        print("ERROR: Invalid alpha step count")
        return False

    motor = alpha

    set_direction(motor, dir_text)

    alpha_state = "UNKNOWN"

    motor["ENA"].on()
    time.sleep(0.02)

    try:

        for _ in range(steps):

            motor["PUL"].on()
            time.sleep(ALPHA_PULSE_HIGH_S)

            motor["PUL"].off()
            time.sleep(ALPHA_PULSE_LOW_S)

        print(
            f"[ALPHA] Moved {steps} steps ({dir_text})"
        )

        return True

    finally:

        motor["PUL"].off()
        motor["ENA"].off()


def alpha_open():

    global alpha_state

    if alpha_state != "CLOSED":
        print("ERROR: Confirm alpha CLOSED first")
        return

    print("[ALPHA] Opening - G3")

    if move_alpha(
        ALPHA_OPEN_DIRECTION,
        ALPHA_STEPS
    ):
        alpha_state = "OPEN"
        print("[ALPHA] Open command completed")


def alpha_close():

    global alpha_state

    if alpha_state != "OPEN":
        print("ERROR: Confirm alpha OPEN first")
        return

    print("[ALPHA] Closing - G9")

    if move_alpha(
        ALPHA_CLOSE_DIRECTION,
        ALPHA_STEPS
    ):
        alpha_state = "CLOSED"
        print("[ALPHA] Close command completed")


# ============================================
# 12. Main
# ============================================

def main():

    global alpha_state

    try:

        init_gpio()
        load_positions()

        print("===================================")
        print(" XYZ + Alpha Position Setup")
        print("===================================")

        print("Commands:")
        print("HOME")
        print("X L 1000")
        print("X H 1000")
        print("Y L 1000")
        print("Z L 1000")
        print("POS")
        print("SAVE 1")
        print("SAVE 2")
        print("SHOW")
        print("A L 100")
        print("A H 100")
        print("G3")
        print("G9")
        print("SET CLOSED")
        print("SET OPEN")
        print("Q")

        print("\nHome sensor states:")

        for axis in PINS:

            state = (
                "PRESSED"
                if switch_pressed(axis)
                else "RELEASED"
            )

            print(f"{axis}: {state}")

        while True:

            command = input(
                "\nCommand > "
            ).strip().upper()

            parts = command.split()

            if not parts:
                continue

            try:

                if parts == ["Q"]:
                    break

                elif parts == ["HOME"]:
                    home_all()

                elif parts == ["POS"]:
                    show_position(position_steps)
                    print(f"Alpha: {alpha_state}")

                elif parts == ["SHOW"]:
                    show_saved_positions()

                elif (
                    len(parts) == 2
                    and parts[0] == "SAVE"
                    and parts[1] in ("1", "2")
                ):
                    save_position(parts[1])

                elif (
                    len(parts) == 3
                    and parts[0] in PINS
                    and parts[1] in ("H", "L")
                ):
                    steps = int(parts[2])

                    jog(
                        parts[0],
                        parts[1],
                        steps
                    )

                elif (
                    len(parts) == 3
                    and parts[0] == "A"
                    and parts[1] in ("H", "L")
                ):
                    steps = int(parts[2])

                    move_alpha(
                        parts[1],
                        steps
                    )

                elif parts == ["G3"]:
                    alpha_open()

                elif parts == ["G9"]:
                    alpha_close()

                elif parts == ["SET CLOSED"]:
                    alpha_state = "CLOSED"
                    print("Alpha confirmed CLOSED")

                elif parts == ["SET OPEN"]:
                    alpha_state = "OPEN"
                    print("Alpha confirmed OPEN")

                else:
                    print("Invalid command")

            except ValueError:
                print("ERROR: Invalid numeric input")

            except Exception as exc:
                print(f"ERROR: {exc}")

    except (KeyboardInterrupt, EOFError):
        print("\nInterrupted")

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
