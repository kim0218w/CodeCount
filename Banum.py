from picamera2 import Picamera2
import cv2
import numpy as np
import time


# =========================
# 설정
# =========================

REAL_WIDTH = 1.0            # 정사각형 실제 폭(cm)
REFERENCE_DISTANCE = 5.0    # 보정할 기준 거리(cm)

MIN_AREA = 100              # 너무 작은 잡음 제거용


# =========================
# 카메라 시작
# =========================

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={
        "size": (640, 480),
        "format": "RGB888"
    }
)

picam2.configure(config)
picam2.start()

time.sleep(2)


# =========================
# 기준 물체 색상 선택
# =========================

frame = picam2.capture_array()
frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

print()
print("======================================")
print("분홍색 정사각형 색상 등록")
print("======================================")
print(f"정사각형을 카메라에서 {REFERENCE_DISTANCE} cm 거리에 놓으세요.")
print("분홍색 내부 부분만 마우스로 선택하세요.")
print("검은 테두리는 가능하면 제외하세요.")
print("선택 후 ENTER 또는 SPACE")
print()

roi = cv2.selectROI(
    "Select PINK Area",
    frame,
    fromCenter=False,
    showCrosshair=True
)

cv2.destroyWindow("Select PINK Area")

x, y, w, h = [int(v) for v in roi]

if w == 0 or h == 0:
    print("영역이 선택되지 않았습니다.")
    picam2.stop()
    exit()


# =========================
# 선택 영역에서 HSV 색상 추출
# =========================

selected = frame[y:y+h, x:x+w]

hsv_selected = cv2.cvtColor(
    selected,
    cv2.COLOR_BGR2HSV
)

# 중앙값 사용
h_mean = int(np.median(hsv_selected[:, :, 0]))
s_mean = int(np.median(hsv_selected[:, :, 1]))
v_mean = int(np.median(hsv_selected[:, :, 2]))

print()
print("선택한 색상 HSV")
print("H:", h_mean)
print("S:", s_mean)
print("V:", v_mean)


# 색 허용 범위
H_MARGIN = 15
S_MARGIN = 80
V_MARGIN = 80

lower = np.array([
    max(0, h_mean - H_MARGIN),
    max(40, s_mean - S_MARGIN),
    max(40, v_mean - V_MARGIN)
])

upper = np.array([
    min(179, h_mean + H_MARGIN),
    min(255, s_mean + S_MARGIN),
    min(255, v_mean + V_MARGIN)
])


# =========================
# 기준거리에서 자동 검출
# =========================

print()
print("기준거리 Calibration 중...")
print("정사각형을 움직이지 마세요.")

time.sleep(1)

reference_width = None


for _ in range(20):

    frame = picam2.capture_array()
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    mask = cv2.inRange(
        hsv,
        lower,
        upper
    )

    # 잡음 제거
    kernel = np.ones((3, 3), np.uint8)

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    valid = [
        c for c in contours
        if cv2.contourArea(c) > MIN_AREA
    ]

    if valid:

        largest = max(
            valid,
            key=cv2.contourArea
        )

        rx, ry, rw, rh = cv2.boundingRect(largest)

        reference_width = rw


if reference_width is None:
    print("기준 물체를 찾지 못했습니다.")
    picam2.stop()
    exit()


# 초점거리 계산
focal_length = (
    reference_width
    * REFERENCE_DISTANCE
    / REAL_WIDTH
)

print()
print("======================================")
print("Calibration 완료")
print("======================================")
print(f"실제 폭       : {REAL_WIDTH:.2f} cm")
print(f"기준 거리     : {REFERENCE_DISTANCE:.2f} cm")
print(f"기준 픽셀 폭  : {reference_width} px")
print(f"초점거리      : {focal_length:.2f} px")
print()
print("이제 물체를 움직여보세요.")
print("종료: q")
print()


# =========================
# 실시간 자동 거리 측정
# =========================

while True:

    frame = picam2.capture_array()
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    hsv = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2HSV
    )

    mask = cv2.inRange(
        hsv,
        lower,
        upper
    )

    kernel = np.ones((3, 3), np.uint8)

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    valid = [
        c for c in contours
        if cv2.contourArea(c) > MIN_AREA
    ]


    if valid:

        # 가장 큰 분홍색 영역
        largest = max(
            valid,
            key=cv2.contourArea
        )

        x, y, w, h = cv2.boundingRect(largest)

        if w > 0:

            distance = (
                REAL_WIDTH
                * focal_length
                / w
            )

            center_x = x + w // 2
            center_y = y + h // 2

            # 자동 검출 Bounding Box
            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

            # 중심
            cv2.circle(
                frame,
                (center_x, center_y),
                5,
                (0, 0, 255),
                -1
            )

            # 거리
            cv2.putText(
                frame,
                f"Distance: {distance:.2f} cm",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            # 현재 폭
            cv2.putText(
                frame,
                f"Width: {w} px",
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

    else:

        cv2.putText(
            frame,
            "Target Not Found",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )


    cv2.imshow(
        "Automatic Distance Measurement",
        frame
    )

    cv2.imshow(
        "Mask",
        mask
    )


    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break


cv2.destroyAllWindows()
picam2.stop()
