import socket
import gpiod
import gpiod.line as gpiod_line
import time
import threading

# ==================================================
# 1. 3축 하드웨어 핀 세팅 (gpiod v2.x 기준)
# ==================================================
X_DIR, X_PULSE, X_ENA = 23, 24, 22
Y_DIR, Y_PULSE, Y_ENA = 17, 27, 18
Z_DIR, Z_PULSE, Z_ENA = 6, 13, 5

chip = gpiod.Chip('/dev/gpiochip4')

# 정수(1, 2) 대신 gpiod v2.x Enum 객체 사용
line_settings = gpiod.LineSettings(
    direction=gpiod_line.Direction.OUTPUT,
    bias=gpiod_line.Bias.PULL_UP
)

all_pins = [X_DIR, X_PULSE, Y_DIR, Y_PULSE, Z_DIR, Z_PULSE]

# config 딕셔너리에 튜플 형태로 일괄 라인 요청
request = chip.request_lines(
    consumer="stepper_3axis_continuous",
    config={tuple(all_pins): line_settings}
)

# 초기 상태 HIGH 인가
request.set_values({pin: gpiod_line.Value.ACTIVE for pin in all_pins})
time.sleep(0.5)

# ==================================================
# 2. 🎮 수동 모드: 꾹 누르기 연속 구동용 멀티스레드 로직
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
# 4. 무선 네트워크 연동 수신부
# ==================================================
PC_IP = "1.247.84.191 "
PC_PORT = 9999

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print("==================================================")
print(f" 🌐 3축 로봇 팔 실시간 제어 기지국({PC_IP}) 접속 중...")
print("==================================================")

try:
    client_socket.connect((PC_IP, PC_PORT))
    print("✅ 무선 연결 성공! [수동 모드 = 꾹 누르기] 작동 준비 완료.")
    
    while True:
        raw_data = client_socket.recv(1024)
        if not raw_data:
            print("❌ PC와의 연결 단절.")
            break
            
        data = raw_data.decode('utf-8').strip()
        if not data:
            continue

        parts = data.split(':')
        
        if len(parts) == 3:
            print(f"📩 [수동 패킷 수신]: {data}")
            axis_packet, action_packet, dir_packet = parts
            handle_manual_control(axis_packet, action_packet, dir_packet)
            
        elif len(parts) == 4:
            print(f"📩 [자동 패킷 수신]: {data}")
            axis_packet, _, dir_packet, steps_packet = parts
            handle_auto_control(axis_packet, dir_packet, int(steps_packet))

except Exception as e:
    print(f"❌ 통신 런타임 에러: {e}")
finally:
    for axis in running_flags:
        running_flags[axis] = False
    request.release()
    chip.close()
    client_socket.close()
    print("안전하게 자원 반환 완료.")
