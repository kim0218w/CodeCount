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
# [수정] ENA+ 3.3V, ENA- GPIO 배선(공통 애노드)에 맞춰 EN 초기값을 LOW로 설정
# ============================================================

motors = {}

for axis, pins in AXIS_PINS.items():
    motors[axis] = {
        "EN": OutputDevice(
            pins["EN"],
            active_high=True,
            initial_value=False  # LOW -> ENA 통전 -> 모터 Disable (초기 대기 상태)
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
# [수정] LOW 출력 = ENA 전류 통전 = 모터 무전력/무력화
# ============================================================

def disable_all():
    for axis in motors:
        motors[axis]["EN"].off()


# ============================================================
# 6. S-Curve (Quintic Smoothstep)
# ============================================================

def s_curve_position(t, total_time, total_steps):
    if t <= 0:
        return 0.0
    if t >= total_time:
        return float(total_steps)

    s = t / total_time
    smooth = 10 * s**3 - 15 * s**4 + 6 * s**5
    return total_steps * smooth


# ============================================================
# 7. S-Curve 이동시간 계산
# ============================================================

def calculate_move_time(axis, steps):
    max_speed = MAX_STEP_RATE[axis]
    max_accel = MAX_ACCEL[axis]

    time_speed = 1.875 * steps / max_speed
    time_accel = math.sqrt(5.7735 * steps / max_accel)

    total_time = max(time_speed, time_accel, 0.05)
    return total_time


# ============================================================
# 8. ZVD Input Shaper 계산
# ============================================================

def get_zvd_shaper(axis):
    freq = RESONANCE_FREQ[axis]
    zeta = DAMPING_RATIO[axis]
    zeta = max(0.0, min(zeta, 0.99))

    sqrt_term = math.sqrt(1.0 - zeta * zeta)
    K = math.exp((-zeta * math.pi) / sqrt_term)
    Td = 1.0 / (2.0 * freq * sqrt_term)

    A1 = 1.0 / ((1.0 + K) ** 2)
    A2 = (2.0 * K) / ((1.0 + K) ** 2)
    A3 = (K**2) / ((1.0 + K) ** 2)

    return [
        (0.0, A1),
        (Td, A2),
        (2.0 * Td, A3)
    ]


# ============================================================
# 9. Input Shaping이 적용된 위치 계산
# ============================================================

def shaped_position(axis, t, move_time, total_steps):
    if not INPUT_SHAPING:
        return s_curve_position(t, move_time, total_steps)

    shaper = get_zvd_shaper(axis)
    position = 0.0

    for delay, amplitude in shaper:
        position += amplitude * s_curve_position(t - delay, move_time, total_steps)

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
    # [수정] 공통 애노드 기준 HIGH = ENA 차단 = 모터 전원 ON (활성화)
    # --------------------------------------------------------
    motor["EN"].on()

    # --------------------------------------------------------
    # 방향
    # --------------------------------------------------------
    if direction == "H":
        motor["DIR"].on()
    else:
        motor["DIR"].off()

    # DIR 및 ENA 전원 안정화 대기
    time.sleep(0.01)

    # --------------------------------------------------------
    # 이동시간 계산
    # --------------------------------------------------------
    move_time = calculate_move_time(axis, steps)
    shaper = get_zvd_shaper(axis)

    final_delay = shaper[-1][0] if INPUT_SHAPING else 0
    total_time = move_time + final_delay

    print()
    print("--------------------------------")
    print(f"{axis}축 이동 시작")
    print(f"방향        : {direction}")
    print(f"스텝        : {steps}")
    print(f"최대속도    : {MAX_STEP_RATE[axis]} step/s")
    print(f"최대가속도  : {MAX_ACCEL[axis]} step/s²")

    if INPUT_SHAPING:
        print("S-Curve      : ON")
        print("Input Shaper : ZVD")
        print(f"공진주파수   : {RESONANCE_FREQ[axis]} Hz")
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
        elapsed = now - start_time

        target_position = shaped_position(axis, elapsed, move_time, steps)
        target_steps = min(int(target_position), steps)

        while emitted_steps < target_steps and emitted_steps < steps:
            step_pulse(motor)
            emitted_steps += 1

        if elapsed >= total_time and emitted_steps >= steps:
            break

        time.sleep(CONTROL_DT)

    # 잔여 STEP 보정
    while emitted_steps < steps:
        step_pulse(motor)
        emitted_steps += 1

    print(f">> 이동 완료 : {emitted_steps} STEP")

    # --------------------------------------------------------
    # [수정] 이동 완료 후 해당 축 모터 전원 차단 (발열 방지)
    # --------------------------------------------------------
    motor["EN"].off()
    print(f">> {axis}축 모터 전원 차단 (Disable)")
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
print("예시      : X L 100 / Y H 500 / Z L 300 / R H 200")
print("종료      : Q")
print("========================================")
print()


try:
    while True:
        command = input("입력 > ").strip().upper()

        if command == "Q":
            break

        parts = command.split()

        if len(parts) != 3:
            print("\n잘못된 입력입니다. (예: X L 100)\n")
            continue

        axis = parts[0]
        direction = parts[1]

        if axis not in AXIS_PINS:
            print("\n축은 X, Y, Z, R 중 하나를 입력하세요.\n")
            continue

        if direction not in ["H", "L"]:
            print("\n방향은 H 또는 L만 입력할 수 있습니다.\n")
            continue

        try:
            steps = int(parts[2])
        except ValueError:
            print("\n스텝 수는 숫자로 입력하세요.\n")
            continue

        if steps <= 0:
            print("\n스텝 수는 1 이상이어야 합니다.\n")
            continue

        move_motor(axis, direction, steps)

except KeyboardInterrupt:
    print("\n강제 종료")

finally:
    # 종료 시 모든 축 Disable 및 GPIO 해제
    disable_all()

    for axis in motors:
        motors[axis]["EN"].close()
        motors[axis]["DIR"].close()
        motors[axis]["PUL"].close()

    print("모든 모터 전원을 차단하고 안전하게 종료합니다.")
