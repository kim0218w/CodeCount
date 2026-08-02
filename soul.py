import cv2

image = cv2.imread('test.jpg')

if image is not None:
    # 1. BGR 컬러를 흑백(Grayscale)으로 변환
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 2. 가우시안 블러 (이미지를 부드럽게/흐리게 처리하여 노이즈 제거)
    # (5, 5)는 커널 크기로, 홀수(3, 5, 7 등)로 설정합니다.
    blurred_image = cv2.GaussianBlur(image, (5, 5), 0)

    # 3. Canny 알고리즘을 이용한 외각선(Edge) 검출
    # 임계값(Threshold) 100과 200 사이의 경계선을 찾아냅니다.
    edges = cv2.Canny(gray_image, 100, 200)

    # 결과 보기
    cv2.imshow('Gray', gray_image)
    cv2.imshow('Blurred', blurred_image)
    cv2.imshow('Edges', edges)

    cv2.waitKey(0)
    cv2.destroyAllWindows()