import gpiod
import gpiod.line as gpiod_line
import time

DIR = 19
PULSE = 20
ENA = 16

chip = gpiod.Chip("/dev/gpiochip4")

settings = gpiod.LineSettings(
    direction=gpiod_line.Direction.OUTPUT
)

request = chip.request_lines(
    consumer="motor_test",
    config={
        (DIR, PULSE, ENA): settings
    }
)

# 초기값
request.set_values({
    DIR: gpiod_line.Value.INACTIVE,
    PULSE: gpiod_line.Value.ACTIVE,
    ENA: gpiod_line.Value.ACTIVE
})

time.sleep(1)

# ENA LOW = Enable
request.set_value(ENA, gpiod_line.Value.INACTIVE)

time.sleep(0.5)

# 방향
request.set_value(DIR, gpiod_line.Value.INACTIVE)

time.sleep(0.5)

print("START")

for i in range(400):

    request.set_value(PULSE, gpiod_line.Value.INACTIVE)
    time.sleep(0.005)

    request.set_value(PULSE, gpiod_line.Value.ACTIVE)
    time.sleep(0.005)

print("DONE")

request.set_value(ENA, gpiod_line.Value.ACTIVE)

request.release()
chip.close()
