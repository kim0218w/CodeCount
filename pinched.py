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

    # DIR 핀 제어
    if is_clockwise:
        dir_pin.on()
    else:
        dir_pin.off()

    # DIR 신호가 드라이버 내부 포토커플러에 확실히 전달되도록 대기 시간 증가
    time.sleep(0.02)

    for _ in range(steps):
        step_pin.on()
        time.sleep(delay)
        step_pin.off()
        time.sleep(delay)

    set_driver_enable(False)


def rotate_by_angle_step_by_step(
    angle, delay=0.002, is_clockwise=True, steps_per_rev=400
):
    """1스텝씩 반복하여 원하는 각도까지 회전시키는 함수"""
    total_steps = round((angle / 360.0) * steps_per_rev)

    if total_steps < 1:
        print("경고: 입력한 각도가 너무 작습니다.")
        return

    print(f"-> 총 {total_steps}스텝을 1스텝씩 나누어 인가합니다.")

    # 1스텝(1.8도 또는 마이크로스텝 단위)씩 total_steps 번 반복 실행
    for i in range(total_steps):
        rotate_stepper(steps=1, delay=delay, is_clockwise=is_clockwise)
        time.sleep(0.001)  # 스텝 간 미세 간격


if __name__ == "__main__":
    try:
        print("=== 스텝 모터 3.6도 (1스텝 반복) 제어 테스트 시작 ===")

        # 1. 정방향 3.6도 회전 (400스텝/회전 기준 4스텝)
        print("\n1. 정방향(CW) 3.6도 회전")
        rotate_by_angle_step_by_step(
            angle=3.6, delay=0.002, is_clockwise=True, steps_per_rev=400
        )
        time.sleep(1)

        # 2. 역방향 3.6도 회전
        print("\n2. 역방향(CCW) 3.6도 회전")
        rotate_by_angle_step_by_step(
            angle=3.6, delay=0.002, is_clockwise=False, steps_per_rev=400
        )
        time.sleep(1)

        print("\n테스트 정상 완료!")

    except KeyboardInterrupt:
        print("\n사용자에 의해 중단됨")

    finally:
        set_driver_enable(False)
        ena_pin.close()
        dir_pin.close()
        step_pin.close()
