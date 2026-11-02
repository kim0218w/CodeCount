
import time
from gpiozero import OutputDevice

# ============================================
# 1. Alpha GPIO Configuration
# ============================================

ALPHA_PINS = {
    "PUL": 11,
    "DIR": 9,
    "ENA": 10
}

ENA_ACTIVE_HIGH = True

# ============================================
# 2. Motor Configuration
# ============================================

PULSE_HIGH_S = 0.0002
PULSE_LOW_S = 0.001

MAX_TEST_STEPS = 2000

# ============================================
# 3. GPIO Initialization
# ============================================

ena = OutputDevice(
    ALPHA_PINS["ENA"],
    active_high=ENA_ACTIVE_HIGH,
    initial_value=False
)

dir_pin = OutputDevice(
    ALPHA_PINS["DIR"],
    active_high=True,
    initial_value=False
)

pul = OutputDevice(
    ALPHA_PINS["PUL"],
    active_high=True,
    initial_value=False
)

# ============================================
# 4. Alpha Motor Control
# ============================================

def move_alpha(direction, steps):

    if direction not in ("H", "L"):
        print("Invalid direction")
        return

    if not 1 <= steps <= MAX_TEST_STEPS:
        print("Invalid step count")
        return

    if direction == "H":
        dir_pin.on()
    else:
        dir_pin.off()

    time.sleep(0.02)

    try:
        ena.on()
        time.sleep(0.02)

        for _ in range(steps):

            pul.on()
            time.sleep(PULSE_HIGH_S)

            pul.off()
            time.sleep(PULSE_LOW_S)

        print(
            f"Alpha moved {steps} steps ({direction})"
        )

    finally:
        pul.off()
        ena.off()


# ============================================
# 5. Main
# ============================================

try:

    print("===================================")
    print(" Alpha Motor Test")
    print("===================================")

    print("Commands:")
    print("H 100")
    print("L 100")
    print("Q")

    while True:

        command = input(
            "\nCommand > "
        ).strip().upper()

        if command == "Q":
            break

        parts = command.split()

        if len(parts) != 2:
            print("Invalid command")
            continue

        direction = parts[0]

        try:
            steps = int(parts[1])

        except ValueError:
            print("Invalid step count")
            continue

        move_alpha(direction, steps)

except KeyboardInterrupt:
    print("\nInterrupted")

finally:

    ena.off()
    pul.off()

    ena.close()
    dir_pin.close()
    pul.close()

    print("GPIO released")
