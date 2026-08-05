import time
from gpiozero import OutputDevice

# ==========================================
# 핀 설정 (본인의 실제 GPIO 핀 번호로 변경)
# ==========================================
ENA_PIN = 26  # Enable 핀 (활성화/비활성화)
DIR_PIN = 20  # Direction 핀 (방향 제어)
STEP_PIN = 21  # Step 핀 (펄스 출력)

# GPIO 출력 개체 생성
ena_pin = OutputDevice(ENA_PIN)
dir_pin = OutputDevice(DIR_PIN)
step_pin = OutputDevice(STEP_PIN)


def set_driver_enable(enable=True):
    """드라이버 활성화/비활성화 함수

    대부분의 스텝 모터 드라이버(A4988, DRV8825, TB6600 등):
    - LOW (off)  = 드라이버 활성화 (전류 공급, 모터 잠김)
    - HIGH (on)  = 드라이버 비활성화 (전류 차단, 모터 풀림)
    """
    if enable:
        ena_pin.off()  # LOW -> Active
    else:
        ena_pin.on()  # HIGH -> Disable


def rotate_stepper(steps, delay, is_clockwise=True):
    """스텝 모터 회전 제어 함수

    :param steps: 회전할 스텝 수 (200스텝 = 1회전)
    :param delay: 스텝 간격 (초 단위, 속도)
    :param is_clockwise: True=정방향, False=역방향
    """
    # 1. 드라이버 활성화
    set_driver_enable(True)
    time.sleep(0.01)  # 활성화 안정화 대기

    # 2. 회전 방향 설정
    if is_clockwise:
        dir_pin.on()  # DIR = HIGH (정방향)
    else:
        dir_pin.off()  # DIR = LOW (역방향)

    time.sleep(0.01)  # DIR 신호 전압 안정을 위한 딜레이

    # 3. STEP 펄스 생성
    for _ in range(steps):
        step_pin.on()
        time.sleep(delay)
        step_pin.off()
        time.sleep(delay)

    # 4. 동작 완료 후 드라이버 비활성화 (선택 사항: 발열 방지)
    # 계속 토크(유지력)를 유지해야 하는 시스템이라면 아래 줄을 주석 처리하세요.
    set_driver_enable(False)


if __name__ == "__main__":
    try:
        print("=== NEMA 17 방향 제어 및 ENA 테스트 시작 ===")

        # 1. 정방향 1회전 (CW)
        print("1. 정방향(CW) 회전 시작")
        rotate_stepper(steps=200, delay=0.002, is_clockwise=True)
        time.sleep(1)

        # 2. 역방향 1회전 (CCW)
        print("2. 역방향(CCW) 회전 시작")
        rotate_stepper(steps=200, delay=0.002, is_clockwise=False)
        time.sleep(1)

        print("테스트 정상 완료!")

    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")

    finally:
        # 종료 시 드라이버 차단 및 GPIO 핀 해제 (1회만 수행)
        set_driver_enable(False)
        ena_pin.close()
        dir_pin.close()
        step_pin.close()
