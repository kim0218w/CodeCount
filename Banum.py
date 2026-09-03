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

    "R": {      # 로우 축
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
# 너무 작으면 Raspberry Pi Python에서 CPU 사용량 증가
CONTROL_DT = 0.001


# ============================================================
# 3. Input Shaping 설정
# ============================================================

INPUT_SHAPING = True


# 각 축의 공진 주파수
#
# !!!!! 중요 !!!!!
# 아래 40Hz는 임시 시험값
# 실제 장비의 공진주파수를 측정한 후 변경하는 것이 좋음
#
RESONANCE_FREQ = {
    "X": 40.0,
    "Y": 40.0,
    "Z": 40.0,
    "R": 40.0
}


# 감쇠비
DAMPING_RATIO = {
    "X": 0.05,
    "Y": 0.05,
    "Z": 0.05,
    "R": 0.05
}


# ============================================================
# 4. GPIO 객체 생성
# ============================================================

motors = {}

for axis, pins in AXIS_PINS.items():

    motors[axis] = {

        "EN": OutputDevice(
            pins["EN"],
            active_high=True,
            initial_value=True
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
        motors[axis]["EN"].on()


# ============================================================
# 6. S-Curve
#
# quintic smoothstep
#
# 시작
# 속도 = 0
# 가속도 = 0
#
# 종료
# 속도 = 0
# 가속도 = 0
#
# 급격한 가속/감속을 줄여 진동 감소
# ============================================================

def s_curve_position(t, total_time, total_steps):

    if t <= 0:
        return 0.0

    if t >= total_time:
        return float(total_steps)

    s = t / total_time

    # 5차 S-Curve
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

    # --------------------------------------------------------
    # 속도 제한 기준 시간
    #
    # quintic smoothstep의 최대 속도
    # 약 1.875 * distance / time
    # --------------------------------------------------------

    time_speed = (
        1.875 * steps / max_speed
    )


    # --------------------------------------------------------
    # 가속도 제한 기준 시간
    #
    # quintic smoothstep 최대 가속도 계수
    # 약 5.7735
    # --------------------------------------------------------

    time_accel = math.sqrt(
        5.7735 * steps / max_accel
    )


    # 둘 중 큰 값 사용
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

    # 잘못된 값 방지
    zeta = max(0.0, min(zeta, 0.99))

    sqrt_term = math.sqrt(
        1.0 - zeta * zeta
    )

    # 감쇠 계수
    K = math.exp(
        (-zeta * math.pi) / sqrt_term
    )


    # 공진 반주기
    Td = 1.0 / (
        2.0
        * freq
        * sqrt_term
    )


    # ZVD Shaper
    A1 = 1.0 / ((1.0 + K) ** 2)

    A2 = (
        2.0 * K
        / ((1.0 + K) ** 2)
    )

    A3 = (
        K**2
        / ((1.0 + K) ** 2)
    )


    return [
        (0.0, A1),
        (Td, A2),
        (2.0 * Td, A3)
    ]


# ============================================================
# 9. Input Shaping이 적용된 위치 계산
# ============================================================

def shaped_position(
    axis,
    t,
    move_time,
    total_steps
):

    # Input Shaping OFF
    if not INPUT_SHAPING:

        return s_curve_position(
            t,
            move_time,
            total_steps
        )


    shaper = get_zvd_shaper(axis)

    position = 0.0


    # ZVD convolution
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

def move_motor(axis, direction, steps):

    motor = motors[axis]


    # --------------------------------------------------------
    # Enable
    # LOW = Enable
    # --------------------------------------------------------

    motor["EN"].off()


    # --------------------------------------------------------
    # 방향
    # --------------------------------------------------------

    if direction == "H":

        motor["DIR"].on()

    else:

        motor["DIR"].off()


    # DIR 안정화
    time.sleep(0.005)


    # --------------------------------------------------------
    # 이동시간 계산
    # --------------------------------------------------------

    move_time = calculate_move_time(
        axis,
        steps
    )


    # Input Shaper 계산
    shaper = get_zvd_shaper(axis)


    if INPUT_SHAPING:

        final_delay = shaper[-1][0]

    else:

        final_delay = 0


    total_time = (
        move_time
        + final_delay
    )


    print()
    print("--------------------------------")
    print(f"{axis}축 이동")
    print(f"방향        : {direction}")
    print(f"스텝        : {steps}")
    print(f"최대속도    : {MAX_STEP_RATE[axis]} step/s")
    print(f"최대가속도  : {MAX_ACCEL[axis]} step/s²")

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
    # 실제 STEP 수
    # --------------------------------------------------------

    emitted_steps = 0


    start_time = time.perf_counter()


    while emitted_steps < steps:

        now = time.perf_counter()

        elapsed = (
            now
            - start_time
        )


        # 현재 목표 위치
        target_position = shaped_position(
            axis,
            elapsed,
            move_time,
            steps
        )


        # 현재 목표 스텝
        target_steps = min(
            int(target_position),
            steps
        )


        # ----------------------------------------------------
        # 필요한 STEP 출력
        # ----------------------------------------------------

        while (
            emitted_steps < target_steps
            and emitted_steps < steps
        ):

            step_pulse(motor)

            emitted_steps += 1


        # 이동 완료
        if (
            elapsed >= total_time
            and emitted_steps >= steps
        ):

            break


        time.sleep(CONTROL_DT)


    # 혹시 반올림 때문에 남은 STEP이 있으면 보정
    while emitted_steps < steps:

        step_pulse(motor)

        emitted_steps += 1


    print(
        f">> 이동 완료 : "
        f"{emitted_steps} STEP"
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
print("입력 형식")
print()
print("축 방향 스텝")
print()
print("예:")
print("X L 100")
print("X H 500")
print("Y L 1000")
print("Z H 300")
print("R L 200")
print()
print("종료 : Q")
print()
print("========================================")
print()


try:

    while True:

        command = input("입력 > ").strip().upper()


        # ====================================================
        # 종료
        # ====================================================

        if command == "Q":
            break


        parts = command.split()


        # ====================================================
        # 입력 형식 검사
        # ====================================================

        if len(parts) != 3:

            print()
            print("잘못된 입력입니다.")
            print("예: X L 100")
            print()

            continue


        axis = parts[0]

        direction = parts[1]


        # ====================================================
        # 축 확인
        # ====================================================

        if axis not in AXIS_PINS:

            print()
            print(
                "축은 X, Y, Z, R 중 "
                "하나를 입력하세요."
            )

            print()

            continue


        # ====================================================
        # 방향 확인
        # ====================================================

        if direction not in ["H", "L"]:

            print()
            print(
                "방향은 H 또는 L만 "
                "입력할 수 있습니다."
            )

            print()

            continue


        # ====================================================
        # 스텝 확인
        # ====================================================

        try:

            steps = int(parts[2])

        except ValueError:

            print()
            print(
                "스텝 수는 숫자로 입력하세요."
            )

            print()

            continue


        if steps <= 0:

            print()
            print(
                "스텝 수는 1 이상이어야 합니다."
            )

            print()

            continue


        # ====================================================
        # 이동
        # ====================================================

        move_motor(
            axis,
            direction,
            steps
        )


except KeyboardInterrupt:

    print()
    print("강제 종료")


finally:

    # ========================================================
    # 종료 시 모든 축 Disable
    # ========================================================

    disable_all()


    for axis in motors:

        motors[axis]["EN"].close()

        motors[axis]["DIR"].close()

        motors[axis]["PUL"].close()


    print(
        "모든 모터를 정지하고 종료합니다."
    )