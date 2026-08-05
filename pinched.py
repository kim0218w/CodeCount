import time
from gpiozero import OutputDevice

# GPIO 핀 설정 (BCM 번호)
ENA_PIN = 26
DIR_PIN = 20
PUL_PIN = 21

# gpiozero OutputDevice 객체 생성
ena_output = OutputDevice(ENA_PIN)
dir_output = OutputDevice(DIR_PIN)
pul_output = OutputDevice(PUL_PIN)

def enable_motor():
    """모터 활성화 (전류 공급, 고정/회전 가능)"""
    ena_output.off()  # TB6600은 LOW일 때 Enable
    time.sleep(0.05)  # ENA 켜짐 후 드라이버 및 내부 포토커플러 완전 안정을 위한 대기

def disable_motor():
    """모터 비활성화 (전류 차단, 전력 절약)"""
    time.sleep(0.02)  # 마지막 펄스 잔여 동작 완료 대기
    ena_output.on()   # TB6600은 HIGH일 때 Disable

def step_motor(steps, delay, direction):
    """
    순수 회전 동작만 수행하는 함수
    (ENA 제어는 외부에서 상위 관리하여 타이밍 충돌 방지)
    :param steps: 이동할 스텝 수
    :param delay: 스텝 간 딜레이 (초 단위)
    :param direction: True(정방향), False(역방향)
    """
    # 1. 방향 신호 확정 (DIR 신호 먼저 변경)
    if direction:
        dir_output.on()   # 정방향 (HIGH)
    else:
        dir_output.off()  # 역방향 (LOW)
    
    # DIR 신호가 포토커플러에 확실히 래치되도록 딜레이 확보
    time.sleep(0.03)

    # 2. 펄스(PUL) 공급
    for _ in range(steps):
        pul_output.on()
        time.sleep(delay)
        pul_output.off()
        time.sleep(delay)

def main():
    try:
        print("--- Nema 17 타이밍 완전 보완 테스트 시작 ---")
        
        # 시작 시 비활성화 상태 유지
        disable_motor()

        steps_per_rev = 200  # 1회전 기본 스텝
        microsteps = 4       # TB6600 DIP 스위치 설정값 (1/4 마이크로스텝)
        total_steps = steps_per_rev * microsteps  # 800스텝

        delay_speed = 0.0005  # 회전 속도

        # ==========================================
        # 1. 정방향 1회전
        # ==========================================
        print("1. 정방향(CW) 1회전...")
        enable_motor()  # 동작 시작 전 ENA 활성화
        step_motor(steps=total_steps, delay=delay_speed, direction=True)
        disable_motor() # 회전 끝난 후 ENA 비활성화 (전력 절약)
        
        time.sleep(1)   # 대기 중 전력 절약

        # ==========================================
        # 2. 역방향 1회전
        # ==========================================
        print("2. 역방향(CCW) 1회전...")
        enable_motor()  # 동작 시작 전 ENA 활성화
        step_motor(steps=total_steps, delay=delay_speed, direction=False)
        disable_motor() # 회전 끝난 후 ENA 비활성화
        
        time.sleep(1)

        # ==========================================
        # 3. 왕복 연속 동작 테스트 (3회)
        # ==========================================
        print("3. 왕복 연속 동작 테스트 (3회)...")
        # 연속 동작 중에는 ENA를 계속 켜둔 상태로 정/역방향을 전환하여 ENA-DIR 간 엇갈림 방지
        enable_motor()
        
        for i in range(3):
            print(f"   [{i+1}/3] 정방향")
            step_motor(steps=total_steps, delay=delay_speed, direction=True)
            time.sleep(0.2)  # 정/역 방향 전환 시 드라이버 충격 방지 대기

            print(f"   [{i+1}/3] 역방향")
            step_motor(steps=total_steps, delay=delay_speed, direction=False)
            time.sleep(0.2)

        # 모든 연속 동작 완료 후 ENA 차단
        disable_motor()

        print("--- 테스트 완료 ---")

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    finally:
        # 종료 시 안전하게 핀 상태 정리
        disable_motor()
        dir_output.off()
        pul_output.off()

if __name__ == "__main__":
    main()
