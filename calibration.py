import cv2
import numpy as np
import os
import glob
import time
from picamera2 import Picamera2


# ============================================================
# 사용자 설정
# ============================================================

CALIB_FILE = "calibration.npz"

CALIB_LEFT_DIR = "calibration/left"
CALIB_RIGHT_DIR = "calibration/right"

# 카메라 해상도
WIDTH = 1920
HEIGHT = 1080

FPS = 30

# ------------------------------------------------------------
# Checkerboard 설정
# "사각형 개수"가 아니라 내부 코너 개수
# 예: 10 x 7 체커보드 -> 내부 코너 9 x 6
# ------------------------------------------------------------

CHECKERBOARD = (9, 6)

# 체커보드 한 칸 실제 크기(mm)
SQUARE_SIZE_MM = 10.0

# Calibration 최소 이미지 수
MIN_CALIB_IMAGES = 15

# ------------------------------------------------------------
# Stereo Matching 설정
# ------------------------------------------------------------

MIN_DISPARITY = 0

# 반드시 16의 배수
NUM_DISPARITIES = 256

BLOCK_SIZE = 5

# ============================================================
# 디렉터리 생성
# ============================================================

os.makedirs(CALIB_LEFT_DIR, exist_ok=True)
os.makedirs(CALIB_RIGHT_DIR, exist_ok=True)


# ============================================================
# 카메라 초기화
# ============================================================

def create_cameras():

    print("카메라 초기화 중...")

    left_camera = Picamera2(0)
    right_camera = Picamera2(1)

    config_left = left_camera.create_video_configuration(
        main={
            "size": (WIDTH, HEIGHT),
            "format": "RGB888"
        },
        controls={
            "FrameRate": FPS
        }
    )

    config_right = right_camera.create_video_configuration(
        main={
            "size": (WIDTH, HEIGHT),
            "format": "RGB888"
        },
        controls={
            "FrameRate": FPS
        }
    )

    left_camera.configure(config_left)
    right_camera.configure(config_right)

    left_camera.start()
    right_camera.start()

    time.sleep(2)

    print("카메라 초기화 완료")

    return left_camera, right_camera


# ============================================================
# Checkerboard 검출
# ============================================================

def find_checkerboard(image):

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    flags = (
        cv2.CALIB_CB_ADAPTIVE_THRESH |
        cv2.CALIB_CB_NORMALIZE_IMAGE
    )

    found, corners = cv2.findChessboardCorners(
        gray,
        CHECKERBOARD,
        flags
    )

    if not found:
        return False, None

    criteria = (
        cv2.TERM_CRITERIA_EPS |
        cv2.TERM_CRITERIA_MAX_ITER,
        100,
        0.0001
    )

    corners = cv2.cornerSubPix(
        gray,
        corners,
        (11, 11),
        (-1, -1),
        criteria
    )

    return True, corners


# ============================================================
# Calibration 이미지 촬영
# ============================================================

def capture_calibration_images(
    left_camera,
    right_camera
):

    print()
    print("============================================")
    print("STEREO CALIBRATION IMAGE CAPTURE")
    print("============================================")
    print()
    print("체커보드를 두 카메라에 동시에 보여주세요.")
    print()
    print("SPACE : Calibration 이미지 저장")
    print("ESC   : 촬영 종료")
    print()

    saved_count = 0

    while True:

        left = left_camera.capture_array()
        right = right_camera.capture_array()

        left = cv2.cvtColor(
            left,
            cv2.COLOR_RGB2BGR
        )

        right = cv2.cvtColor(
            right,
            cv2.COLOR_RGB2BGR
        )

        left_display = left.copy()
        right_display = right.copy()

        found_left, corners_left = find_checkerboard(left)
        found_right, corners_right = find_checkerboard(right)

        # ----------------------------------------------------
        # LEFT 표시
        # ----------------------------------------------------

        if found_left:

            cv2.drawChessboardCorners(
                left_display,
                CHECKERBOARD,
                corners_left,
                found_left
            )

            cv2.putText(
                left_display,
                "LEFT: OK",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 255, 0),
                2
            )

        else:

            cv2.putText(
                left_display,
                "LEFT: NOT FOUND",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 0, 255),
                2
            )

        # ----------------------------------------------------
        # RIGHT 표시
        # ----------------------------------------------------

        if found_right:

            cv2.drawChessboardCorners(
                right_display,
                CHECKERBOARD,
                corners_right,
                found_right
            )

            cv2.putText(
                right_display,
                "RIGHT: OK",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 255, 0),
                2
            )

        else:

            cv2.putText(
                right_display,
                "RIGHT: NOT FOUND",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 0, 255),
                2
            )

        cv2.putText(
            left_display,
            f"Saved: {saved_count}",
            (30, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 0),
            2
        )

        cv2.imshow(
            "LEFT - Calibration",
            left_display
        )

        cv2.imshow(
            "RIGHT - Calibration",
            right_display
        )

        key = cv2.waitKey(1) & 0xFF

        # ----------------------------------------------------
        # SPACE -> 저장
        # ----------------------------------------------------

        if key == 32:

            if found_left and found_right:

                filename = f"{saved_count + 1:04d}.jpg"

                left_path = os.path.join(
                    CALIB_LEFT_DIR,
                    filename
                )

                right_path = os.path.join(
                    CALIB_RIGHT_DIR,
                    filename
                )

                cv2.imwrite(
                    left_path,
                    left
                )

                cv2.imwrite(
                    right_path,
                    right
                )

                saved_count += 1

                print(
                    f"[저장] {filename}"
                )

                # 같은 자세의 중복 저장 방지
                time.sleep(0.3)

            else:

                print(
                    "체커보드가 양쪽 카메라에서 "
                    "모두 검출되어야 합니다."
                )

        # ----------------------------------------------------
        # ESC
        # ----------------------------------------------------

        elif key == 27:

            break

    cv2.destroyAllWindows()

    return saved_count


# ============================================================
# Stereo Calibration
# ============================================================

def calibrate_stereo():

    print()
    print("============================================")
    print("STEREO CALIBRATION")
    print("============================================")

    left_files = sorted(
        glob.glob(
            os.path.join(
                CALIB_LEFT_DIR,
                "*.jpg"
            )
        )
    )

    right_files = sorted(
        glob.glob(
            os.path.join(
                CALIB_RIGHT_DIR,
                "*.jpg"
            )
        )
    )

    if len(left_files) != len(right_files):

        raise RuntimeError(
            "LEFT / RIGHT Calibration 이미지 개수가 다릅니다."
        )

    if len(left_files) < MIN_CALIB_IMAGES:

        raise RuntimeError(
            f"Calibration 이미지가 부족합니다. "
            f"현재 {len(left_files)}장 / "
            f"최소 {MIN_CALIB_IMAGES}장"
        )

    # --------------------------------------------------------
    # 3D Checkerboard 좌표
    # --------------------------------------------------------

    object_point = np.zeros(
        (
            CHECKERBOARD[0] *
            CHECKERBOARD[1],
            3
        ),
        dtype=np.float32
    )

    object_point[:, :2] = np.mgrid[
        0:CHECKERBOARD[0],
        0:CHECKERBOARD[1]
    ].T.reshape(-1, 2)

    object_point *= SQUARE_SIZE_MM

    object_points = []

    left_points = []
    right_points = []

    image_size = None

    valid_count = 0

    # --------------------------------------------------------
    # 모든 Calibration 이미지 처리
    # --------------------------------------------------------

    for left_file, right_file in zip(
        left_files,
        right_files
    ):

        left = cv2.imread(left_file)
        right = cv2.imread(right_file)

        if left is None or right is None:
            continue

        gray_left = cv2.cvtColor(
            left,
            cv2.COLOR_BGR2GRAY
        )

        gray_right = cv2.cvtColor(
            right,
            cv2.COLOR_BGR2GRAY
        )

        image_size = (
            gray_left.shape[1],
            gray_left.shape[0]
        )

        found_left, corners_left = \
            find_checkerboard(left)

        found_right, corners_right = \
            find_checkerboard(right)

        if found_left and found_right:

            object_points.append(
                object_point.copy()
            )

            left_points.append(
                corners_left
            )

            right_points.append(
                corners_right
            )

            valid_count += 1

            print(
                f"[OK] "
                f"{os.path.basename(left_file)}"
            )

        else:

            print(
                f"[FAIL] "
                f"{os.path.basename(left_file)}"
            )

    print()
    print(
        "사용 가능한 Calibration 쌍:",
        valid_count
    )

    if valid_count < MIN_CALIB_IMAGES:

        raise RuntimeError(
            "유효한 Calibration 이미지가 부족합니다."
        )

    # --------------------------------------------------------
    # LEFT Camera Calibration
    # --------------------------------------------------------

    print()
    print("LEFT Camera Calibration...")

    left_rms, K1, D1, _, _ = \
        cv2.calibrateCamera(
            object_points,
            left_points,
            image_size,
            None,
            None
        )

    # --------------------------------------------------------
    # RIGHT Camera Calibration
    # --------------------------------------------------------

    print(
        "RIGHT Camera Calibration..."
    )

    right_rms, K2, D2, _, _ = \
        cv2.calibrateCamera(
            object_points,
            right_points,
            image_size,
            None,
            None
        )

    # --------------------------------------------------------
    # Stereo Calibration
    # --------------------------------------------------------

    print()
    print("Stereo Calibration...")

    criteria = (
        cv2.TERM_CRITERIA_EPS |
        cv2.TERM_CRITERIA_MAX_ITER,
        100,
        1e-6
    )

    flags = cv2.CALIB_FIX_INTRINSIC

    stereo_rms, K1, D1, K2, D2, R, T, E, F = \
        cv2.stereoCalibrate(
            object_points,
            left_points,
            right_points,
            K1,
            D1,
            K2,
            D2,
            image_size,
            criteria=criteria,
            flags=flags
        )

    # --------------------------------------------------------
    # Rectification
    # --------------------------------------------------------

    R1, R2, P1, P2, Q, roi1, roi2 = \
        cv2.stereoRectify(
            K1,
            D1,
            K2,
            D2,
            image_size,
            R,
            T,
            flags=cv2.CALIB_ZERO_DISPARITY,
            alpha=0
        )

    baseline = np.linalg.norm(T)

    # --------------------------------------------------------
    # 결과 출력
    # --------------------------------------------------------

    print()
    print("============================================")
    print("CALIBRATION RESULT")
    print("============================================")

    print(
        f"LEFT RMS  : {left_rms:.6f}"
    )

    print(
        f"RIGHT RMS : {right_rms:.6f}"
    )

    print(
        f"STEREO RMS: {stereo_rms:.6f}"
    )

    print(
        f"BASELINE  : {baseline:.3f} mm"
    )

    print()
    print("Translation T:")
    print(T)

    # --------------------------------------------------------
    # Calibration 저장
    # --------------------------------------------------------

    np.savez(
        CALIB_FILE,

        K1=K1,
        D1=D1,

        K2=K2,
        D2=D2,

        R=R,
        T=T,

        R1=R1,
        R2=R2,

        P1=P1,
        P2=P2,

        Q=Q,

        width=image_size[0],
        height=image_size[1],

        baseline=baseline
    )

    print()
    print(
        f"Calibration 저장 완료: {CALIB_FILE}"
    )

    return True


# ============================================================
# Stereo Measurement
# ============================================================

class StereoMeasurement:

    def __init__(self):

        print()
        print("Calibration 데이터 로드...")

        data = np.load(CALIB_FILE)

        self.K1 = data["K1"]
        self.D1 = data["D1"]

        self.K2 = data["K2"]
        self.D2 = data["D2"]

        self.R1 = data["R1"]
        self.R2 = data["R2"]

        self.P1 = data["P1"]
        self.P2 = data["P2"]

        self.Q = data["Q"]

        self.width = int(
            data["width"]
        )

        self.height = int(
            data["height"]
        )

        # ----------------------------------------------------
        # Rectification map
        # ----------------------------------------------------

        self.map1x, self.map1y = \
            cv2.initUndistortRectifyMap(
                self.K1,
                self.D1,
                self.R1,
                self.P1,
                (self.width, self.height),
                cv2.CV_32FC1
            )

        self.map2x, self.map2y = \
            cv2.initUndistortRectifyMap(
                self.K2,
                self.D2,
                self.R2,
                self.P2,
                (self.width, self.height),
                cv2.CV_32FC1
            )

        # ----------------------------------------------------
        # Stereo SGBM
        # ----------------------------------------------------

        self.stereo = cv2.StereoSGBM_create(

            minDisparity=MIN_DISPARITY,

            numDisparities=NUM_DISPARITIES,

            blockSize=BLOCK_SIZE,

            P1=8 * 1 * BLOCK_SIZE ** 2,

            P2=32 * 1 * BLOCK_SIZE ** 2,

            disp12MaxDiff=1,

            uniquenessRatio=8,

            speckleWindowSize=100,

            speckleRange=2,

            preFilterCap=63,

            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
        )

        print("Measurement system ready.")

    # --------------------------------------------------------
    # 두 영상 Rectification
    # --------------------------------------------------------

    def rectify(self, left, right):

        left_rect = cv2.remap(
            left,
            self.map1x,
            self.map1y,
            cv2.INTER_LINEAR
        )

        right_rect = cv2.remap(
            right,
            self.map2x,
            self.map2y,
            cv2.INTER_LINEAR
        )

        return left_rect, right_rect

    # --------------------------------------------------------
    # Disparity
    # --------------------------------------------------------

    def calculate_disparity(
        self,
        left,
        right
    ):

        gray_left = cv2.cvtColor(
            left,
            cv2.COLOR_BGR2GRAY
        )

        gray_right = cv2.cvtColor(
            right,
            cv2.COLOR_BGR2GRAY
        )

        disparity = self.stereo.compute(
            gray_left,
            gray_right
        ).astype(np.float32) / 16.0

        return disparity

    # --------------------------------------------------------
    # 특정 픽셀의 3D 좌표
    # --------------------------------------------------------

    def get_3d_point(
        self,
        disparity,
        x,
        y
    ):

        d = float(
            disparity[y, x]
        )

        if d <= 0:

            return None

        # Q matrix를 이용한 3D 변환
        point = np.array(
            [
                [float(x)],
                [float(y)],
                [d],
                [1.0]
            ],
            dtype=np.float64
        )

        xyz = self.Q @ point

        if abs(xyz[3, 0]) < 1e-10:

            return None

        xyz = xyz[:3, 0] / xyz[3, 0]

        return xyz

    # --------------------------------------------------------
    # 거리 계산
    # --------------------------------------------------------

    def get_distance(
        self,
        xyz
    ):

        x = xyz[0]
        y = xyz[1]
        z = xyz[2]

        distance = np.sqrt(
            x * x +
            y * y +
            z * z
        )

        return distance


# ============================================================
# 마우스
# ============================================================

selected_point = None


def mouse_callback(
    event,
    x,
    y,
    flags,
    param
):

    global selected_point

    if event == cv2.EVENT_LBUTTONDOWN:

        selected_point = (
            x,
            y
        )

        print(
            f"측정점 선택: "
            f"X={x}, Y={y}"
        )


# ============================================================
# Measurement Mode
# ============================================================

def measurement_mode(
    left_camera,
    right_camera
):

    measurement = StereoMeasurement()

    global selected_point

    cv2.namedWindow(
        "Stereo Measurement"
    )

    cv2.setMouseCallback(
        "Stereo Measurement",
        mouse_callback
    )

    print()
    print("============================================")
    print("DISTANCE MEASUREMENT MODE")
    print("============================================")
    print()
    print("왼쪽 영상에서 측정할 점을 클릭하세요.")
    print()
    print("ESC : 종료")
    print()

    while True:

        left = left_camera.capture_array()
        right = right_camera.capture_array()

        left = cv2.cvtColor(
            left,
            cv2.COLOR_RGB2BGR
        )

        right = cv2.cvtColor(
            right,
            cv2.COLOR_RGB2BGR
        )

        # ----------------------------------------------------
        # Rectification
        # ----------------------------------------------------

        left_rect, right_rect = \
            measurement.rectify(
                left,
                right
            )

        # ----------------------------------------------------
        # Disparity
        # ----------------------------------------------------

        disparity = \
            measurement.calculate_disparity(
                left_rect,
                right_rect
            )

        display = left_rect.copy()

        # ----------------------------------------------------
        # 측정점
        # ----------------------------------------------------

        if selected_point is not None:

            x, y = selected_point

            if (
                0 <= x < disparity.shape[1]
                and
                0 <= y < disparity.shape[0]
            ):

                xyz = measurement.get_3d_point(
                    disparity,
                    x,
                    y
                )

                if xyz is not None:

                    distance = \
                        measurement.get_distance(
                            xyz
                        )

                    cv2.circle(
                        display,
                        (x, y),
                        8,
                        (0, 0, 255),
                        2
                    )

                    cv2.putText(
                        display,
                        f"X : {xyz[0]:.2f} mm",
                        (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        display,
                        f"Y : {xyz[1]:.2f} mm",
                        (30, 85),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        display,
                        f"Z : {xyz[2]:.2f} mm",
                        (30, 120),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        display,
                        f"Distance : {distance:.2f} mm",
                        (30, 165),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 255, 255),
                        3
                    )

        cv2.imshow(
            "Stereo Measurement",
            display
        )

        key = cv2.waitKey(1) & 0xFF

        if key == 27:

            break

    cv2.destroyAllWindows()


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("============================================")
    print(" Raspberry Pi 5 Stereo Distance System")
    print(" IMX519 x 2")
    print("============================================")

    # --------------------------------------------------------
    # 카메라 시작
    # --------------------------------------------------------

    left_camera, right_camera = \
        create_cameras()

    try:

        # ====================================================
        # 1. Calibration 존재 여부 확인
        # ====================================================

        if not os.path.exists(CALIB_FILE):

            print()
            print(
                "Calibration 파일이 없습니다."
            )

            print(
                "Calibration을 시작합니다."
            )

            # -----------------------------------------------
            # Calibration 이미지 촬영
            # -----------------------------------------------

            count = capture_calibration_images(
                left_camera,
                right_camera
            )

            print()
            print(
                f"촬영된 Calibration 이미지: "
                f"{count}"
            )

            if count < MIN_CALIB_IMAGES:

                raise RuntimeError(
                    "Calibration 이미지가 부족합니다."
                )

            # -----------------------------------------------
            # Calibration 계산
            # -----------------------------------------------

            calibrate_stereo()

        else:

            print()
            print(
                "기존 Calibration 파일 발견:"
            )

            print(
                CALIB_FILE
            )

            print(
                "Calibration을 건너뜁니다."
            )

        # ====================================================
        # 2. 거리 측정
        # ====================================================

        measurement_mode(
            left_camera,
            right_camera
        )

    finally:

        left_camera.stop()
        right_camera.stop()

        cv2.destroyAllWindows()

        print()
        print("프로그램 종료")


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":

    main()
