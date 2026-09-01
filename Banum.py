from picamera2 import Picamera2
import cv2
import numpy as np
import time


# ==========================================
# 설정값
# ==========================================

REAL_WIDTH = 3.5
REAL_HEIGHT = 3.5

REFERENCE_DISTANCE = 15.5

MIN_AREA = 300


# ==========================================
# 카메라 생성
# ==========================================

cam0 = Picamera2(0)
cam1 = Picamera2(1)


config0 = cam0.create_preview_configuration(
    main={
        "size": (640, 480),
        "format": "RGB888"
    }
)

config1 = cam1.create_preview_configuration(
    main={
        "size": (640, 480),
        "format": "RGB888"
    }
)

cam0.configure(config0)
cam1.configure(config1)

cam0.start()
cam1.start()

time.sleep(2)


# ==========================================
# 기준 물체 색상 등록
# Camera 0에서 노란색 내부 선택
# ==========================================

frame0 = cam0.capture_array()

frame0 = cv2.cvtColor(
    frame0,
    cv2.COLOR_RGB2BGR
)

print()
print("======================================")
print("기준 물체 색상 등록")
print("======================================")
print(f"물체 크기 : {REAL_WIDTH} x {REAL_HEIGHT} cm")
print(f"기준 거리 : {REFERENCE_DISTANCE} cm")
print()
print("물체를 정확히 15.5 cm에 놓으세요.")
print("노란색 내부 영역만 마우스로 선택하세요.")
print("검은색 테두리는 제외하는 것이 좋습니다.")
print("선택 후 ENTER 또는 SPACE")
print()


roi = cv2.selectROI(
    "Select Yellow Area",
    frame0,
    fromCenter=False,
    showCrosshair=True
)

cv2.destroyWindow("Select Yellow Area")


x, y, w, h = [int(v) for v in roi]


if w == 0 or h == 0:

    print("영역 선택 실패")

    cam0.stop()
    cam1.stop()

    exit()


# ==========================================
# 선택 영역 HSV 분석
# ==========================================

selected = frame0[
    y:y+h,
    x:x+w
]

hsv_selected = cv2.cvtColor(
    selected,
    cv2.COLOR_BGR2HSV
)


h_mean = int(
    np.median(hsv_selected[:, :, 0])
)

s_mean = int(
    np.median(hsv_selected[:, :, 1])
)

v_mean = int(
    np.median(hsv_selected[:, :, 2])
)


print()
print("선택 색상 HSV")
print("H =", h_mean)
print("S =", s_mean)
print("V =", v_mean)


# ==========================================
# HSV 허용 범위
# ==========================================

H_MARGIN = 15
S_MARGIN = 90
V_MARGIN = 90


lower = np.array([
    max(0, h_mean - H_MARGIN),
    max(30, s_mean - S_MARGIN),
    max(30, v_mean - V_MARGIN)
])


upper = np.array([
    min(179, h_mean + H_MARGIN),
    min(255, s_mean + S_MARGIN),
    min(255, v_mean + V_MARGIN)
])


kernel = np.ones(
    (3, 3),
    np.uint8
)


# ==========================================
# 타겟 검출 함수
# ==========================================

def detect_target(frame):

    hsv = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2HSV
    )

    mask = cv2.inRange(
        hsv,
        lower,
        upper
    )


    # 작은 잡음 제거
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )

    # 영역 내부 작은 구멍 연결
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


    if not valid:
        return None, mask


    target = max(
        valid,
        key=cv2.contourArea
    )


    x, y, w, h = cv2.boundingRect(target)


    cx = x + w / 2.0
    cy = y + h / 2.0


    return (
        x,
        y,
        w,
        h,
        cx,
        cy
    ), mask


# ==========================================
# 15.5 cm 기준 disparity 측정
# ==========================================

print()
print("======================================")
print("15.5 cm 기준값 측정")
print("======================================")
print("물체를 움직이지 마세요.")


reference_disparities = []


for _ in range(30):

    frame0 = cam0.capture_array()
    frame1 = cam1.capture_array()


    frame0 = cv2.cvtColor(
        frame0,
        cv2.COLOR_RGB2BGR
    )

    frame1 = cv2.cvtColor(
        frame1,
        cv2.COLOR_RGB2BGR
    )


    result0, _ = detect_target(frame0)
    result1, _ = detect_target(frame1)


    if result0 is not None and result1 is not None:

        cx0 = result0[4]
        cx1 = result1[4]

        disparity = abs(
            cx0 - cx1
        )

        reference_disparities.append(
            disparity
        )


if len(reference_disparities) == 0:

    print("두 카메라에서 물체를 동시에 찾지 못했습니다.")

    cam0.stop()
    cam1.stop()

    exit()


REFERENCE_DISPARITY = float(
    np.median(reference_disparities)
)


print()
print("기준 거리 :", REFERENCE_DISTANCE, "cm")
print(
    "기준 disparity :",
    round(REFERENCE_DISPARITY, 2),
    "px"
)
print()
print("이제 물체를 앞뒤로 움직여보세요.")
print("종료 : q")
print()


# ==========================================
# 실시간 처리
# ==========================================

while True:

    frame0 = cam0.capture_array()
    frame1 = cam1.capture_array()


    frame0 = cv2.cvtColor(
        frame0,
        cv2.COLOR_RGB2BGR
    )

    frame1 = cv2.cvtColor(
        frame1,
        cv2.COLOR_RGB2BGR
    )


    result0, mask0 = detect_target(frame0)
    result1, mask1 = detect_target(frame1)


    if result0 is not None:

        x0, y0, w0, h0, cx0, cy0 = result0


        cv2.rectangle(
            frame0,
            (x0, y0),
            (x0 + w0, y0 + h0),
            (0, 255, 0),
            2
        )


        cv2.circle(
            frame0,
            (int(cx0), int(cy0)),
            5,
            (0, 0, 255),
            -1
        )


    if result1 is not None:

        x1, y1, w1, h1, cx1, cy1 = result1


        cv2.rectangle(
            frame1,
            (x1, y1),
            (x1 + w1, y1 + h1),
            (0, 255, 0),
            2
        )


        cv2.circle(
            frame1,
            (int(cx1), int(cy1)),
            5,
            (0, 0, 255),
            -1
        )


    # 두 카메라 모두 검출 성공
    if (
        result0 is not None
        and
        result1 is not None
    ):

        disparity = abs(
            cx0 - cx1
        )


        cv2.putText(
            frame0,
            f"X0: {cx0:.1f}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )


        cv2.putText(
            frame1,
            f"X1: {cx1:.1f}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )


        cv2.putText(
            frame0,
            f"Disparity: {disparity:.1f}px",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )


        cv2.putText(
            frame1,
            f"Disparity: {disparity:.1f}px",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )


        cv2.putText(
            frame0,
            f"Ref 15.5cm: {REFERENCE_DISPARITY:.1f}px",
            (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )


    else:

        cv2.putText(
            frame0,
            "Target Not Found",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )


    # 두 화면 합치기
    stereo_view = cv2.hconcat([
        frame0,
        frame1
    ])


    cv2.imshow(
        "Stereo Measurement",
        stereo_view
    )


    cv2.imshow(
        "Mask Camera 0",
        mask0
    )


    cv2.imshow(
        "Mask Camera 1",
        mask1
    )


    key = cv2.waitKey(1) & 0xFF


    if key == ord("q"):
        break


cv2.destroyAllWindows()

cam0.stop()
cam1.stop()
