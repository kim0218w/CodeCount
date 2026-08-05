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
    """모터 활성화 (전류 공급)"""
    ena_output.off()  # TB6600 LOW = Enable
    time.sleep(0.05)  # 드라이버 회로 및 포토커플러 완전 충전 대기

def disable_motor():
    """모터 비활성화 (전력 절약)"""
    time.sleep(0.05)  # 잔여 펄스 완전 소진 대기
    ena_output.on()   # TB6600 HIGH = Disable

def clear_buffer():
    """버퍼 및 잔여 신호 강제 비우기 (Flush)"""
    pul_output.off()
    time.sleep(0.05)  # 잔여 신호 강제 드롭 및 대기

def step_motor_precise(steps, step_delay, direction):
    """
    큐/버퍼 쌓임 방지형 모터 제어 함수
    :param steps: 이동할 스텝 수
    :param step_delay: 스텝 간격 (초 단위)
    :param direction: True(정방향), False(역방향)
    """
    # 1. 방향 설정 (PUL 신호가 0인 상태에서 확실하게 인가)
    pul_output.off()
    
    if direction:
        dir_output.on()   # 정방향 (HIGH)
    else:
        dir_output.off()  # 역방향 (LOW)
    
    # DIR 방향 신호가 내부 포토커플러에 완전 고정(Latch)될 때까지 대기
    time.sleep(0.05) 

    # 2. 정확한 동기식 펄스 생성 (버퍼링 방지)
    # perf_counter를 사용하여 시스템 버퍼 지연에 의한 펄스 뭉침 현상 방지
    for _ in range(steps):
        pul_output.on()
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < step_delay:
            pass  # 정밀 미세 대기
        
        pul_output.off()
        t1 = time.perf_counter()
        while time.perf_counter() - t1 < step_delay:
            pass

    # 3. 동작 완료 후 잔여 신호 정리
    clear_buffer()

def main():
    try:
        print("--- Nema 17 버퍼 쌓임 방지 테스트 시작 ---")
        
        # 시작 전 초기화
        pul_output.off()
        dir_output.off()
        disable_motor()

        steps_per_rev = 200  # 1회전 기본 스텝
        microsteps = 4       # TB6600 DIP 스위치 설정 (1/4 마이크로스텝)
        total_steps = steps_per_rev * microsteps  # 800스텝

        # 펄스 속도 (너무 빠르면 CPU 점유율이 올라가므로 0.0008~0.001 권장)
        pulse_delay = 0.0008 

        # ==========================================
        # 1. 정방향 / 역방향 단발 테스트
        # ==========================================
        print("1. 정방향(CW) 회전...")
        enable_motor()
        step_motor_precise(total_steps, pulse_delay, True)
        disable_motor()
        time.sleep(1)

        print("2. 역방향(CCW) 회전...")
        enable_motor()
        step_motor_precise(total_steps, pulse_delay, False)
        disable_motor()
        time.sleep(1)

        # ==========================================
        # 2. 왕복 연속 동작 (쌓임 방지 검증)
        # ==========================================
        print("3. 왕복 연속 테스트 (3회)...")
        enable_motor()

        for i in range(3):
            print(f"   [{i+1}/3] 정방향")
            step_motor_precise(total_steps, pulse_delay, True)
            time.sleep(0.3)  # 모터 관성 및 신호 버퍼 정리를 위한 대기

            print(f"   [{i+1}/3] 역방향")
            step_motor_precise(total_steps, pulse_delay, False)
            time.sleep(0.3)

        disable_motor()
        print("--- 테스트 완료 ---")

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    finally:
        disable_motor()
        clear_buffer()

if __name__ == "__main__":
    main()
