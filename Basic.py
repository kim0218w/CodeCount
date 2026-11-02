
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
    "Z": {"PUL": 6,  "DIR": 5,  "ENA": 0, "HOME": 3},
}

# ============================================
# 2. Motion Configuration
# ============================================

PULSES_PER_MM = {
    "X": 794.70,
    "Y": 843.59,
    "Z": 765.55
}

ENA_ACTIVE_HIGH = True
HOME_SIGNAL_INVERTED = True

HOME_ORDER = ("Z", "X", "Y")

HOME_RATE = 500.0
MAX_HOME_SECONDS = 120.0

MAX_HOME_STEPS = {
    "X": 60000,
    "Y": 60000,
    "Z": 60000
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

MAX_JOG_STEPS = 20000

# Temporary software travel limits
MAX_POSITION_STEPS = {
    "X": 200000,
    "Y": 200000,
    "Z": 200000
}

SAVE_FILE = Path(__file__).with_name(
    "robot_positions.json"
)

motors = {}
sensors = {}

position_steps = {
    axis: None for axis in PINS
}

saved_positions = {}

# ============================================
# 3. Sensor Functions
# ============================================

def switch_pressed(axis):

    raw = sensors[axis].is_pressed

    if HOME_SIGNAL_INVERTED:
        return not raw

    return raw


def direction(axis, toward_home):

    if toward_home:
        motors[axis]["DIR"].on()
    else:
        motors[axis]["DIR"].off()

    time.sleep(0.01)


def pulse(axis):

    motors[axis]["PUL"].on()

    time.sleep(PULSE_HIGH_S)

    motors[axis]["PUL"].off()


# ============================================
# 4. GPIO Initialization
# ============================================

def init_gpio():

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


# ============================================
# 5. Position File Functions
# ============================================

def load_positions():

    if SAVE_FILE.exists():

        with SAVE_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            loaded = json.load(f)

        for key in ("1", "2"):

            data = loaded.get(key)

            if (
                isinstance(data, dict)
                and all(
                    isinstance(data.get(a), int)
                    for a in PINS
                )
            ):

                saved_positions[key] = {
                    a: data[a] for a in PINS
                }


def save_position(number):

    if any(
        value is None
        for value in position_steps.values()
    ):

        print(
            "ERROR: All axes must be homed first."
        )
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

    print(
        f"Position {number} saved to {SAVE_FILE.name}"
    )

    show_position(saved_positions[number])


def show_position(steps):

    for axis in PINS:

        count = steps[axis]

        if count is None:
            value = "UNKNOWN"

        else:
            mm = count / PULSES_PER_MM[axis]

            value = (
                f"{count} steps "
                f"({mm:.3f} mm)"
            )

        print(f"  {axis}: {value}")


# ============================================
# 6. Homing Functions
# ============================================

def home_axis(axis):

    if switch_pressed(axis):

        raise RuntimeError(
            f"{axis}: Switch already active. "
            f"Release it before homing."
        )

    print(
        f"[{axis}] Homing towards H..."
    )

    direction(axis, True)

    motor = motors[axis]

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
                    f"{axis}: Home timeout"
                )

            if count >= MAX_HOME_STEPS[axis]:

                raise RuntimeError(
                    f"{axis}: Home step limit"
                )

            t0 = time.perf_counter()

            pulse(axis)

            count += 1

            remaining = (
                1.0 / HOME_RATE
                - (time.perf_counter() - t0)
            )

            if remaining > 0:
                time.sleep(remaining)

        position_steps[axis] = 0

        print(
            f"[{axis}] HOME reached, position = 0"
        )

    finally:

        motor["PUL"].off()
        motor["ENA"].off()


def home_all():

    for axis in PINS:

        if switch_pressed(axis):

            print(
                f"ERROR: {axis} switch is "
                f"already pressed. Homing cancelled."
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

    print(
        "Homing complete: X=0, Y=0, Z=0"
    )


# ============================================
# 7. S-Curve Functions
# ============================================

def duration(axis, steps):

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
# 8. Manual Jog Movement
# ============================================

def jog(axis, dir_text, steps):

    if position_steps[axis] is None:

        print(
            "ERROR: Home all axes before jogging."
        )
        return

    if not (1 <= steps <= MAX_JOG_STEPS):

        print(
            f"ERROR: Jog steps must be "
            f"1..{MAX_JOG_STEPS}."
        )
        return

    toward_home = dir_text == "H"

    old = position_steps[axis]

    if toward_home:
        target = old - steps
    else:
        target = old + steps

    if not (
        0 <= target <= MAX_POSITION_STEPS[axis]
    ):

        print(
            "ERROR: Requested move exceeds "
            "temporary software position limit."
        )
        return

    if toward_home and switch_pressed(axis):

        print(
            "ERROR: Home switch already pressed."
        )
        return

    motor = motors[axis]

    direction(axis, toward_home)

    motor["ENA"].on()

    done = 0

    total_time = duration(axis, steps)

    start = time.perf_counter()

    try:

        while done < steps:

            if toward_home and switch_pressed(axis):

                raise RuntimeError(
                    f"{axis}: Home switch triggered "
                    "during jog"
                )

            elapsed = (
                time.perf_counter() - start
            )

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

                pulse(axis)

                done += 1

                if toward_home:
                    position_steps[axis] -= 1

                else:
                    position_steps[axis] += 1

            else:

                time.sleep(
                    CONTROL_INTERVAL_S
                )

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
# 9. Main Program
# ============================================

def main():

    try:

        init_gpio()

        load_positions()

        print(
            "==================================="
        )
        print(
            " Raspberry Pi 5 XYZ Position Setup"
        )
        print(
            " Homing + S-Curve + Position Save"
        )
        print(
            "==================================="
        )

        print("Commands:")
        print("HOME")
        print("X L 1000")
        print("X H 500")
        print("Y L 1000")
        print("Z L 1000")
        print("POS")
        print("SAVE 1")
        print("SAVE 2")
        print("SHOW")
        print("Q")

        print("\nSensor check:")

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

            # Exit
            if parts == ["Q"]:
                break

            # Homing
            elif parts == ["HOME"]:

                home_all()

            # Current position
            elif parts == ["POS"]:

                show_position(position_steps)

            # Show saved positions
            elif parts == ["SHOW"]:

                for n in ("1", "2"):

                    print(f"Position {n}:")

                    if n in saved_positions:

                        show_position(
                            saved_positions[n]
                        )

                    else:
                        print("  NOT SAVED")

            # Save position
            elif (
                len(parts) == 2
                and parts[0] == "SAVE"
                and parts[1] in ("1", "2")
            ):

                save_position(parts[1])

            # Manual movement
            elif (
                len(parts) == 3
                and parts[0] in PINS
                and parts[1] in ("H", "L")
            ):

                try:

                    steps = int(parts[2])

                except ValueError:

                    print(
                        "ERROR: Step count must "
                        "be an integer."
                    )
                    continue

                jog(
                    parts[0],
                    parts[1],
                    steps
                )

            else:

                print(
                    "Invalid command. "
                    "Example: X L 1000"
                )

    except (KeyboardInterrupt, EOFError):

        print("\nInterrupted")

    except Exception as exc:

        print(f"ERROR: {exc}")

    finally:

        for motor in motors.values():

            motor["ENA"].off()
            motor["PUL"].off()

            for device in motor.values():
                device.close()

        for sensor in sensors.values():
            sensor.close()

        print("GPIO released")


if __name__ == "__main__":
    main()
