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
    time.sleep(0.01)  # 드라이버 대기 시간

def disable_motor():
    """모터 비활성화 (전류 차단, 전력 절약, 모터 헐거워짐)"""
    ena_output.on()   # TB6600은 HIGH일 때 Disable
    time.sleep(0.01)

def step_motor(steps, delay, direction):
    """
    모터 스텝 제어 함수
    :param steps: 이동할 스텝 수
    :param delay: 스텝 간 딜레이 (초 단위)
    :param direction: True(정방향), False(역방향)
    """
    # 1. 모터 전원 공급 (Enable)
    enable_motor()

    # 2. 방향 설정
    if direction:
        dir_output.on()   # 정방향 (HIGH)
    else:
        dir_output.off()  # 역방향 (LOW)
    
    time.sleep(0.005)  # 방향 신호 안정화

    # 3. 펄스(Step) 신호 발생
    for _ in range(steps):
        pul_output.on()
        time.sleep(delay)
        pul_output.off()
        time.sleep(delay)

    # 4. 회전 완료 후 즉시 전원 차단 (전력 절약)
    disable_motor()

def main():
    try:
        print("--- Nema 17 ENA 제어 모드 테스트 시작 ---")
        
        # 시작 시 모터 전원 차단 상태 유지
        disable_motor()

        steps_per_rev = 200  # 1회전 기본 스텝
        microsteps = 4       # TB6600 DIP 스위치 설정값 (1/4 마이크로스텝)
        total_steps = steps_per_rev * microsteps  # 800스텝

        delay_speed = 0.0005  # 회전 속도

        # 1. 정방향 1회전 (회전 후 전원 차단됨)
        print("1. 정방향(CW) 1회전 (회전 후 전력 차단)...")
        step_motor(steps=total_steps, delay=delay_speed, direction=True)
        print("   -> 대기 중: ENA 차단됨 (전력 0, 손으로 모터 축 회전 가능)")
        time.sleep(2)

        # 2. 역방향 1회전 (회전 후 전원 차단됨)
        print("2. 역방향(CCW) 1회전 (회전 후 전력 차단)...")
        step_motor(steps=total_steps, delay=delay_speed, direction=False)
        print("   -> 대기 중: ENA 차단됨")
        time.sleep(2)

        # 3. 연속 왕복 동작 테스트
        print("3. 왕복 연속 동작 테스트 (3회)...")
        for i in range(3):
            print(f"   [{i+1}/3] 정방향")
            step_motor(steps=total_steps, delay=delay_speed, direction=True)
            time.sleep(1)  # 대기 시간 동안 전력 절약 상태 유지

            print(f"   [{i+1}/3] 역방향")
            step_motor(steps=total_steps, delay=delay_speed, direction=False)
            time.sleep(1)

        print("--- 테스트 완료 ---")

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    finally:
        # 종료 시 모터 전원 차단 및 핀 정리
        disable_motor()
        dir_output.off()
        pul_output.off()

if __name__ == "__main__":
    main()
