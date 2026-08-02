import cv2

# 0번 카메라(기본 웹캠) 연결
cap = cv2.VideoCapture(0)

# 카메라가 정상적으로 열렸는지 확인
if not cap.isOpened():
    print("카메라를 열 수 없습니다.")
else:
    while True:
        # 프레임 단위로 영상 읽기
        ret, frame = cap.read()
        
        if not ret:
            print("프레임을 불러오지 못했습니다.")
            break

        # --- 영상 위에 도형 및 텍스트 그리기 ---s
        # 1. 사각형 그리기 (이미지, 좌상단 좌표, 우하단 좌표, 색상(BGR), 두께)
        cv2.rectangle(frame, (100, 100), (300, 300), (0, 255, 0), 2)

        # 2. 원 그리기 (이미지, 중심 좌표, 반지름, 색상, 두께)
        cv2.circle(frame, (200, 200), 50, (0, 0, 255), -1) # -1은 내부 채우기

        # 3. 텍스트 쓰기 (이미지, 텍스트, 위치, 폰트, 크기, 색상, 두께)
        cv2.putText(frame, "OpenCV Camera Test", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # 화면에 출력
        cv2.imshow('Webcam Live', frame)

        # 'q' 키를 누르면 반복문 종료
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 자원 해제
    cap.release()
    cv2.destroyAllWindows()