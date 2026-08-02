import cv2

image = cv2.imread('test.jpg')

if image is not None:
    # --- 1. 이미지 크기 조절 (Resize) ---
    # 가로 400, 세로 300 피처로 변경
    resized_image = cv2.resize(image, (400, 300))
    
    # 비율을 유지하며 절반(0.5배)으로 줄이기
    half_image = cv2.resize(image, (0, 0), fx=0.5, fy=0.5)

    # --- 2. 이미지 자르기 (Crop) ---
    # OpenCV 이미지는 Numpy 배열이므로 [y축 범위, x축 범위]로 자릅니다.
    # 예: y축 50~250px, x축 100~300px 영역 추출
    cropped_image = image[50:250, 100:300]

    # 결과 확인
    cv2.imshow('Resized (400x300)', resized_image)
    cv2.imshow('Cropped', cropped_image)
    
    cv2.waitKey(0)
    cv2.destroyAllWindows()