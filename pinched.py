import time
from gpiozero import OutputDevice

# ==========================================
# 핀 설정 (본인의 실제 GPIO 핀 번호로 변경하세요)
# ==========================================
DIR_PIN = 20   # 방향 제어 핀 (Direction Pin)
STEP_PIN = 21  # 스텝 신호 핀 (Step Pin)

# GPIO 출력 개체 생성
dir_pin = OutputDevice(DIR_PIN)
step_pin = OutputDevice(STEP_PIN)

def rotate_stepper(steps, delay, is_clockwise=True):
    """
    스텝 모터 회전 함수
    :param steps: 회전할 스텝 수 (NEMA 17 기본 1회전 = 200스텝)
    :param delay: 스텝 간 간격 (초 단위, 속도 제어)
    :param is_clockwise: True면 정방향, False면 역방향
    """
    # 1. 방향 설정 (High/Low 신호 전환)
    if is_clockwise:
        dir_pin.on()   # DIR = HIGH (정방향)
    else:
        dir_pin.off()  # DIR = LOW (역방향)
        
    time.sleep(0.01) # DIR 신호 안정화 대기

    # 2. STEP 신호 펄스 생성
    for _ in range(steps):
        step_pin.on()
        time.sleep(delay)
        step_pin.off()
        time.sleep(delay)

try:
    print("=== NEMA 17 방향 제어 테스트 시작 ===")
    
    # 1. 정방향 1회전 (시계 방향)
    print("1. 정방향(CW) 회전 중...")
    rotate_stepper(steps=200, delay=0.002, is_clockwise=True)
    time.sleep(1) # 1초 대기

    # 2. 역방향 1회전 (반시계 방향)
    print("2. 역방향(CCW) 회전 중...")
    rotate_stepper(steps=200, delay=0.002, is_clockwise=False)
    time.sleep(1)

    print("테스트 완료!")

except KeyboardInterrupt:
    print("\n사용자에 의해 중단됨")

finally:
    # 핀 초기화 (안전을 위해 출력 OFF)
    dir_pin.close()
    step_pin.close()
