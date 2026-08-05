import time
from gpiozero import OutputDevice

# ==========================================
# 핀 설정
# ==========================================
ENA_PIN = 26  # Enable 핀
DIR_PIN = 20  # Direction 핀
STEP_PIN = 21  # Step 핀

# GPIO 출력 개체 생성
ena_pin = OutputDevice(ENA_PIN)
dir_pin = OutputDevice(DIR_PIN)
step_pin = OutputDevice(STEP_PIN)


def set_driver_enable(enable=True):
    """드라이버 활성화/비활성화 함수"""
    if enable:
        ena_pin.off()  # LOW -> Active
    else:
        ena_pin.on()  # HIGH -> Disable


def rotate_stepper(steps, delay, is_clockwise=True):
    """스텝 수 기반 회전 제어 함수"""
    set_driver_enable(True)
    time.sleep(0.01)

    if is_clockwise:
        dir_pin.on()
    else:
        dir_pin.off()

    time.sleep(0.01)

    for _ in range(steps):
        step_pin.on()
        time.sleep(delay)
        step_pin.off()
        time.sleep(delay)

    set_driver_enable(False)


def rotate_by_angle(angle, delay=0.002, is_clockwise=True, steps_per_rev=400):
    """각도 기반 회전 제어 함수

    :param steps_per_rev: TB6600 1/2 마이크로스텝(SW1=OFF, SW2/3=ON) 기준 400
    """
    # int() 대신 round()를 사용하여 반올림 처리 (부동소수점 오차 방지)
    steps = round((angle / 360.0) * steps_per_rev)

    if steps < 1:
        print("경고: 입력한 각도가 너무 작아 1스텝 미만입니다.")
        return

    rotate_stepper(steps=steps, delay=delay, is_clockwise=is_clockwise)

if __name__ == "__main__":
    try:
        print("=== 스텝 모터 3.6도 제어 테스트 시작 ===")

        # 1. 정방향 3.6도 회전
        print("1. 정방향 3.6도 회전")
        rotate_by_angle(angle=3.6, delay=0.002, is_clockwise=True)
        time.sleep(1)

        # 2. 역방향 3.6도 회전
        print("2. 역방향 3.6도 회전")
        rotate_by_angle(angle=3.6, delay=0.002, is_clockwise=False)
        time.sleep(1)

        print("테스트 정상 완료!")

    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")

    finally:
        set_driver_enable(False)
        ena_pin.close()
        dir_pin.close()
        step_pin.close()
