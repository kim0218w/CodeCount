import cv2

# 1. 이미지 파일 읽기 (파일명 또는 경로 입력)
# cv2.IMREAD_COLOR: 컬러로 읽기 (기본값)
# cv2.IMREAD_GRAYSCALE: 흑백으로 읽기
image = cv2.imread('test.jpg')

# 이미지를 정상적으로 불러왔는지 확인
if image is None:
    print("이미지를 불러올 수 없습니다. 파일 경로를 확인해주세요.")
else:
    # 2. 이미지의 기본 정보 확인 (높이, 너비, 채널)
    height, width, channels = image.shape
    print(f"이미지 크기: {width}x{height}, 채널: {channels}")

    # 3. 창에 이미지 표시하기
    cv2.imshow('Original Image', image)

    # 4. 키보드 입력을 기다림 (0은 키 입력이 있을 때까지 무한 대기)
    cv2.waitKey(0)

    # 5. 다른 이름으로 이미지 저장하기
    cv2.imwrite('output_copy.jpg', image)

    # 6. 생성된 모든 OpenCV 창 닫기
    cv2.destroyAllWindows()