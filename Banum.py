from picamera2 import Picamera2
import cv2
import numpy as np
import time
import os


# ==================================================
# 설정
# ==================================================

# 체커보드 내부 코너 개수
CHECKERBOARD = (7, 6)

# 체커보드 한 칸 실제 크기(cm)
# 반드시 실제 화면에서 자로 재서 수정!
SQUARE_SIZE = 2.0

# 저장할 최소 이미지 수
MIN_IMAGES = 10

SAVE_DIR = "stereo_calibration"

os.makedirs(SAVE_DIR, exist_ok=True)


# ==================================================
# 카메라 시작
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
# 체커보드 3D 좌표
# ==================================================

objp = np.zeros(
    (CHECKERBOARD[0] * CHECKERBOARD[1], 3),
    np.float32
)

objp[:, :2] = (
    np.mgrid[
        0:CHECKERBOARD[0],
        0:CHECKERBOARD[1]
    ]
    .T
    .reshape(-1, 2)
)

objp *= SQUARE_SIZE


# ==================================================
# 저장 데이터
# ==================================================

objpoints = []

imgpoints0 = []
imgpoints1 = []

saved_count = 0


# ==================================================
# 코너 정밀화 조건
# ==================================================

criteria = (
    cv2.TERM_CRITERIA_EPS
    + cv2.TERM_CRITERIA_MAX_ITER,
    30,
    0.001
)


print()
print("==========================================")
print("Stereo Calibration Capture")
print("==========================================")
print()
print("체커보드를 두 카메라가 모두 볼 수 있게 하세요.")
print()
print("s : 현재 체커보드 위치 저장")
print("c : calibration 실행")
print("q : 종료")
print()
print(f"최소 {MIN_IMAGES}장 이상 권장")
print()


# ==================================================
# 촬영 단계
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

    gray0 = cv2.cvtColor(
        frame0,
        cv2.COLOR_BGR2GRAY
    )

    gray1 = cv2.cvtColor(
        frame1,
        cv2.COLOR_BGR2GRAY
    )


    # --------------------------------------------------
    # 체커보드 탐색
    # --------------------------------------------------

    ret0, corners0 = cv2.findChessboardCorners(
        gray0,
        CHECKERBOARD,
        None
    )

    ret1, corners1 = cv2.findChessboardCorners(
        gray1,
        CHECKERBOARD,
        None
    )


    # --------------------------------------------------
    # Camera 0 표시
    # --------------------------------------------------

    if ret0:

        corners0_refined = cv2.cornerSubPix(
            gray0,
            corners0,
            (11, 11),
            (-1, -1),
            criteria
        )

        cv2.drawChessboardCorners(
            frame0,
            CHECKERBOARD,
            corners0_refined,
            ret0
        )

        cv2.putText(
            frame0,
            "Checkerboard: OK",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

    else:

        cv2.putText(
            frame0,
            "Checkerboard: NOT FOUND",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )


    # --------------------------------------------------
    # Camera 1 표시
    # --------------------------------------------------

    if ret1:

        corners1_refined = cv2.cornerSubPix(
            gray1,
            corners1,
            (11, 11),
            (-1, -1),
            criteria
        )

        cv2.drawChessboardCorners(
            frame1,
            CHECKERBOARD,
            corners1_refined,
            ret1
        )

        cv2.putText(
            frame1,
            "Checkerboard: OK",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

    else:

        cv2.putText(
            frame1,
            "Checkerboard: NOT FOUND",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )


    # --------------------------------------------------
    # 저장 개수 표시
    # --------------------------------------------------

    text = f"Saved: {saved_count}"

    cv2.putText(
        frame0,
        text,
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame1,
        text,
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )


    stereo_view = cv2.hconcat([
        frame0,
        frame1
    ])

    cv2.imshow(
        "Stereo Calibration",
        stereo_view
    )


    key = cv2.waitKey(1) & 0xFF


    # ==================================================
    # S 키
    # ==================================================

    if key == ord("s"):

        if ret0 and ret1:

            objpoints.append(
                objp.copy()
            )

            imgpoints0.append(
                corners0_refined.copy()
            )

            imgpoints1.append(
                corners1_refined.copy()
            )


            filename0 = os.path.join(
                SAVE_DIR,
                f"cam0_{saved_count:02d}.jpg"
            )

            filename1 = os.path.join(
                SAVE_DIR,
                f"cam1_{saved_count:02d}.jpg"
            )


            cv2.imwrite(
                filename0,
                frame0
            )

            cv2.imwrite(
                filename1,
                frame1
            )


            saved_count += 1

            print(
                f"[{saved_count}] 저장 완료"
            )

        else:

            print(
                "두 카메라 모두에서 체커보드가 보여야 저장됩니다."
            )


    # ==================================================
    # C 키 → calibration
    # ==================================================

    if key == ord("c"):

        if saved_count < MIN_IMAGES:

            print()
            print(
                f"이미지가 부족합니다. "
                f"현재 {saved_count}장"
            )

            print(
                f"최소 {MIN_IMAGES}장 이상 저장하세요."
            )

            continue


        print()
        print("==========================================")
        print("Calibration 시작")
        print("==========================================")
        print()


        image_size = gray0.shape[::-1]


        # ==================================================
        # Camera 0 개별 calibration
        # ==================================================

        ret_cal0, mtx0, dist0, rvecs0, tvecs0 = (
            cv2.calibrateCamera(
                objpoints,
                imgpoints0,
                image_size,
                None,
                None
            )
        )


        # ==================================================
        # Camera 1 개별 calibration
        # ==================================================

        ret_cal1, mtx1, dist1, rvecs1, tvecs1 = (
            cv2.calibrateCamera(
                objpoints,
                imgpoints1,
                image_size,
                None,
                None
            )
        )


        print("Camera 0")
        print("fx =", mtx0[0, 0])
        print("fy =", mtx0[1, 1])
        print("cx =", mtx0[0, 2])
        print("cy =", mtx0[1, 2])
        print()

        print("Camera 1")
        print("fx =", mtx1[0, 0])
        print("fy =", mtx1[1, 1])
        print("cx =", mtx1[0, 2])
        print("cy =", mtx1[1, 2])
        print()


        # ==================================================
        # Stereo calibration
        # ==================================================

        stereo_flags = (
            cv2.CALIB_FIX_INTRINSIC
        )


        stereo_criteria = (
            cv2.TERM_CRITERIA_EPS
            + cv2.TERM_CRITERIA_MAX_ITER,
            100,
            1e-5
        )


        ret_stereo, \
        mtx0, dist0, \
        mtx1, dist1, \
        R, T, E, F = cv2.stereoCalibrate(
            objpoints,
            imgpoints0,
            imgpoints1,
            mtx0,
            dist0,
            mtx1,
            dist1,
            image_size,
            criteria=stereo_criteria,
            flags=stereo_flags
        )


        print()
        print("Stereo RMS Error:")
        print(ret_stereo)

        print()
        print("Rotation Matrix R:")
        print(R)

        print()
        print("Translation Vector T:")
        print(T)


        # ==================================================
        # 실제 baseline
        # ==================================================

        baseline = np.linalg.norm(T)

        print()
        print(
            f"Calculated Baseline: "
            f"{baseline:.4f} cm"
        )


        # ==================================================
        # Stereo Rectification
        # ==================================================

        R1, R2, P1, P2, Q, roi1, roi2 = (
            cv2.stereoRectify(
                mtx0,
                dist0,
                mtx1,
                dist1,
                image_size,
                R,
                T,
                alpha=0
            )
        )


        # ==================================================
        # Remap 생성
        # ==================================================

        map0_x, map0_y = cv2.initUndistortRectifyMap(
            mtx0,
            dist0,
            R1,
            P1,
            image_size,
            cv2.CV_32FC1
        )


        map1_x, map1_y = cv2.initUndistortRectifyMap(
            mtx1,
            dist1,
            R2,
            P2,
            image_size,
            cv2.CV_32FC1
        )


        # ==================================================
        # calibration 저장
        # ==================================================

        np.savez(
            "stereo_calibration.npz",

            mtx0=mtx0,
            dist0=dist0,

            mtx1=mtx1,
            dist1=dist1,

            R=R,
            T=T,

            R1=R1,
            R2=R2,

            P1=P1,
            P2=P2,

            Q=Q,

            map0_x=map0_x,
            map0_y=map0_y,

            map1_x=map1_x,
            map1_y=map1_y
        )


        print()
        print("==========================================")
        print("Calibration 완료")
        print("==========================================")
        print()
        print(
            "stereo_calibration.npz 저장 완료"
        )
        print()

        break


    # ==================================================
    # Q 키
    # ==================================================

    if key == ord("q"):
        break


# ==================================================
# 종료
# ==================================================

cv2.destroyAllWindows()

cam0.stop()
cam1.stop()
