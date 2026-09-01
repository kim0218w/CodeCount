from picamera2 import Picamera2
import cv2
import time

# ==========================================
# 실험 설정
# ==========================================

REAL_WIDTH = 1.0           # 정사각형 실제 폭 (cm)
REFERENCE_DISTANCE = 5.0   # 기준 거리 (cm)

# ==========================================
# 카메라 시작
# ==========================================

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={
        "size": (640, 480),
        "format": "RGB888"
    }
)

picam2.configure(config)
picam2.start()

# 카메라가 안정될 때까지 잠시 대기
time.sleep(2)

# ==========================================
# 기준 거리에서 물체 선택
# ==========================================

frame = picam2.capture_array()

# OpenCV용 BGR 변환
frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

print()
print("===================================")
print("거리 측정 Calibration")
print("===================================")
print(f"1cm x 1cm 정사각형을 카메라에서 {REFERENCE_DISTANCE}cm 떨어진 곳에 놓으세요.")
print("영상에서 정사각형의 바깥 테두리를 마우스로 선택하세요.")
print("선택 후 ENTER 또는 SPACE를 누르세요.")
print()

bbox = cv2.selectROI(
    "Calibration - Select 1cm Square",
    frame,
    fromCenter=False,
    showCrosshair=True
)

cv2.destroyWindow("Calibration - Select 1cm Square")

x, y, w, h = bbox

if w == 0 or h == 0:
    print("물체가 선택되지 않았습니다.")
    picam2.stop()
    exit()

# ==========================================
# 초점거리 계산
# ==========================================

reference_pixel_width = float(w)

focal_length = (
    reference_pixel_width
    * REFERENCE_DISTANCE
    / REAL_WIDTH
)

print()
print("Calibration 완료")
print("-----------------------------------")
print(f"실제 물체 폭      : {REAL_WIDTH:.2f} cm")
print(f"기준 거리         : {REFERENCE_DISTANCE:.2f} cm")
print(f"영상에서 물체 폭  : {reference_pixel_width:.1f} px")
print(f"계산된 초점거리   : {focal_length:.1f} px")
print("-----------------------------------")
print("이제 물체를 앞뒤로 움직여보세요.")
print("종료하려면 q를 누르세요.")
print()

# ==========================================
# Tracker 생성
# ==========================================

try:
    tracker = cv2.legacy.TrackerCSRT_create()
except AttributeError:
    tracker = cv2.TrackerCSRT_create()

tracker.init(frame, bbox)

# ==========================================
# 실시간 거리 측정
# ==========================================

while True:

    frame = picam2.capture_array()

    frame = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2BGR
    )

    success, bbox = tracker.update(frame)

    if success:

        x, y, w, h = [int(v) for v in bbox]

        # 0으로 나누는 것 방지
        if w > 0:

            # 거리 계산
            distance = (
                REAL_WIDTH
                * focal_length
                / w
            )

            # Bounding Box
            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

            # 중심점
            center_x = x + w // 2
            center_y = y + h // 2

            cv2.circle(
                frame,
                (center_x, center_y),
                4,
                (0, 0, 255),
                -1
            )

            # 거리 표시
            cv2.putText(
                frame,
                f"Distance: {distance:.2f} cm",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            # 픽셀 폭 표시
            cv2.putText(
                frame,
                f"Width: {w} px",
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            # 10cm 이내인지 표시
            if distance <= 10.0:

                cv2.putText(
                    frame,
                    "Measurement Range: OK",
                    (20, 110),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            else:

                cv2.putText(
                    frame,
                    "Over 10 cm",
                    (20, 110),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2
                )

    else:

        cv2.putText(
            frame,
            "Tracking Lost",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

    cv2.imshow(
        "Real-time Distance Measurement",
        frame
    )

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break


# ==========================================
# 종료
# ==========================================

cv2.destroyAllWindows()
picam2.stop()
