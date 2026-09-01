from picamera2 import Picamera2
import cv2
import time


# ==============================
# 카메라 생성
# ==============================

cam0 = Picamera2(0)
cam1 = Picamera2(1)


# ==============================
# 영상 설정
# ==============================

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


# ==============================
# 카메라 시작
# ==============================

cam0.start()
cam1.start()

time.sleep(2)


# ==============================
# 실시간 영상
# ==============================

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

    cv2.putText(
        frame0,
        "CAMERA 0",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame1,
        "CAMERA 1",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )

    # 두 영상 가로로 붙이기
    stereo_view = cv2.hconcat([
        frame0,
        frame1
    ])

    cv2.imshow(
        "Stereo Camera Test",
        stereo_view
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


cv2.destroyAllWindows()

cam0.stop()
cam1.stop()
