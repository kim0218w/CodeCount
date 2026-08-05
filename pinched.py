import time
from gpiozero import OutputDevice

# GPIO 핀 설정 (BCM 번호)
DIR_PIN = 20
PUL_PIN = 21

# gpiozero OutputDevice 객체 생성
dir_output = OutputDevice(DIR_PIN)
pul_output = OutputDevice(PUL_PIN)

def step_motor(steps, delay, direction):
    """
    모터 스텝 제어 함수
    :param steps: 이동할 스텝 수
    :param delay: 스텝 간 딜레이 (초 단위, 속도 조절)
    :param direction: True(정방향), False(역방향)
    """
    # 1. 방향 설정
    if direction:
        dir_output.on()   # 정방향 (HIGH)
    else:
        dir_output.off()  # 역방향 (LOW)
    
    time.sleep(0.005)  # 방향 신호가 안정화되도록 딜레이

    # 2. 펄스(Step) 신호 발생
    for _ in range(steps):
        pul_output.on()
        time.sleep(delay)
        pul_output.off()
        time.sleep(delay)

def main():
    try:
        print("--- Nema 17 모터 gpiozero 테스트 시작 ---")

        steps_per_rev = 200  # 1회전 기본 200스텝 (1.8도 기준)
        microsteps = 4       # TB6600 DIP 스위치 설정값 (예: 1/4 마이크로스텝)
        total_steps = steps_per_rev * microsteps  # 1회전당 필요 펄스 수 (800스텝)

        delay_speed = 0.0005  # 속도 조절 (작을수록 빠름, 추천 range: 0.0002 ~ 0.002)

        # 1. 정방향 테스트
        print("1. 정방향(CW) 1회전...")
        step_motor(steps=total_steps, delay=delay_speed, direction=True)
        time.sleep(1)

        # 2. 역방향 테스트
        print("2. 역방향(CCW) 1회전...")
        step_motor(steps=total_steps, delay=delay_speed, direction=False)
        time.sleep(1)

        # 3. 왕복 테스트 (3회)
        print("3. 왕복 테스트 (3회)...")
        for i in range(3):
            print(f"   [{i+1}/3] 정방향")
            step_motor(steps=total_steps, delay=delay_speed, direction=True)
            time.sleep(0.5)

            print(f"   [{i+1}/3] 역방향")
            step_motor(steps=total_steps, delay=delay_speed, direction=False)
            time.sleep(0.5)

        print("--- 테스트 완료 ---")

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    finally:
        # 종료 시 핀 상태 초기화
        dir_output.off()
        pul_output.off()

if __name__ == "__main__":
    main()
