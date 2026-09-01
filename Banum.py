from picamera2 import Picamera2
import cv2
import numpy as np
import time


# ==================================================
# 설정
# ==================================================

MIN_AREA = 300

# 측정할 실제 거리
DISTANCES = [13.5, 11.5, 9.5, 7.5, 5.5, 3.5]

current_index = 0


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
# 노란색 타겟 색상 등록
# ==================================================

frame0 = cam0.capture_array()

frame0 = cv2.cvtColor(
    frame0,
    cv2.COLOR_RGB2BGR
)

print()
print("==========================================")
print("  Stereo Disparity Measurement")
print("==========================================")
print()
print("노란색 물체 내부를 마우스로 선택하세요.")
print("검은 테두리는 제외하세요.")
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


# ==================================================
# HSV 색상 계산
# ==================================================

selected = frame0[y:y+h, x:x+w]

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


    if not valid:
        return None


    target = max(
        valid,
        key=cv2.contourArea
    )


    x, y, w, h = cv2.boundingRect(target)


    cx = x + w / 2.0
    cy = y + h / 2.0


    return x, y, w, h, cx, cy


# ==================================================
# 사용법 출력
# ==================================================

print()
print("==========================================")
print("측정 시작")
print("==========================================")
print()

print("물체를 13.5 cm에 놓으세요.")
print()

print("s : 현재 값 기록")
print("q : 프로그램 종료")

print()


# ==================================================
# 실시간 측정
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


    # --------------------------------------------------
    # Camera 0
    # --------------------------------------------------

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


    # --------------------------------------------------
    # Camera 1
    # --------------------------------------------------

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


    # --------------------------------------------------
    # Signed disparity
    # --------------------------------------------------

    if cx0 is not None and cx1 is not None:

        # abs() 사용하지 않음!
        disparity = cx0 - cx1


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
            f"D: {disparity:.1f}px",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )


        cv2.putText(
            frame1,
            f"D: {disparity:.1f}px",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )


    # --------------------------------------------------
    # 현재 측정해야 할 거리 표시
    # --------------------------------------------------

    if current_index < len(DISTANCES):

        current_distance = DISTANCES[current_index]

        cv2.putText(
            frame0,
            f"Set target: {current_distance:.1f} cm",
            (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )


    # --------------------------------------------------
    # 화면 합치기
    # --------------------------------------------------

    stereo_view = cv2.hconcat([
        frame0,
        frame1
    ])


    cv2.imshow(
        "Stereo Measurement",
        stereo_view
    )


    key = cv2.waitKey(1) & 0xFF


    # ==================================================
    # S키 → 현재값 출력
    # ==================================================

    if key == ord("s"):

        if current_index >= len(DISTANCES):

            print()
            print("모든 거리 측정이 끝났습니다.")

        elif disparity is None:

            print()
            print("!!! 두 카메라에서 물체가 검출되지 않았습니다.")

        else:

            distance = DISTANCES[current_index]

            print()
            print("------------------------------------------")
            print(f"거리       : {distance:.1f} cm")
            print(f"Camera 0 X : {cx0:.1f} px")
            print(f"Camera 1 X : {cx1:.1f} px")
            print(f"Disparity  : {disparity:.1f} px")
            print("------------------------------------------")


            current_index += 1


            if current_index < len(DISTANCES):

                print()
                print(
                    f"다음: 물체를 "
                    f"{DISTANCES[current_index]:.1f} cm에 놓으세요."
                )

            else:

                print()
                print("==========================================")
                print("모든 측정 완료!")
                print("==========================================")


    # ==================================================
    # Q키 → 종료
    # ==================================================

    if key == ord("q"):
        break


cv2.destroyAllWindows()

cam0.stop()
cam1.stop()
