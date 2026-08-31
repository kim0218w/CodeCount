import gpiod
import gpiod.line as gpiod_line
import time
import threading
import sys

# ==================================================
# 1. 3축 하드웨어 핀 세팅 (라파 5 / gpiod v2.x 기준)
# ==================================================
X_DIR, X_PULSE, X_ENA = 23, 24, 22
Y_DIR, Y_PULSE, Y_ENA = 17, 27, 18
Z_DIR, Z_PULSE, Z_ENA = 6, 13, 5

# 라즈베리 파이 5 OS 버전에 따라 'gpiochip4' 또는 'gpiochip0' 사용
chip = gpiod.Chip('/dev/gpiochip4')

# gpiod v2.x Enum 객체 사용 설정
line_settings = gpiod.LineSettings(
    direction=gpiod_line.Direction.OUTPUT,
    bias=gpiod_line.Bias.PULL_UP
)

all_pins = [X_DIR, X_PULSE, X_ENA, Y_DIR, Y_PULSE, Y_ENA, Z_DIR, Z_PULSE, Z_ENA]

# config 딕셔너리에 튜플 형태로 일괄 라인 요청
request = chip.request_lines(
    consumer="stepper_3axis_local",
    config={tuple(all_pins): line_settings}
)

# 초기 상태 HIGH(ACTIVE) 인가 및 ENA 핀 활성화 예시
request.set_values({pin: gpiod_line.Value.ACTIVE for pin in all_pins})
time.sleep(0.5)

# ==================================================
# 2. 🎮 수동 모드: 연속 구동용 멀티스레드 로직
# ==================================================
running_flags = {"AXIS_X": False, "AXIS_Y": False, "AXIS_Z": False}
active_threads = {}
CONTINUOUS_DELAY = 0.0008  

def continuous_run_worker(axis_str, pulse_pin):
    print(f"🔥 [{axis_str}] 실시간 연속 구동 스레드 가동!")
    while running_flags[axis_str]:
        request.set_value(pulse_pin, gpiod_line.Value.INACTIVE)
        time.sleep(CONTINUOUS_DELAY)
        request.set_value(pulse_pin, gpiod_line.Value.ACTIVE)
        time.sleep(CONTINUOUS_DELAY)
    print(f"🛑 [{axis_str}] 연속 구동 스레드 안전 정지.")

def handle_manual_control(axis_str, action_str, direction_str):
    global running_flags, active_threads

    if axis_str == "AXIS_X": dir_pin, pulse_pin = X_DIR, X_PULSE
    elif axis_str == "AXIS_Y": dir_pin, pulse_pin = Y_DIR, Y_PULSE
    elif axis_str == "AXIS_Z": dir_pin, pulse_pin = Z_DIR, Z_PULSE
    else: return

    if action_str == "START":
        if running_flags[axis_str]: return
        
        dir_val = gpiod_line.Value.INACTIVE if direction_str == "DIR_CW" else gpiod_line.Value.ACTIVE
        request.set_value(dir_pin, dir_val)
        time.sleep(0.01)

        running_flags[axis_str] = True
        t = threading.Thread(target=continuous_run_worker, args=(axis_str, pulse_pin), daemon=True)
        active_threads[axis_str] = t
        t.start()

    elif action_str == "STOP":
        running_flags[axis_str] = False

# ==================================================
# 3. ⚙️ 자동 모드: 정밀 이동용 S-Curve 알고리즘
# ==================================================
MAX_DELAY_US = 2500   
MIN_DELAY_US = 800    

def smoothstep(x):
    if x < 0.0: x = 0.0
    if x > 1.0: x = 1.0
    return x * x * (3.0 - 2.0 * x)

def get_s_curve_delay(step_index, total_steps, max_delay, min_delay):
    mid = (total_steps - 1) / 2.0
    progress = step_index / mid if step_index <= mid else (total_steps - 1 - step_index) / mid
    s = smoothstep(progress)
    delay_f = float(max_delay) - s * float(max_delay - min_delay)
    return max(delay_f, 1.0) / 1000000.0

def handle_auto_control(axis_str, direction_str, total_steps):
    if axis_str == "AXIS_X": dir_pin, pulse_pin = X_DIR, X_PULSE
    elif axis_str == "AXIS_Y": dir_pin, pulse_pin = Y_DIR, Y_PULSE
    elif axis_str == "AXIS_Z": dir_pin, pulse_pin = Z_DIR, Z_PULSE
    else: return

    dir_val = gpiod_line.Value.INACTIVE if direction_str == "DIR_CW" else gpiod_line.Value.ACTIVE
    request.set_value(dir_pin, dir_val)
    time.sleep(0.05)

    print(f"🤖 [자동 모드] {axis_str} -> {direction_str}방향 {total_steps}스텝 가감속 시작")
    for i in range(total_steps):
        d = get_s_curve_delay(i, total_steps, MAX_DELAY_US, MIN_DELAY_US)
        request.set_value(pulse_pin, gpiod_line.Value.INACTIVE)
        time.sleep(d)
        request.set_value(pulse_pin, gpiod_line.Value.ACTIVE)
        time.sleep(d)
    print(f"▶ [{axis_str} 자동 구동 완료]")

# ==================================================
# 4. 🚀 부팅 시 자동 테스트 모션 함수
# ==================================================
def run_startup_test():
    print("==================================================")
    print(" 🔍 시스템 부팅 완료: 3축 모터 초기화 테스트 시작")
    print("==================================================")
    
    # 테스트할 축 목록 (축 이름, DIR 핀, PULSE 핀)
    test_axes = [
        ("AXIS_X", X_DIR, X_PULSE),
        ("AXIS_Y", Y_DIR, Y_PULSE),
        ("AXIS_Z", Z_DIR, Z_PULSE)
    ]
    
    test_steps = 400  # 테스트 시 움직일 스텝 수 (적당히 조절 가능)
    
    for axis_name, dir_pin, pulse_pin in test_axes:
        print(f"👉 [{axis_name}] 정방향(CW) 테스트 중...")
        request.set_value(dir_pin, gpiod_line.Value.INACTIVE)
        time.sleep(0.05)
        
        for _ in range(test_steps):
            request.set_value(pulse_pin, gpiod_line.Value.INACTIVE)
            time.sleep(0.0015)
            request.set_value(pulse_pin, gpiod_line.Value.ACTIVE)
            time.sleep(0.0015)
            
        time.sleep(0.3) # 방향 전환 전 잠시 대기
        
        print(f"👉 [{axis_name}] 역방향(CCW) 복귀 중...")
        request.set_value(dir_pin, gpiod_line.Value.ACTIVE)
        time.sleep(0.05)
        
        for _ in range(test_steps):
            request.set_value(pulse_pin, gpiod_line.Value.INACTIVE)
            time.sleep(0.0015)
            request.set_value(pulse_pin, gpiod_line.Value.ACTIVE)
            time.sleep(0.0015)
            
        print(f"✅ [{axis_name}] 테스트 완료\n")
        time.sleep(0.5)

    print("🎉 모든 축의 초기화 테스트가 성공적으로 끝났습니다!")

# ==================================================
# 5. 로컬 테스트용 콘솔 인터페이스
# ==================================================
def local_console_interface():
    # 프로그램 시작 시 자동 테스트 모션 실행
    run_startup_test()

    print("==================================================")
    print(" 🤖 라즈베리 파이 5 3축 스퍼모터 단독 제어 프로그램")
    print("==================================================")
    print(" [사용법 예시]")
    print("  - 수동 시작: AXIS_X:START:DIR_CW (또는 DIR_CCW)")
    print("  - 수동 정지: AXIS_X:STOP:DIR_CW")
    print("  - 자동 이동: AXIS_X:AUTO:DIR_CW:1000 (축:모드:방향:스텝수)")
    print("  - 종료: quit")
    print("==================================================")

    try:
        while True:
            user_input = input("명령어 입력 > ").strip()
            if not user_input:
                continue
            if user_input.lower() == 'quit':
                break

            parts = user_input.split(':')

            if len(parts) == 3:
                axis_packet, action_packet, dir_packet = parts
                handle_manual_control(axis_packet, action_packet, dir_packet)
                
            elif len(parts) == 4:
                axis_packet, _, dir_packet, steps_packet = parts
                handle_auto_control(axis_packet, dir_packet, int(steps_packet))
            else:
                print("❌ 잘못된 형식입니다. 다시 입력해주세요.")

    except KeyboardInterrupt:
        print("\n사용자에 의해 강제 중단되었습니다.")
    finally:
        for axis in running_flags:
            running_flags[axis] = False
        time.sleep(0.2)
        request.release()
        chip.close()
        print("안전하게 하드웨어 자원 반환 완료.")

if __name__ == "__main__":
    local_console_interface()
