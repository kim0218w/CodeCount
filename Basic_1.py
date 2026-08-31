import gpiod
import gpiod.line as gpiod_line
import time
import threading
import sys

# ==================================================
# 1. 3축 하드웨어 핀 세팅 (라파 5 / gpiod v2.x 기준)
# ==================================================
X_DIR, X_PULSE, X_ENA = 19,20,16
Y_DIR, Y_PULSE, Y_ENA = 23,24,22
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

# 초기 상태: 모든 핀 HIGH 인가 (부팅 시 안전하게 전체 ENA 비활성화 등)
request.set_values({pin: gpiod_line.Value.ACTIVE for pin in all_pins})
time.sleep(0.5)

# ==================================================
# 2. 🔌 특정 축만 전류 인가하고 나머지 차단하는 헬퍼 함수
# ==================================================
def enable_only_axis(active_axis_str):
    """
    선택된 축의 ENA는 LOW(활성화/전류 공급), 
    나머지 축의 ENA는 HIGH(비활성화/전류 차단)로 설정합니다.
    (※ 드라이버에 따라 활성화 레벨이 반대라면 INACTIVE와 ACTIVE를 교체하세요)
    """
    ena_map = {
        "AXIS_X": X_ENA,
        "AXIS_Y": Y_ENA,
        "AXIS_Z": Z_ENA
    }
    
    for axis_name, ena_pin in ena_map.items():
        if axis_name == active_axis_str:
            # 구동할 축: 전류 공급 (활성화)
            request.set_value(ena_pin, gpiod_line.Value.INACTIVE)
        else:
            # 나머지 축: 전류 차단 (토크 해제)
            request.set_value(ena_pin, gpiod_line.Value.ACTIVE)

def disable_all_motors():
    """모든 모터의 전류를 차단합니다."""
    for ena_pin in [X_ENA, Y_ENA, Z_ENA]:
        request.set_value(ena_pin, gpiod_line.Value.ACTIVE)

# ==================================================
# 3. 🎮 수동 모드: 연속 구동용 멀티스레드 로직
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
    
    # 구동이 끝나면 해당 축 전류 차단
    if axis_str == "AXIS_X": request.set_value(X_ENA, gpiod_line.Value.ACTIVE)
    elif axis_str == "AXIS_Y": request.set_value(Y_ENA, gpiod_line.Value.ACTIVE)
    elif axis_str == "AXIS_Z": request.set_value(Z_ENA, gpiod_line.Value.ACTIVE)
    
    print(f"🛑 [{axis_str}] 연속 구동 스레드 안전 정지 및 전류 차단.")

def handle_manual_control(axis_str, action_str, direction_str):
    global running_flags, active_threads

    if axis_str == "AXIS_X": dir_pin, pulse_pin = X_DIR, X_PULSE
    elif axis_str == "AXIS_Y": dir_pin, pulse_pin = Y_DIR, Y_PULSE
    elif axis_str == "AXIS_Z": dir_pin, pulse_pin = Z_DIR, Z_PULSE
    else: return

    if action_str == "START":
        if running_flags[axis_str]: return
        
        # 움직일 축만 전류를 켜고 나머지는 차단
        enable_only_axis(axis_str)
        time.sleep(0.01)

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
# 4. ⚙️ 자동 모드: 정밀 이동용 S-Curve 알고리즘
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

    # 움직일 축만 전류 인가, 나머지 축 전류 차단
    enable_only_axis(axis_str)
    time.sleep(0.02)

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
        
    # 구동 완료 후 해당 축 전류 차단
    if axis_str == "AXIS_X": request.set_value(X_ENA, gpiod_line.Value.ACTIVE)
    elif axis_str == "AXIS_Y": request.set_value(Y_ENA, gpiod_line.Value.ACTIVE)
    elif axis_str == "AXIS_Z": request.set_value(Z_ENA, gpiod_line.Value.ACTIVE)
    
    print(f"▶ [{axis_str} 자동 구동 완료 및 전류 차단]")

# ==================================================
# 5. 🚀 부팅 시 자동 테스트 모션 함수
# ==================================================
def run_startup_test():
    print("==================================================")
    print(" 🔍 시스템 부팅 완료: 3축 모터 초기화 테스트 시작")
    print("==================================================")
    
    test_axes = [
        ("AXIS_X", X_DIR, X_PULSE, X_ENA),
        ("AXIS_Y", Y_DIR, Y_PULSE, Y_ENA),
        ("AXIS_Z", Z_DIR, Z_PULSE, Z_ENA)
    ]
    
    test_steps = 400  
    
    for axis_name, dir_pin, pulse_pin, ena_pin in test_axes:
        # 테스트할 축만 전류 인가, 나머지 차단
        enable_only_axis(axis_name)
        time.sleep(0.05)

        print(f"👉 [{axis_name}] 정방향(CW) 테스트 중...")
        request.set_value(dir_pin, gpiod_line.Value.INACTIVE)
        time.sleep(0.05)
        
        for _ in range(test_steps):
            request.set_value(pulse_pin, gpiod_line.Value.INACTIVE)
            time.sleep(0.0015)
            request.set_value(pulse_pin, gpiod_line.Value.ACTIVE)
            time.sleep(0.0015)
            
        time.sleep(0.3) 
        
        print(f"👉 [{axis_name}] 역방향(CCW) 복귀 중...")
        request.set_value(dir_pin, gpiod_line.Value.ACTIVE)
        time.sleep(0.05)
        
        for _ in range(test_steps):
            request.set_value(pulse_pin, gpiod_line.Value.INACTIVE)
            time.sleep(0.0015)
            request.set_value(pulse_pin, gpiod_line.Value.ACTIVE)
            time.sleep(0.0015)
            
        # 테스트 종료 후 해당 축 전류 차단
        request.set_value(ena_pin, gpiod_line.Value.ACTIVE)
        print(f"✅ [{axis_name}] 테스트 완료 및 전류 차단\n")
        time.sleep(0.5)

    print("🎉 모든 축의 초기화 테스트가 성공적으로 끝났습니다!")

# ==================================================
# 6. 로컬 테스트용 콘솔 인터페이스
# ==================================================
def local_console_interface():
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
        disable_all_motors()
        request.release()
        chip.close()
        print("안전하게 하드웨어 자원 반환 완료.")

if __name__ == "__main__":
    local_console_interface()
