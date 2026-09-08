import os
import time
import cv2
import numpy as np
from picamera2 import Picamera2

# ==================================================
# 캘리브레이션 데이터 로드
# ==================================================
CALIB_FILE = "stereo_calibration.npz"

if not os.path.exists(CALIB_FILE):
    print(f"⚠️ 오류: {CALIB_FILE} 파일이 없습니다. 캘리브레이션을 먼저 진행하세요.")
    exit()

data = np.load(CALIB_FILE)
mtx0 = data["mtx0"]
T = data["T"]

# Remap 찌그러짐 방지를 위해 float32 강제 형변환
map0_x = np.array(data["map0_x"], dtype=np.float32)
map0_y = np.array(data["map0_y"], dtype=np.float32)
map1_x = np.array(data["map1_x"], dtype=np.float32)
map1_y = np.array(data["map1_y"], dtype=np.float32)

fx = mtx0[0, 0]
baseline = np.linalg.norm(T)  # cm 단위

# ==================================================
# ArUco 마커 설정
# ==================================================
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()

# ==================================================
# 카메라 시작
# ==================================================
cam0 = Picamera2(0)
cam1 = Picamera2(1)

config0 = cam0.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"}
)
config1 = cam1.create_preview_configuration(
    main={"size": (640, 480), "format": "RGB888"}
)

cam0.configure(config0)
cam1.configure(config1)

cam0.start()
cam1.start()
time.sleep(2)

print("\n==========================================")
print("ArUco Stereo Distance Measurement")
print("종료하려면 'q'를 누르세요.")
print("==========================================\n")

while True:
    frame0 = cam0.capture_array()
    frame1 = cam1.capture_array()

    if frame0 is None or frame1 is None:
        continue

    # 메모리 연속성 확보 및 BGR 변환 (찌그러짐 방지 핵심)
    frame0 = cv2.cvtColor(np.ascontiguousarray(frame0), cv2.COLOR_RGB2BGR)
    frame1 = cv2.cvtColor(np.ascontiguousarray(frame1), cv2.COLOR_RGB2BGR)

    # Rectification (왜곡 보정)
    rect0 = cv2.remap(frame0, map0_x, map0_y, cv2.INTER_LINEAR)
    rect1 = cv2.remap(frame1, map1_x, map1_y, cv2.INTER_LINEAR)

    gray0 = cv2.cvtColor(rect0, cv2.COLOR_BGR2GRAY)
    gray1 = cv2.cvtColor(rect1, cv2.COLOR_BGR2GRAY)

    corners0, ids0, _ = cv2.aruco.detectMarkers(
        gray0, aruco_dict, parameters=aruco_params
    )
    corners1, ids1, _ = cv2.aruco.detectMarkers(
        gray1, aruco_dict, parameters=aruco_params
    )

    cv2.aruco.drawDetectedMarkers(rect0, corners0, ids0)
    cv2.aruco.drawDetectedMarkers(rect1, corners1, ids1)

    if ids0 is not None and ids1 is not None:
        for i, id0 in enumerate(ids0.flatten()):
            if id0 in ids1.flatten():
                j = np.where(ids1.flatten() == id0)[0][0]

                # 마커 중심점 계산
                c0 = corners0[i][0]
                c1 = corners1[j][0]

                center0 = np.mean(c0, axis=0)
                center1 = np.mean(c1, axis=0)

                cx0, cy0 = int(center0[0]), int(center0[1])
                cx1, cy1 = int(center1[0]), int(center1[1])

                cv2.circle(rect0, (cx0, cy0), 5, (0, 255, 0), -1)
                cv2.circle(rect1, (cx1, cy1), 5, (0, 255, 0), -1)

                # 시차 계산 (X축 거리 차이)
                disparity = abs(cx0 - cx1)

                if disparity > 0:
                    distance = (fx * baseline) / disparity
                    cv2.putText(
                        rect0,
                        f"ID:{id0} Dist: {distance:.1f} cm",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2,
                    )

    # 좌우 보정 영상 결합 출력
    stereo_view = cv2.hconcat([rect0, rect1])
    cv2.imshow("ArUco Stereo Distance", stereo_view)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cv2.destroyAllWindows()
cam0.stop()
cam1.stop()
