from gpiozero import OutputDevice
import time
import math


# ============================================================
# 1. GPIO 핀 설정 (BCM GPIO 번호)
# ============================================================

AXIS_PINS = {
    "X": {
        "EN": 16,
        "DIR": 19,
        "PUL": 20
    },
    "Y": {
        "EN": 22,
        "DIR": 23,
        "PUL": 24
    },
    "Z": {
        "EN": 5,
        "DIR": 6,
        "PUL": 13
    },
    "R": {
        "EN": 18,
        "DIR": 17,
        "PUL": 27
    }
}


# ============================================================
# 2. 모션 설정
# ============================================================

# 최대 속도 [step/s]
MAX_STEP_RATE = {
    "X": 600,
    "Y": 600,
    "Z": 400,
    "R": 400
}

# 최대 가속도 [step/s²]
MAX_ACCEL = {
    "X": 1200,
    "Y": 1200,
    "Z": 800,
    "R": 800
}

# STEP HIGH 유지 시간
PULSE_WIDTH = 0.0001

# 제어 주기
CONTROL_DT = 0.001


# ============================================================
# 3. Input Shaping 설정
# ============================================================

INPUT_SHAPING = True

RESONANCE_FREQ = {
    "X": 40.0,
    "Y": 40.0,
    "Z": 40.0,
    "R": 40.0
}

DAMPING_RATIO = {
    "X": 0.05,
    "Y": 0.05,
    "Z": 0.05,
    "R": 0.05
}


# ============================================================
# 4. GPIO 객체 생성
#
# 현재 배선 기준
# EN LOW  = Disable
# EN HIGH = Enable
# ============================================================

motors = {}

for axis, pins in AXIS_PINS.items():
    motors[axis] = {
        "EN": OutputDevice(
            pins["EN"],
            active_high=True,
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


# ============================================================
# 5. 모든 모터 Disable
# ============================================================

def disable_all():

    for axis in motors:
        motors[axis]["EN"].off()


# ============================================================
# 6. S-Curve
# Quintic Smoothstep
# ============================================================

def s_curve_position(t, total_time, total_steps):

    if t <= 0:
        return 0.0

    if t >= total_time:
        return float(total_steps)

    s = t / total_time

    smooth = (
        10 * s**3
        - 15 * s**4
        + 6 * s**5
    )

    return total_steps * smooth


# ============================================================
# 7. S-Curve 이동시간 계산
# ============================================================

def calculate_move_time(axis, steps):

    max_speed = MAX_STEP_RATE[axis]
    max_accel = MAX_ACCEL[axis]

    time_speed = 1.875 * steps / max_speed

    time_accel = math.sqrt(
        5.7735 * steps / max_accel
    )

    total_time = max(
        time_speed,
        time_accel,
        0.05
    )

    return total_time


# ============================================================
# 8. ZVD Input Shaper 계산
# ============================================================

def get_zvd_shaper(axis):

    freq = RESONANCE_FREQ[axis]
    zeta = DAMPING_RATIO[axis]

    zeta = max(
        0.0,
        min(zeta, 0.99)
    )

    sqrt_term = math.sqrt(
        1.0 - zeta * zeta
    )

    K = math.exp(
        (-zeta * math.pi) / sqrt_term
    )

    Td = 1.0 / (
        2.0 * freq * sqrt_term
    )

    A1 = 1.0 / (
        (1.0 + K) ** 2
    )

    A2 = (
        2.0 * K
    ) / (
        (1.0 + K) ** 2
    )

    A3 = (
        K ** 2
    ) / (
        (1.0 + K) ** 2
    )

    return [
        (0.0, A1),
        (Td, A2),
        (2.0 * Td, A3)
    ]


# ============================================================
# 9. Input Shaping 적용 위치 계산
# ============================================================

def shaped_position(
    axis,
    t,
    move_time,
    total_steps
):

    if not INPUT_SHAPING:

        return s_curve_position(
            t,
            move_time,
            total_steps
        )

    shaper = get_zvd_shaper(axis)

    position = 0.0

    for delay, amplitude in shaper:

        position += (
            amplitude
            * s_curve_position(
                t - delay,
                move_time,
                total_steps
            )
        )

    return position


# ============================================================
# 10. STEP 펄스
# ============================================================

def step_pulse(motor):

    motor["PUL"].on()

    time.sleep(PULSE_WIDTH)

    motor["PUL"].off()


# ============================================================
# 11. 모터 이동
# ============================================================

def move_motor(
    axis,
    direction,
    steps
):

    motor = motors[axis]

    # --------------------------------------------------------
    # Enable
    # --------------------------------------------------------

    motor["EN"].on()


    # --------------------------------------------------------
    # 방향
    # --------------------------------------------------------

    if direction == "H":
        motor["DIR"].on()

    else:
        motor["DIR"].off()


    # DIR / EN 안정화
    time.sleep(0.01)


    # --------------------------------------------------------
    # 이동 시간 계산
    # --------------------------------------------------------

    move_time = calculate_move_time(
        axis,
        steps
    )

    shaper = get_zvd_shaper(axis)

    if INPUT_SHAPING:

        final_delay = shaper[-1][0]

    else:

        final_delay = 0.0


    total_time = (
        move_time
        + final_delay
    )


    # --------------------------------------------------------
    # 정보 출력
    # --------------------------------------------------------

    print()
    print("--------------------------------")
    print(f"{axis}축 이동 시작")
    print(f"방향        : {direction}")
    print(f"스텝        : {steps}")
    print(
        f"최대속도    : "
        f"{MAX_STEP_RATE[axis]} step/s"
    )
    print(
        f"최대가속도  : "
        f"{MAX_ACCEL[axis]} step/s²"
    )

    if INPUT_SHAPING:

        print("S-Curve      : ON")
        print("Input Shaper : ZVD")

        print(
            f"공진주파수   : "
            f"{RESONANCE_FREQ[axis]} Hz"
        )

    else:

        print("S-Curve      : ON")
        print("Input Shaper : OFF")

    print("--------------------------------")


    # --------------------------------------------------------
    # 실제 STEP 출력
    # --------------------------------------------------------

    emitted_steps = 0

    start_time = time.perf_counter()


    while emitted_steps < steps:

        now = time.perf_counter()

        elapsed = (
            now
            - start_time
        )


        # ====================================================
        # 중요 수정 부분
        #
        # 이동시간 종료 후에는
        # 강제로 target_steps = steps
        #
        # 999.999999 → int() → 999
        # 때문에 무한루프에 빠지는 문제 방지
        # ====================================================

        if elapsed >= total_time:

            target_steps = steps

        else:

            target_position = shaped_position(
                axis,
                elapsed,
                move_time,
                steps
            )

            target_steps = min(
                int(target_position),
                steps
            )


        # ----------------------------------------------------
        # 필요한 만큼 STEP 발생
        # ----------------------------------------------------

        while (
            emitted_steps < target_steps
            and
            emitted_steps < steps
        ):

            step_pulse(motor)

            emitted_steps += 1


        time.sleep(CONTROL_DT)


    # --------------------------------------------------------
    # 이동 완료
    # --------------------------------------------------------

    print(
        f">> 이동 완료 : "
        f"{emitted_steps} STEP"
    )


    # --------------------------------------------------------
    # 이동 완료 후 모터 Disable
    # --------------------------------------------------------

    motor["EN"].off()

    print(
        f">> {axis}축 모터 전원 차단 "
        f"(Disable)"
    )

    print()


# ============================================================
# 12. 메인
# ============================================================

disable_all()


print()
print("========================================")
print(" Raspberry Pi 5")
print(" S-Curve + ZVD Input Shaping")
print("========================================")

print()
print("입력 형식 : [축] [방향] [스텝]")
print()
print("예:")
print("X L 100")
print("X H 500")
print("Y L 1000")
print("Z H 300")
print("R L 200")
print()
print("종료 : Q")
print("========================================")
print()


try:

    while True:

        command = input(
            "입력 > "
        ).strip().upper()


        # ----------------------------------------------------
        # 종료
        # ----------------------------------------------------

        if command == "Q":

            print()
            print("프로그램을 종료합니다.")

            break


        # ----------------------------------------------------
        # 입력 분리
        # ----------------------------------------------------

        parts = command.split()


        if len(parts) != 3:

            print()
            print(
                "잘못된 입력입니다."
            )

            print(
                "예: X L 100"
            )

            print()

            continue


        axis = parts[0]

        direction = parts[1]


        # ----------------------------------------------------
        # 축 확인
        # ----------------------------------------------------

        if axis not in AXIS_PINS:

            print()
            print(
                "축은 X, Y, Z, R 중 "
                "하나를 입력하세요."
            )
            print()

            continue


        # ----------------------------------------------------
        # 방향 확인
        # ----------------------------------------------------

        if direction not in [
            "H",
            "L"
        ]:

            print()
            print(
                "방향은 H 또는 L만 "
                "입력할 수 있습니다."
            )
            print()

            continue


        # ----------------------------------------------------
        # STEP 확인
        # ----------------------------------------------------

        try:

            steps = int(
                parts[2]
            )

        except ValueError:

            print()
            print(
                "스텝 수는 숫자로 "
                "입력하세요."
            )
            print()

            continue


        if steps <= 0:

            print()
            print(
                "스텝 수는 "
                "1 이상이어야 합니다."
            )
            print()

            continue


        # ----------------------------------------------------
        # 모터 이동
        # ----------------------------------------------------

        try:

            move_motor(
                axis,
                direction,
                steps
            )

        except Exception as e:

            # 해당 명령에서 문제가 나더라도
            # 가능한 경우 프로그램 전체가
            # 종료되지 않도록 처리

            motors[axis]["EN"].off()

            print()
            print(
                "모터 이동 중 오류 발생:"
            )

            print(e)

            print()


        # ----------------------------------------------------
        # 다시 다음 명령 입력
        # ----------------------------------------------------

        print(
            "다음 명령을 입력하세요."
        )

        print()


except KeyboardInterrupt:

    print()
    print("강제 종료")


finally:

    # ========================================================
    # 프로그램 종료 시 모든 모터 Disable
    # ========================================================

    disable_all()


    # GPIO 객체 해제
    for axis in motors:

        motors[axis]["EN"].close()

        motors[axis]["DIR"].close()

        motors[axis]["PUL"].close()


    print()
    print(
        "모든 모터 전원을 차단하고 "
        "안전하게 종료합니다."
    )