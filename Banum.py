from picamera2 import Picamera2
import cv2
import numpy as np
import time


# ==================================================
# 설정
# ==================================================

MIN_AREA = 300

# 실험으로 얻은 보정식
# Distance = A * disparity + B
A = 0.08537908
B = 15.13501923

# 현재 신뢰할 수 있는 측정 범위
MIN_DISTANCE = 5.5
MAX_DISTANCE = 13.5


# ==================================================
# 카메라 설정
# ==================================================

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


# ==================================================
# 1단계
# 두 카메라 실시간 영상 확인
# ==================================================

print()
print("==========================================")
print("Stereo Camera Preview")
print("==========================================")
print()
print("물체를 두 카메라에 보이도록 위치시키세요.")
print()
print("r : 현재 화면에서 색상 영역 선택")
print("q : 종료")
print()


roi_frame = None


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

    # 안내 문구
    cv2.putText(
        frame0,
        "Camera 0",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame1,
        "Camera 1",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame0,
        "Press R to select target",
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame1,
        "Press R to select target",
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )

    # 두 화면을 옆으로 합침
    preview = cv2.hconcat([
        frame0,
        frame1
    ])

    cv2.imshow(
        "Stereo Camera Preview",
        preview
    )

    key = cv2.waitKey(1) & 0xFF

    # --------------------------------------------------
    # R 키 → 현재 Camera 0 화면 저장 후 ROI 선택 단계
    # --------------------------------------------------

    if key == ord("r"):

        roi_frame = frame0.copy()
        break

    # --------------------------------------------------
    # Q 키 → 종료
    # --------------------------------------------------

    if key == ord("q"):

        cv2.destroyAllWindows()

        cam0.stop()
        cam1.stop()

        exit()


cv2.destroyWindow(
    "Stereo Camera Preview"
)


# ==================================================
# 2단계
# Camera 0 정지화면에서 노란 영역 선택
# ==================================================

print()
print("화면이 정지되었습니다.")
print("Camera 0 화면에서 노란색 부분만 선택하세요.")
print("검은 테두리는 가능하면 제외하세요.")
print("선택 후 ENTER 또는 SPACE")
print()


roi = cv2.selectROI(
    "Select Yellow Area",
    roi_frame,
    fromCenter=False,
    showCrosshair=True
)

cv2.destroyWindow(
    "Select Yellow Area"
)


x, y, w, h = [
    int(v)
    for v in roi
]


if w == 0 or h == 0:

    print("영역 선택 실패")

    cam0.stop()
    cam1.stop()

    exit()


# ==================================================
# 선택한 영역에서 HSV 계산
# ==================================================

selected = roi_frame[
    y:y+h,
    x:x+w
]


hsv_selected = cv2.cvtColor(
    selected,
    cv2.COLOR_BGR2HSV
)


h_mean = int(
    np.median(
        hsv_selected[:, :, 0]
    )
)

s_mean = int(
    np.median(
        hsv_selected[:, :, 1]
    )
)

v_mean = int(
    np.median(
        hsv_selected[:, :, 2]
    )
)


print()
print("==========================================")
print("선택한 색상 HSV")
print("==========================================")
print("H:", h_mean)
print("S:", s_mean)
print("V:", v_mean)


# ==================================================
# HSV 허용 범위
# ==================================================

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


# ==================================================
# 물체 검출 함수
# ==================================================

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

    # 끊어진 영역 연결
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
        return None

    target = max(
        valid,
        key=cv2.contourArea
    )

    x, y, w, h = cv2.boundingRect(
        target
    )

    cx = x + w / 2.0
    cy = y + h / 2.0

    return x, y, w, h, cx, cy


# ==================================================
# 거리값 안정화
# ==================================================

distance_history = []

HISTORY_SIZE = 10


print()
print()
print("==========================================")
print("실시간 Stereo 측정 시작")
print("==========================================")
print()
print("사용 권장 범위: 5.5 ~ 13.5 cm")
print("종료: q")
print()


# ==================================================
# 3단계
# 실시간 Stereo 처리
# ==================================================

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

    result0 = detect_target(frame0)
    result1 = detect_target(frame1)

    cx0 = None
    cx1 = None
    disparity = None


    # ==================================================
    # Camera 0
    # ==================================================

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


    # ==================================================
    # Camera 1
    # ==================================================

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


    # ==================================================
    # 두 카메라 모두 검출 성공
    # ==================================================

    if cx0 is not None and cx1 is not None:

        # Signed disparity
        disparity = cx0 - cx1


        # --------------------------------------------------
        # 기존 보정식
        # --------------------------------------------------

        raw_distance = (
            A * disparity
            + B
        )


        # --------------------------------------------------
        # 최근 10프레임 중앙값
        # --------------------------------------------------

        distance_history.append(
            raw_distance
        )

        if len(distance_history) > HISTORY_SIZE:
            distance_history.pop(0)


        distance = float(
            np.median(
                distance_history
            )
        )


        # --------------------------------------------------
        # Camera 0 정보
        # --------------------------------------------------

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
            frame0,
            f"Disparity: {disparity:.1f}px",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )


        # --------------------------------------------------
        # Camera 1 정보
        # --------------------------------------------------

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
            frame1,
            f"Disparity: {disparity:.1f}px",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )


        # --------------------------------------------------
        # 거리 표시
        # --------------------------------------------------

        if MIN_DISTANCE <= distance <= MAX_DISTANCE:

            text = (
                f"Distance: "
                f"{distance:.2f} cm"
            )

            text_color = (
                0,
                255,
                0
            )

        else:

            text = (
                f"Out of Range: "
                f"{distance:.2f} cm"
            )

            text_color = (
                0,
                0,
                255
            )


        cv2.putText(
            frame0,
            text,
            (20, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            text_color,
            2
        )

        cv2.putText(
            frame1,
            text,
            (20, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            text_color,
            2
        )


    else:

        # 한쪽이라도 검출 실패하면 이전 기록 제거
        distance_history.clear()

        cv2.putText(
            frame0,
            "Target Not Found",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

        cv2.putText(
            frame1,
            "Target Not Found",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )


    # ==================================================
    # 두 영상 합치기
    # ==================================================

    stereo_view = cv2.hconcat([
        frame0,
        frame1
    ])


    cv2.imshow(
        "Stereo Distance Measurement",
        stereo_view
    )


    key = cv2.waitKey(1) & 0xFF


    if key == ord("q"):
        break


# ==================================================
# 종료
# ==================================================

cv2.destroyAllWindows()

cam0.stop()
cam1.stop()
