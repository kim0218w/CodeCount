
#!/usr/bin/env python3

import math
import time
from gpiozero import OutputDevice

# ==============================================
# 1. GPIO 설정 (BCM 번호)
# ==============================================

AXIS_PINS = {
    "X": {"PUL": 26, "DIR": 19, "ENA": 13},
    "Y": {"PUL": 21, "DIR": 20, "ENA": 16},
    "Z": {"PUL": 6,  "DIR": 5,  "ENA": 0},
}

# ENA 활성화 방식
# True  : HIGH = Enable
# False : LOW  = Enable
ENA_ACTIVE_HIGH = True

# ==============================================
# 2. 모터 속도 및 가속도
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
# 3. S-Curve 위치 계산
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
# 4. 이동 시간 계산
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
# 5. 메인 프로그램
# ==============================================

def main():

    motors = {}

    try:
        # GPIO 초기화
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

        print("입력 예시:")
        print("X H 100")
        print("X L 100")
        print("Y H 100")
        print("Z H 100")
        print("종료: Q")

        while True:

            command = input(
                "\n명령 입력 > "
            ).strip().upper()

            parts = command.split()

            # 종료
            if parts == ["Q"]:
                break

            # 입력 검사
            if len(parts) != 3:
                print("입력 오류. 예: X H 100")
                continue

            axis, direction, steps_text = parts

            if axis not in motors:
                print("축은 X, Y, Z만 가능합니다.")
                continue

            if direction not in ("H", "L"):
                print("방향은 H 또는 L입니다.")
                continue

            try:
                steps = int(steps_text)

            except ValueError:
                print("스텝 수는 정수여야 합니다.")
                continue

            if not 1 <= steps <= MAX_COMMAND_STEPS:
                print("스텝 수 범위를 확인하세요.")
                continue

            motor = motors[axis]

            duration = move_duration(
                axis, steps
            )

            print(
                f"\n[{axis}축] {direction} 방향 "
                f"{steps}스텝 이동 시작"
            )

            try:
                # 회전 방향 설정
                if direction == "H":
                    motor["DIR"].on()
                else:
                    motor["DIR"].off()

                time.sleep(0.01)

                # 모터 Enable
                motor["ENA"].on()
                time.sleep(0.02)

                start = time.perf_counter()
                done = 0

                # S-Curve 펄스 출력
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
                    f"[{axis}축] 이동 완료: "
                    f"{done}스텝"
                )

            finally:
                motor["PUL"].off()
                motor["ENA"].off()

    except (KeyboardInterrupt, EOFError):
        print("\n사용자 종료")

    finally:

        # 모든 모터 Disable
        for motor in motors.values():

            motor["ENA"].off()

            for device in motor.values():
                device.close()

        print("GPIO 자원 해제 완료")


if __name__ == "__main__":
    main()
