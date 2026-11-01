import cv2
import numpy as np
import time
import tkinter as tk
from tkinter import simpledialog
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
import threading

# Raspberry Pi 카메라 지원 (picamera2)
try:
    from picamera2 import Picamera2
    USE_PICAMERA2 = True
except ImportError:
    USE_PICAMERA2 = False
    print("[INFO] picamera2 not found, using standard camera")   

# ===== 설정 =====
SOURCE = 0  # USB 카메라 폴백 인덱스
CAMERA_RESOLUTION = (1280, 720)
CAMERA_FPS = 30
CAMERA_INDEX = 0  # 연결된 IMX519이 여러 대일 때 변경
# 자동초점은 Arducam 드라이버 및 세부 모델에 따라 지원 여부가 다름.
# 초기 버전은 카메라의 기본 초점 동작을 사용하고 AF 명령은 강제하지 않음.
FONT = cv2.FONT_HERSHEY_SIMPLEX

# ===== 전역 변수 =====
FIXED_Z_DISTANCE = 0.032  # 3.2cm = 0.032m (기본값)
focal_length = 800.0  # 픽셀 단위 가정 초점거리 (캘리브레이션되지 않음)

selected_points = []  # 선택한 3점의 초기 픽셀 좌표
point_names = ['Point 1', 'Point 2', 'Point 3']
tracked_points = []  # 추적 중인 점들 (실시간 업데이트)

tracking_active = False
freeze_points = False  # 점 위치 고정 모드 (True = 1초마다 업데이트, False = 실시간 추적)
last_freeze_update_time = 0  # 마지막 고정 모드 업데이트 시간

# 측정 관련 변수
measurement_active = False
last_measurement_time = 0
measurement_log = []  # 측정 기록 저장

# 그래프 관련 변수
graph_enabled = False
graph_data_time = deque(maxlen=100)  # 최근 100개 데이터만 유지
graph_data_p1 = deque(maxlen=100)
graph_data_p2 = deque(maxlen=100)
graph_data_p3 = deque(maxlen=100)
graph_start_time = None
graph_lock = threading.Lock()

# 실시간 막대그래프 표시 설정
show_bar_graph = True  # 기본적으로 막대그래프 표시
bar_graph_position = 'right'  # 'bottom' 또는 'right' - 오른쪽에 작게 배치

def draw_realtime_bar_graph(frame, distances_cm, point_names, colors, position='bottom', z_values_cm=None):
    """
    OpenCV를 사용해 실시간 막대그래프를 프레임에 그리기
    
    Args:
        frame: OpenCV 프레임
        distances_cm: [dist1, dist2, dist3] 거리 리스트 (cm)
        point_names: 점 이름 리스트
        colors: 색상 리스트 (BGR)
        position: 'bottom' 또는 'right' (그래프 위치)
    
    Returns:
        그래프가 추가된 프레임
    """
    h, w = frame.shape[:2]
    
    if position == 'bottom':
        # 하단에 그래프 영역 추가
        graph_height = 280  # 조정 가이드를 위해 높이 증가
        graph_width = w
        graph_frame = np.zeros((graph_height, graph_width, 3), dtype=np.uint8)
        graph_frame[:] = (40, 40, 40)  # 어두운 배경
        
        # 그래프 영역 설정
        margin = 100
        bar_area_width = graph_width - 2 * margin
        bar_width = bar_area_width // 6  # 3개 막대 + 간격
        bar_spacing = bar_width // 2
        
        # 최대값 찾기 (스케일링용)
        if distances_cm and len(distances_cm) > 0 and all(d is not None for d in distances_cm):
            # 평균값 계산
            avg_distance = sum(distances_cm) / len(distances_cm)
            max_distance = max(distances_cm)
            min_distance = min(distances_cm)
            
            # 고정 스케일: 평균값 ±20% 범위 (실제 차이를 정확히 보여줌)
            y_center = avg_distance
            y_range = avg_distance * 0.4  # ±20%
            y_max = y_center + y_range / 2
            y_min = max(0, y_center - y_range / 2)
            
            graph_max_height = graph_height - 80  # 그래프 최대 높이
            graph_bottom = graph_height - 30  # 그래프 바닥
            
            # 제목
            cv2.putText(graph_frame, "Real-time Distance Bar Graph (Fixed Scale)", 
                       (graph_width // 2 - 250, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.7, (255, 255, 255), 2)
            
            # 평균값과 편차 정보 표시
            max_diff = max_distance - avg_distance
            min_diff = min_distance - avg_distance
            max_deviation = max(abs(max_diff), abs(min_diff))
            
            info_text = f"Average: {avg_distance:.2f}cm | Max Deviation: {max_deviation*10:.1f}mm"
            cv2.putText(graph_frame, info_text, 
                       (graph_width // 2 - 180, 55), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, (200, 200, 200), 1)
            
            # 기준선 그리기
            cv2.line(graph_frame, (margin, graph_bottom), 
                    (graph_width - margin, graph_bottom), (150, 150, 150), 2)
            
            # 평균 기준선 그리기 (녹색 점선)
            avg_normalized = (avg_distance - y_min) / y_range
            avg_y_pos = int(graph_bottom - (graph_max_height * avg_normalized))
            
            # 점선으로 평균선 그리기
            for x in range(margin, graph_width - margin, 20):
                cv2.line(graph_frame, (x, avg_y_pos), (x + 10, avg_y_pos), (0, 255, 0), 2)
            
            # 평균선 레이블
            cv2.putText(graph_frame, f"AVG: {avg_distance:.2f}cm", 
                       (margin - 95, avg_y_pos + 5), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.45, (0, 255, 0), 1)
            
            # 허용 오차 영역 표시 (±1mm = ±0.1cm)
            tolerance_cm = 0.1  # 1mm
            tolerance_upper = avg_distance + tolerance_cm
            tolerance_lower = avg_distance - tolerance_cm
            
            if y_min <= tolerance_lower <= y_max:
                tol_lower_normalized = (tolerance_lower - y_min) / y_range
                tol_lower_y = int(graph_bottom - (graph_max_height * tol_lower_normalized))
                for x in range(margin, graph_width - margin, 15):
                    cv2.line(graph_frame, (x, tol_lower_y), (x + 7, tol_lower_y), (0, 200, 200), 1)
            
            if y_min <= tolerance_upper <= y_max:
                tol_upper_normalized = (tolerance_upper - y_min) / y_range
                tol_upper_y = int(graph_bottom - (graph_max_height * tol_upper_normalized))
                for x in range(margin, graph_width - margin, 15):
                    cv2.line(graph_frame, (x, tol_upper_y), (x + 7, tol_upper_y), (0, 200, 200), 1)
            
            # Y축 눈금 표시 (5단계)
            for i in range(6):
                y_val = y_min + (y_range * i / 5)
                y_pos = int(graph_bottom - (graph_max_height * i / 5))
                cv2.line(graph_frame, (margin - 10, y_pos), 
                        (margin, y_pos), (150, 150, 150), 1)
                cv2.putText(graph_frame, f"{y_val:.1f}", 
                           (margin - 70, y_pos + 5), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.4, (200, 200, 200), 1)
            
            # Y축 레이블
            cv2.putText(graph_frame, "cm", 
                       (margin - 80, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, (200, 200, 200), 1)
            
            # 막대 그리기
            for i, (distance, name, color) in enumerate(zip(distances_cm, point_names, colors)):
                if distance is not None and distance > 0:
                    # 막대 위치 계산
                    x_start = margin + i * (bar_width + bar_spacing) + bar_spacing
                    x_center = x_start + bar_width // 2
                    
                    # 막대 높이 계산 (정규화)
                    normalized_height = (distance - y_min) / y_range
                    bar_height = int(graph_max_height * normalized_height)
                    
                    # 평균 대비 차이 계산
                    diff_from_avg = distance - avg_distance
                    diff_mm = diff_from_avg * 10  # cm → mm
                    
                    # 막대 색상 (평균 ±1mm 이내면 녹색 테두리)
                    is_aligned = abs(diff_mm) <= 1.0
                    border_color = (0, 255, 0) if is_aligned else (255, 255, 255)
                    border_thickness = 3 if is_aligned else 2
                    
                    # 막대 그리기
                    y_start = graph_bottom - bar_height
                    cv2.rectangle(graph_frame, 
                                (x_start, y_start), 
                                (x_start + bar_width, graph_bottom), 
                                color, -1)
                    
                    # 막대 테두리
                    cv2.rectangle(graph_frame, 
                                (x_start, y_start), 
                                (x_start + bar_width, graph_bottom), 
                                border_color, border_thickness)
                    
                    # 거리 값 표시 (막대 위)
                    text = f"{distance:.2f}cm"
                    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                    text_x = x_start + (bar_width - text_size[0]) // 2
                    text_y = y_start - 35 if y_start > 50 else y_start + 20
                    cv2.putText(graph_frame, text, 
                               (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.5, (255, 255, 255), 2)
                    
                    # 평균 대비 조정량 표시 (화살표 + 값)
                    if abs(diff_mm) > 0.1:  # 0.1mm 이상 차이나면 표시
                        arrow_color = (0, 255, 255)  # 노란색
                        if diff_mm > 0:
                            # 평균보다 높음 -> 내려야 함
                            arrow_text = f"DOWN {abs(diff_mm):.1f}mm"
                            arrow_symbol = "↓"
                        else:
                            # 평균보다 낮음 -> 올려야 함
                            arrow_text = f"UP {abs(diff_mm):.1f}mm"
                            arrow_symbol = "↑"
                        
                        # 화살표와 조정량
                        adj_text_size = cv2.getTextSize(arrow_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
                        adj_text_x = x_start + (bar_width - adj_text_size[0]) // 2
                        adj_text_y = y_start - 15 if y_start > 50 else y_start + 35
                        
                        cv2.putText(graph_frame, arrow_text, 
                                   (adj_text_x, adj_text_y), cv2.FONT_HERSHEY_SIMPLEX, 
                                   0.45, arrow_color, 2)
                        
                        # 큰 화살표 표시
                        cv2.putText(graph_frame, arrow_symbol, 
                                   (x_center - 8, text_y - 15 if y_start > 50 else text_y + 35), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, arrow_color, 2)
                    else:
                        # 정렬됨 표시
                        cv2.putText(graph_frame, "OK", 
                                   (x_center - 15, text_y - 15 if y_start > 50 else text_y + 35), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    # 점 이름 (막대 아래)
                    name_size = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
                    name_x = x_start + (bar_width - name_size[0]) // 2
                    cv2.putText(graph_frame, name, 
                               (name_x, graph_bottom + 25), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, color, 2)
        
        else:
            # 데이터가 없을 때
            cv2.putText(graph_frame, "Waiting for 3 points selection...", 
                       (graph_width // 2 - 200, graph_height // 2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (150, 150, 150), 2)
        
        # 프레임에 그래프 추가
        combined_frame = np.vstack([frame, graph_frame])
        return combined_frame
    
    elif position == 'right':
        # 오른쪽에 세로 막대그래프 영역 추가
        graph_width = 350  # 좁은 폭
        graph_height = h
        graph_frame = np.zeros((graph_height, graph_width, 3), dtype=np.uint8)
        graph_frame[:] = (35, 35, 35)  # 어두운 배경
        
        if distances_cm and len(distances_cm) > 0 and all(d is not None for d in distances_cm):
            # Z축 기준 계산
            if z_values_cm and len(z_values_cm) == len(distances_cm):
                # Z축 평균을 기준으로 사용
                z_reference = sum(z_values_cm) / len(z_values_cm)
            else:
                z_reference = None
            
            # 평균값 계산
            avg_distance = sum(distances_cm) / len(distances_cm)
            max_distance = max(distances_cm)
            min_distance = min(distances_cm)
            
            # 고정 스케일: 평균값 ±20% 범위
            y_center = avg_distance
            y_range = avg_distance * 0.4
            y_max = y_center + y_range / 2
            y_min = max(0, y_center - y_range / 2)
            
            # 그래프 영역 설정
            margin_top = 100
            margin_bottom = 80
            margin_side = 40
            graph_area_height = graph_height - margin_top - margin_bottom
            
            # 제목 (작게)
            cv2.putText(graph_frame, "Bar Graph", 
                       (graph_width // 2 - 50, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.6, (255, 255, 255), 2)
            
            # Z축 기준과 편차 정보
            if z_reference is not None and z_values_cm:
                max_z_diff = max([abs(z - z_reference) for z in z_values_cm])
                cv2.putText(graph_frame, f"Z-ref: {z_reference:.2f}cm", 
                           (margin_side, 55), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.45, (200, 200, 200), 1)
                cv2.putText(graph_frame, f"Max Z-diff: {max_z_diff*10:.1f}mm", 
                           (margin_side, 75), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.45, (200, 200, 200), 1)
            else:
                # Z값이 없으면 평균 기준
                max_diff = max_distance - avg_distance
                min_diff = min_distance - avg_distance
                max_deviation = max(abs(max_diff), abs(min_diff))
                cv2.putText(graph_frame, f"Avg: {avg_distance:.2f}cm", 
                           (margin_side, 55), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.45, (200, 200, 200), 1)
                cv2.putText(graph_frame, f"Dev: {max_deviation*10:.1f}mm", 
                           (margin_side, 75), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.45, (200, 200, 200), 1)
            
            # 막대 영역
            bar_height = graph_area_height // 5
            bar_spacing = bar_height // 3
            bar_max_width = graph_width - 2 * margin_side - 80  # 왼쪽에 레이블 공간
            
            # 세로로 3개 막대 그리기
            for i, (distance, name, color) in enumerate(zip(distances_cm, point_names, colors)):
                if distance is not None and distance > 0:
                    y_pos = margin_top + i * (bar_height + bar_spacing)
                    
                    # Z축 기준 차이 계산
                    if z_reference is not None and z_values_cm and i < len(z_values_cm):
                        # Z축 평균 대비 현재 점의 Z값 차이
                        z_diff = z_values_cm[i] - z_reference  # cm 단위
                        z_diff_mm = z_diff * 10  # mm 단위
                    else:
                        # Z값이 없으면 평균 거리 대비 차이
                        z_diff = distance - avg_distance
                        z_diff_mm = z_diff * 10
                    
                    # 정렬 여부 (1mm 이내)
                    is_aligned = abs(z_diff_mm) <= 1.0
                    border_color = (0, 255, 0) if is_aligned else (255, 255, 255)
                    
                    # 막대 폭 계산 (정규화)
                    normalized_width = (distance - y_min) / y_range
                    bar_width_val = int(bar_max_width * normalized_width)
                    
                    x_start = margin_side + 60  # 레이블 공간
                    
                    # 막대 그리기
                    cv2.rectangle(graph_frame,
                                (x_start, y_pos),
                                (x_start + bar_width_val, y_pos + bar_height),
                                color, -1)
                    
                    # 막대 테두리
                    cv2.rectangle(graph_frame,
                                (x_start, y_pos),
                                (x_start + bar_width_val, y_pos + bar_height),
                                border_color, 2)
                    
                    # 점 이름 (왼쪽, 간결하게)
                    short_name = f"P{i+1}"
                    cv2.putText(graph_frame, short_name,
                               (margin_side, y_pos + bar_height // 2 + 5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
                    
                    # 거리 값 (막대 안 또는 오른쪽)
                    dist_text = f"{distance:.2f}"
                    cv2.putText(graph_frame, dist_text,
                               (x_start + 5, y_pos + bar_height // 2 + 5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                    
                    # Z축 기준 조정 가이드 (막대 오른쪽)
                    if abs(z_diff_mm) > 0.1:
                        # +는 기준보다 높음 (올라가 있음) -> 내려야 함
                        # -는 기준보다 낮음 (내려가 있음) -> 올려야 함
                        if z_diff > 0:
                            guide_text = f"+{z_diff_mm:.2f}mm"
                            guide_color = (100, 200, 255)  # 주황색
                        else:
                            guide_text = f"{z_diff_mm:.2f}mm"
                            guide_color = (100, 255, 255)  # 노란색
                        
                        cv2.putText(graph_frame, guide_text,
                                   (x_start + bar_width_val + 5, y_pos + bar_height // 2 + 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, guide_color, 1)
                    else:
                        cv2.putText(graph_frame, "OK",
                                   (x_start + bar_width_val + 5, y_pos + bar_height // 2 + 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
            
            # Y축 스케일 표시 (하단)
            scale_y = graph_height - margin_bottom + 20
            cv2.putText(graph_frame, f"Scale: {y_min:.1f} ~ {y_max:.1f} cm",
                       (margin_side, scale_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
            
            # 평균선 표시 (세로선)
            avg_normalized = (avg_distance - y_min) / y_range
            avg_x = int(x_start + bar_max_width * avg_normalized)
            for y in range(margin_top, graph_height - margin_bottom, 15):
                cv2.line(graph_frame, (avg_x, y), (avg_x, y + 7), (0, 255, 0), 1)
            
        else:
            # 데이터가 없을 때
            cv2.putText(graph_frame, "Waiting...",
                       (graph_width // 2 - 50, graph_height // 2),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        
        # 프레임에 그래프 추가 (오른쪽)
        combined_frame = np.hstack([frame, graph_frame])
        return combined_frame
    
    return frame

def get_z_distance_input():
    """Z축 거리 입력 받기"""
    root = tk.Tk()
    root.withdraw()
    
    distance_cm = simpledialog.askfloat(
        "Z축 거리 설정",
        "카메라와 물체 사이의 Z축 거리를 입력하세요 (cm 단위):\n\n"
        "예: 3.2 (3.2cm)\n"
        "    5.0 (5cm)\n"
        "    10.0 (10cm)",
        initialvalue=3.2,
        minvalue=0.1,
        maxvalue=1000.0
    )
    
    root.destroy()
    
    if distance_cm is not None:
        return distance_cm / 100.0  # cm를 m로 변환
    return None

def calculate_3d_position_fixed_z(point_px, focal_length, fixed_z, image_width, image_height):
    """
    고정된 Z 거리로 3D 위치 계산
    
    Args:
        point_px: (x, y) 픽셀 좌표
        focal_length: 초점거리
        fixed_z: 고정된 Z축 거리 (미터)
        image_width, image_height: 이미지 크기
    
    Returns:
        (X, Y, Z, distance_3d)
    """
    cx = image_width / 2.0
    cy = image_height / 2.0
    
    # 픽셀 좌표를 정규화
    x_norm = (point_px[0] - cx) / focal_length
    y_norm = (point_px[1] - cy) / focal_length
    
    # 3D 위치 (Z는 고정)
    Z = fixed_z
    X = x_norm * Z
    Y = y_norm * Z
    
    # 카메라로부터의 유클리드 거리
    distance_3d = np.sqrt(X**2 + Y**2 + Z**2)
    
    return X, Y, Z, distance_3d

def calculate_alignment_metrics(points_3d):
    """
    3개 점의 정렬 상태를 측정
    
    Args:
        points_3d: [(X1, Y1, Z1), (X2, Y2, Z2), (X3, Y3, Z3)]
    
    Returns:
        dict: {
            'z_std': Z축 표준편차,
            'z_range': Z축 최대-최소 차이,
            'collinearity': 공선성 정도 (0에 가까울수록 일직선),
            'is_aligned': 정렬 여부 (bool)
        }
    """
    if len(points_3d) != 3:
        return None
    
    # Z축 분석
    z_values = [p[2] for p in points_3d]
    z_std = np.std(z_values)
    z_range = max(z_values) - min(z_values)
    
    # 공선성 측정 (3점이 일직선상에 있는지)
    # 벡터 AB와 AC를 구하고 외적(cross product)의 크기를 계산
    p1, p2, p3 = points_3d
    vec_AB = np.array([p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]])
    vec_AC = np.array([p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2]])
    
    # 외적의 크기 (0에 가까울수록 일직선)
    cross_product = np.cross(vec_AB, vec_AC)
    collinearity = np.linalg.norm(cross_product)
    
    # 정규화 (거리 기준)
    distance_AB = np.linalg.norm(vec_AB)
    distance_AC = np.linalg.norm(vec_AC)
    if distance_AB > 0 and distance_AC > 0:
        collinearity_normalized = collinearity / (distance_AB * distance_AC)
    else:
        collinearity_normalized = 0
    
    # 정렬 판정 기준
    # Z축 범위가 1mm 이내이고, 공선성이 낮으면 정렬된 것으로 판정
    is_aligned = (z_range < 0.001) and (collinearity_normalized < 0.05)
    
    return {
        'z_std': z_std,
        'z_range': z_range,
        'collinearity': collinearity,
        'collinearity_normalized': collinearity_normalized,
        'is_aligned': is_aligned
    }

def mouse_callback(event, x, y, flags, param):
    """마우스 클릭으로 3점 선택"""
    global selected_points, tracked_points, tracking_active, measurement_active, last_measurement_time
    
    if event == cv2.EVENT_LBUTTONDOWN and not tracking_active:
        if len(selected_points) < 3:
            selected_points.append((x, y))
            tracked_points.append((x, y))
            print(f"[INFO] {point_names[len(selected_points)-1]} 선택: ({x}, {y})")
            
            if len(selected_points) == 3:
                tracking_active = True
                measurement_active = True  # 자동으로 측정 시작
                last_measurement_time = time.time()
                print("[INFO] 3점 선택 완료! 실시간 추적 및 측정 자동 시작")

def track_points_optical_flow(prev_gray, curr_gray, points):
    """
    Optical Flow로 점 추적
    
    Args:
        prev_gray: 이전 프레임 (grayscale)
        curr_gray: 현재 프레임 (grayscale)
        points: 추적할 점들
    
    Returns:
        추적된 점들 또는 None
    """
    if points is None or len(points) == 0:
        return None
    
    # Lucas-Kanade Optical Flow 파라미터
    lk_params = dict(
        winSize=(15, 15),
        maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
    )
    
    # numpy array로 변환
    points_array = np.array(points, dtype=np.float32).reshape(-1, 1, 2)
    
    # Optical Flow 계산
    next_points, status, error = cv2.calcOpticalFlowPyrLK(
        prev_gray, curr_gray, points_array, None, **lk_params
    )
    
    if next_points is None:
        return None
    
    # 성공적으로 추적된 점들만 반환
    good_points = []
    for i, (st, pt) in enumerate(zip(status, next_points)):
        if st == 1:  # 추적 성공
            good_points.append(tuple(pt.ravel()))
        else:
            # 추적 실패 시 이전 위치 유지
            good_points.append(points[i])
    
    return good_points

def update_graph_data(distances_cm):
    """
    그래프 데이터 업데이트
    
    Args:
        distances_cm: [dist1, dist2, dist3] (cm 단위)
    """
    global graph_data_time, graph_data_p1, graph_data_p2, graph_data_p3
    global graph_start_time, graph_lock
    
    if graph_start_time is None:
        graph_start_time = time.time()
    
    elapsed_time = time.time() - graph_start_time
    
    with graph_lock:
        graph_data_time.append(elapsed_time)
        graph_data_p1.append(distances_cm[0])
        graph_data_p2.append(distances_cm[1])
        graph_data_p3.append(distances_cm[2])

def create_realtime_graph():
    """실시간 그래프 창 생성 및 업데이트"""
    global graph_enabled
    
    # matplotlib 설정
    try:
        plt.style.use('seaborn-v0_8-darkgrid')
    except:
        try:
            plt.style.use('seaborn-darkgrid')
        except:
            pass  # 기본 스타일 사용
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    line1, = ax.plot([], [], 'b-', linewidth=2, label='Point 1', marker='o', markersize=3)
    line2, = ax.plot([], [], 'g-', linewidth=2, label='Point 2', marker='s', markersize=3)
    line3, = ax.plot([], [], 'r-', linewidth=2, label='Point 3', marker='^', markersize=3)
    
    ax.set_xlabel('Time (seconds)', fontsize=12)
    ax.set_ylabel('Distance (cm)', fontsize=12)
    ax.set_title('Real-time Distance Tracking (3 Points)', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    
    def init():
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        return line1, line2, line3
    
    def update(frame):
        global graph_data_time, graph_data_p1, graph_data_p2, graph_data_p3
        
        with graph_lock:
            if len(graph_data_time) > 0:
                times = list(graph_data_time)
                p1_data = list(graph_data_p1)
                p2_data = list(graph_data_p2)
                p3_data = list(graph_data_p3)
                
                line1.set_data(times, p1_data)
                line2.set_data(times, p2_data)
                line3.set_data(times, p3_data)
                
                # 축 범위 자동 조정
                if len(times) > 0:
                    ax.set_xlim(max(0, times[-1] - 30), times[-1] + 2)  # 최근 30초
                    
                    all_distances = p1_data + p2_data + p3_data
                    if all_distances:
                        min_dist = min(all_distances)
                        max_dist = max(all_distances)
                        margin = (max_dist - min_dist) * 0.1 or 1
                        ax.set_ylim(min_dist - margin, max_dist + margin)
        
        return line1, line2, line3
    
    ani = FuncAnimation(fig, update, init_func=init, blit=True, interval=100, cache_frame_data=False)
    
    plt.tight_layout()
    plt.show()
    
    graph_enabled = False
    print("[INFO] 그래프 창이 닫혔습니다.")

def start_graph_thread():
    """그래프를 별도 스레드에서 실행 (Linux/Raspberry Pi에서 제한적 지원)"""
    global graph_enabled, graph_start_time
    global graph_data_time, graph_data_p1, graph_data_p2, graph_data_p3
    
    if graph_enabled:
        print("[WARNING] 그래프가 이미 실행 중입니다.")
        return
    
    # matplotlib 스레드 안전성 경고
    print("[WARNING] matplotlib 그래프는 메인 스레드 문제로 인해 제한적으로 작동할 수 있습니다.")
    print("[INFO] 대신 's' 키를 눌러 CSV 파일로 저장 후, 별도로 그래프를 그리는 것을 권장합니다.")
    print("[INFO] 그래프 기능을 시도합니다...")
    
    # 그래프 데이터 초기화
    graph_start_time = time.time()
    with graph_lock:
        graph_data_time.clear()
        graph_data_p1.clear()
        graph_data_p2.clear()
        graph_data_p3.clear()
    
    graph_enabled = True
    
    # 스레드 대신 별도 프로세스 사용 시도
    try:
        graph_thread = threading.Thread(target=create_realtime_graph, daemon=True)
        graph_thread.start()
        print("[INFO] 실시간 그래프 시작 (별도 창)")
    except Exception as e:
        print(f"[ERROR] 그래프 시작 실패: {e}")
        print("[INFO] CSV 저장 기능('s' 키)을 사용하세요.")
        graph_enabled = False

def save_measurement_log():
    """측정 기록을 CSV 파일로 저장"""
    if not measurement_log:
        print("\n" + "="*70)
        print("[INFO] 저장할 측정 데이터가 없습니다.")
        print("\n측정 데이터를 저장하는 방법:")
        print("  1. 화면에서 마우스로 3점을 클릭하세요")
        print("  2. 3점 선택 후 자동으로 1초마다 측정이 시작됩니다")
        print("  3. 측정이 진행되는 동안 's' 키를 눌러 저장하세요")
        print("  4. 또는 'm' 키로 측정을 시작/중지할 수 있습니다")
        print("="*70 + "\n")
        return
    
    filename = f"distance_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, 'w', encoding='utf-8') as f:
        # 헤더
        f.write("Timestamp,Point1_X(cm),Point1_Y(cm),Point1_Z(cm),Point1_Distance(cm),")
        f.write("Point2_X(cm),Point2_Y(cm),Point2_Z(cm),Point2_Distance(cm),")
        f.write("Point3_X(cm),Point3_Y(cm),Point3_Z(cm),Point3_Distance(cm),")
        f.write("Z_Range(mm),Collinearity,Aligned\n")
        
        # 데이터
        for entry in measurement_log:
            f.write(f"{entry['timestamp']},")
            for i in range(3):
                pt = entry['points'][i]
                f.write(f"{pt['X']:.2f},{pt['Y']:.2f},{pt['Z']:.2f},{pt['distance']:.2f},")
            
            # 정렬 정보 추가
            if 'alignment' in entry and entry['alignment'] is not None:
                align = entry['alignment']
                f.write(f"{align['z_range']*1000:.2f},")  # mm로 변환
                f.write(f"{align['collinearity_normalized']:.4f},")
                f.write(f"{'YES' if align['is_aligned'] else 'NO'}")
            else:
                f.write("N/A,N/A,N/A")
            
            f.write("\n")
    
    print("\n" + "="*70)
    print(f"✓ 측정 데이터 저장 완료!")
    print(f"  파일명: {filename}")
    print(f"  기록 수: {len(measurement_log)}개")
    print(f"  3점 거리 데이터 (X, Y, Z 좌표 및 정렬 상태 포함)")
    print("="*70 + "\n")

def main():
    global FIXED_Z_DISTANCE, focal_length
    global selected_points, tracked_points, tracking_active, freeze_points, last_freeze_update_time
    global measurement_active, last_measurement_time, measurement_log, show_bar_graph, bar_graph_position
    
    # Z축 거리 설정
    print("[INFO] Z축 거리 설정...")
    z_input = get_z_distance_input()
    
    if z_input is not None:
        FIXED_Z_DISTANCE = z_input
        print(f"[INFO] Z축 거리 설정: {FIXED_Z_DISTANCE*100:.1f}cm ({FIXED_Z_DISTANCE:.4f}m)")
    else:
        print(f"[INFO] 기본값 사용: {FIXED_Z_DISTANCE*100:.1f}cm")
    
    print("[INFO] 카메라 초기화 중... (Raspberry Pi 4 + Arducam IMX519)")
    print("[주의] 고정 Z는 실제 깊이 측정값이 아니라 입력한 가정값입니다.")
    
    # 카메라 초기화
    picam = None
    cap = None
    
    # Raspberry Pi 카메라 시도 (picamera2)
    if USE_PICAMERA2:
        try:
            print("[INFO] Raspberry Pi 카메라(picamera2) 초기화 중...")
            
            available_cameras = Picamera2.global_camera_info()
            print(f"[INFO] CSI 카메라 목록: {available_cameras}")
            if not available_cameras:
                raise RuntimeError("CSI 카메라가 감지되지 않았습니다. IMX519 드라이버와 케이블을 확인하세요.")
            if CAMERA_INDEX >= len(available_cameras):
                raise RuntimeError(f"CAMERA_INDEX={CAMERA_INDEX} 범위 초과")
            model = str(available_cameras[CAMERA_INDEX].get('Model', '')).lower()
            if 'imx519' not in model:
                print(f"[WARNING] 감지된 센서가 IMX519가 아닐 수 있습니다: {model}")
            picam = Picamera2(CAMERA_INDEX)
            
            # 비디오 설정 생성 (BGR888 포맷으로 OpenCV와 호환)
            config = picam.create_video_configuration(
                main={"size": CAMERA_RESOLUTION, "format": "BGR888"},
                controls={"FrameRate": CAMERA_FPS}
            )
            picam.configure(config)
            
            # 카메라 시작
            picam.start()
            
            print("[INFO] 카메라 워밍업 중... (2초)")
            time.sleep(2)  # 카메라 워밍업
            
            # 테스트 프레임 캡처
            test_frame = picam.capture_array()
            
            if test_frame is not None and test_frame.size > 0:
                h, w = test_frame.shape[:2]
                print(f"[SUCCESS] Raspberry Pi 카메라 초기화 완료!")
                print(f"  해상도: {w}x{h}")
                print(f"  포맷: BGR888")
                print(f"  라이브러리: picamera2")
            else:
                print("[ERROR] 테스트 프레임 캡처 실패")
                picam.stop()
                picam.close()
                picam = None
                
        except Exception as e:
            print(f"[ERROR] Raspberry Pi 카메라 초기화 실패: {e}")
            print(f"  오류 타입: {type(e).__name__}")
            print("\n해결 방법:")
            print("  1. 카메라 케이블 연결 확인")
            print("  2. libcamera가 설치되어 있는지 확인:")
            print("     sudo apt install -y python3-picamera2")
            print("  3. 카메라가 감지되는지 확인:")
            print("     libcamera-hello --list-cameras")
            print("  4. 재부팅: sudo reboot")
            
            if picam is not None:
                try:
                    picam.stop()
                    picam.close()
                except:
                    pass
            picam = None
            print("[INFO] USB 카메라로 자동 전환합니다...\n")
    
    # USB 카메라 사용 (picamera가 없거나 실패한 경우)
    if picam is None:
        print("[INFO] USB 카메라 사용")
        cap = cv2.VideoCapture(SOURCE)
        if not cap.isOpened():
            print("[ERROR] USB 카메라를 열 수 없습니다!")
            print("[INFO] 다른 카메라 인덱스 시도 중...")
            # 다른 카메라 인덱스 시도
            for i in range(1, 4):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    print(f"[INFO] 카메라 인덱스 {i}에서 카메라 발견!")
                    break
            
            if not cap.isOpened():
                print("[ERROR] 사용 가능한 카메라를 찾을 수 없습니다!")
                print("\n해결 방법:")
                print("1. Raspberry Pi 카메라를 사용하려면:")
                print("   sudo raspi-config -> Interface Options -> Camera -> Enable")
                print("2. USB 카메라가 제대로 연결되었는지 확인하세요:")
                print("   ls /dev/video*")
                return
        
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])
        
        for _ in range(5):
            cap.read()
            time.sleep(0.1)
        
        ret, test_frame = cap.read()
        if not ret or test_frame is None:
            print("[ERROR] 카메라에서 프레임을 읽을 수 없습니다!")
            cap.release()
            return
        
        print(f"[INFO] USB 카메라 초기화 성공! 해상도: {test_frame.shape[1]}x{test_frame.shape[0]}")
    
    # 창 생성 (막대그래프를 위한 공간 추가)
    window_name = "Fixed Z-Axis Distance Tracker"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    if show_bar_graph and bar_graph_position == 'right':
        cv2.resizeWindow(window_name, 1630, 720)  # 1280 + 350 (오른쪽 그래프)
    elif show_bar_graph and bar_graph_position == 'bottom':
        cv2.resizeWindow(window_name, 1280, 1000)  # 720 + 280 (하단 그래프)
    else:
        cv2.resizeWindow(window_name, 1280, 720)
    cv2.setMouseCallback(window_name, mouse_callback)
    
    print("\n" + "="*70)
    print(" Fixed Z-Axis Distance Tracker with Alignment Detection")
    print("="*70)
    print(f"\n설정: Z축 고정 거리 = {FIXED_Z_DISTANCE*100:.1f}cm")
    print("\n사용법:")
    print("  1. 마우스로 3점을 클릭하여 선택")
    print("  2. 자동으로 실시간 추적 및 측정 시작 (1초마다 자동 기록)")
    print("  3. 점이 흔들리면 'F' 키를 눌러 안정화 모드! ⭐")
    print("     (1초마다 점 위치를 업데이트하여 흔들림 없이 높이 변화 반영)")
    print("  4. 오른쪽 막대그래프에서 평형 조정 가이드를 확인하세요")
    print("  5. 화면 오른쪽 상단에서 3점의 정렬 상태를 확인할 수 있습니다")
    print("  6. 's' 키를 눌러 측정 데이터를 CSV 파일로 저장")
    print("\n오른쪽 막대그래프 기능:")
    print("  - 고정 스케일: 평균값 ±20% 범위로 실제 차이를 정확히 표시")
    print("  - Z-ref: 3점의 평균 Z축 높이 (기준면)")
    print("  - Z축 기준 차이: +값(기준보다 높음), -값(기준보다 낮음)")
    print("    예) Z-ref: 3.20cm일 때")
    print("        P1: 3.47cm → +0.27cm (2.7mm 높음)")
    print("        P2: 3.00cm → -0.20cm (2.0mm 낮음)")
    print("  - 정렬 완료: 막대 테두리가 녹색으로 변경 + 'OK' 표시")
    print("  - Max Z-diff: 기준면 대비 최대 높이 차이 (1mm 이하 목표)")
    print("\n단축키:")
    print("  'f' - 점 위치 안정화 ON/OFF (1초마다 업데이트, 흔들림 제거!) ⭐")
    print("  'm' - 측정 시작/중지 (기본: 자동 시작)")
    print("  's' - 측정 데이터를 CSV 파일로 저장 (중요!)")
    print("  'b' - 실시간 막대그래프 ON/OFF (기본: ON)")
    print("  'g' - 선 그래프 표시 (3점의 거리 vs 시간, 제한적)")
    print("  'r' - 점 선택 초기화 (다시 선택)")
    print("  'z' - Z축 거리 재설정")
    print("  'q' - 종료 (자동으로 데이터 저장)")
    print("="*70)
    print("\n💡 평형 조정 방법:")
    print("  1. 오른쪽 막대그래프에서 Z축 기준 차이 확인")
    print("     +0.27mm → 기준보다 2.7mm 높음 (내려야 함)")
    print("     -0.20mm → 기준보다 2.0mm 낮음 (올려야 함)")
    print("  2. 표시된 mm 값만큼 모터 위치 조정")
    print("  3. 막대 테두리가 녹색으로 변하고 'OK'가 표시되면 완료!")
    print("  4. 'Max Z-diff'가 1.0mm 이하가 되도록 조정하세요")
    print("="*70 + "\n")
    
    # EMA 필터 (부드러운 출력)
    alpha = 0.3
    ema_distances = [None, None, None]
    
    # Optical Flow용 이전 프레임
    prev_gray = None
    freeze_reference_gray = None  # 안정화 모드에서는 마지막 업데이트 시점과 비교
    
    h_img, w_img = test_frame.shape[:2]
    
    # picamera2는 스트리밍 설정이 필요 없음 (이미 start()로 시작됨)
    if picam is not None:
        print("[INFO] Raspberry Pi 카메라 스트리밍 준비 완료")
    
    while True:
        # 프레임 읽기
        if picam is not None:
            try:
                # picamera2로 프레임 캡처 (BGR888 포맷)
                frame = picam.capture_array()
                
                if frame is None or frame.size == 0:
                    time.sleep(0.01)
                    continue
            except Exception as e:
                print(f"[ERROR] 프레임 읽기 오류: {e}")
                time.sleep(0.1)
                continue
        else:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.1)
                continue
        
        h_img, w_img = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 현재 시간
        current_time = time.time()
        
        # 점 추적 (Optical Flow)
        if tracking_active and prev_gray is not None:
            if not freeze_points:
                # 실시간 추적: 이전 프레임과 비교
                new_points = track_points_optical_flow(prev_gray, gray, tracked_points)
                if new_points is not None:
                    tracked_points = new_points
            elif current_time - last_freeze_update_time >= 1.0:
                # 안정화 모드: 마지막 위치 갱신 시점의 프레임과 비교
                reference = freeze_reference_gray if freeze_reference_gray is not None else prev_gray
                new_points = track_points_optical_flow(reference, gray, tracked_points)
                if new_points is not None:
                    tracked_points = new_points
                    selected_points = tracked_points.copy()
                freeze_reference_gray = gray.copy()
                last_freeze_update_time = current_time

        prev_gray = gray.copy()
        
        # 상태 표시
        if not tracking_active:
            remaining = 3 - len(selected_points)
            cv2.putText(frame, f"Click to select points ({remaining} remaining)", 
                       (20, 30), FONT, 0.8, (0, 255, 255), 2)
            cv2.putText(frame, f"Z-axis distance: {FIXED_Z_DISTANCE*100:.1f}cm (fixed)", 
                       (20, 60), FONT, 0.6, (255, 255, 255), 2)
        else:
            # 추적 모드에 따라 메시지 변경
            if freeze_points:
                # 다음 업데이트까지 남은 시간 계산
                time_until_update = max(0, 1.0 - (current_time - last_freeze_update_time))
                tracking_msg = f"STABILIZED - Updates every 1 sec (Next: {time_until_update:.1f}s)"
                tracking_color = (0, 255, 255)  # 노란색
            else:
                tracking_msg = "Tracking active - Move camera left/right"
                tracking_color = (0, 255, 0)  # 녹색
            
            cv2.putText(frame, tracking_msg, 
                       (20, 30), FONT, 0.7, tracking_color, 2)
            cv2.putText(frame, f"Z-axis: {FIXED_Z_DISTANCE*100:.1f}cm (fixed)", 
                       (20, 60), FONT, 0.6, (255, 255, 255), 2)
            
            # 측정 상태 표시
            if measurement_active:
                cv2.putText(frame, f"[AUTO MEASURING] Recording every 1 sec ({len(measurement_log)} records)", 
                           (20, 90), FONT, 0.7, (0, 255, 0), 2)
                # 깜박이는 효과 (녹색)
                if int(current_time * 2) % 2 == 0:
                    cv2.circle(frame, (w_img - 30, 30), 15, (0, 255, 0), -1)
                    cv2.putText(frame, "REC", (w_img - 80, 40), FONT, 0.6, (0, 255, 0), 2)
                # 저장 안내
                cv2.putText(frame, "[Press 'S' to save data to CSV]", 
                           (20, 120), FONT, 0.6, (0, 255, 255), 2)
            else:
                cv2.putText(frame, "[Paused - Press 'M' to resume measuring]", 
                           (20, 90), FONT, 0.6, (0, 165, 255), 2)
            
            # 막대그래프 상태 표시
            bar_status = "ON" if show_bar_graph else "OFF"
            bar_color = (0, 255, 0) if show_bar_graph else (100, 100, 100)
            cv2.putText(frame, f"[Bar Graph: {bar_status}]", 
                       (20, 150), FONT, 0.5, bar_color, 1)
            
            # 안정화 모드 상태 표시
            if freeze_points:
                stabilize_text = "[Stabilized Mode: ON - 1sec updates]"
                cv2.putText(frame, stabilize_text, 
                           (20, 175), FONT, 0.5, (0, 255, 255), 2)
                # 깜박이는 인디케이터
                if int(current_time * 2) % 2 == 0:
                    cv2.circle(frame, (w_img - 80, 100), 8, (0, 255, 255), -1)
            
            # 선 그래프 상태 표시
            if graph_enabled:
                cv2.putText(frame, "[Line Graph: ON]", 
                           (20, 200), FONT, 0.5, (0, 255, 255), 1)
        
        # 선택된/추적 중인 점들 표시 및 거리 계산
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        
        # 현재 프레임의 측정 데이터 저장용
        current_measurements = []
        points_3d = []  # 정렬 측정용 3D 좌표 리스트
        
        for i in range(len(tracked_points)):
            point = tracked_points[i]
            color = colors[i]
            
            # 점 표시 (안정화 모드에서 업데이트 직후에는 깜박임 효과)
            if freeze_points and (current_time - last_freeze_update_time) < 0.2:
                # 업데이트 직후 0.2초간 밝게 표시
                cv2.circle(frame, (int(point[0]), int(point[1])), 15, (255, 255, 255), -1)
                cv2.circle(frame, (int(point[0]), int(point[1])), 20, (255, 255, 255), 3)
            else:
                # 일반 표시
                cv2.circle(frame, (int(point[0]), int(point[1])), 10, color, -1)
                cv2.circle(frame, (int(point[0]), int(point[1])), 15, color, 2)
            
            cv2.putText(frame, point_names[i], 
                       (int(point[0]) + 20, int(point[1]) - 15), 
                       FONT, 0.6, color, 2)
            
            # 거리 계산
            result = calculate_3d_position_fixed_z(
                point, focal_length, FIXED_Z_DISTANCE, w_img, h_img
            )
            
            if result is not None:
                X, Y, Z, distance_3d = result
                
                # EMA 필터 적용
                if ema_distances[i] is None:
                    ema_distances[i] = distance_3d
                else:
                    ema_distances[i] = alpha * distance_3d + (1 - alpha) * ema_distances[i]
                
                # 3D 좌표 저장 (정렬 측정용)
                points_3d.append((X, Y, Z))
                
                # 측정 데이터 저장
                current_measurements.append({
                    'X': X * 100,  # m → cm
                    'Y': Y * 100,
                    'Z': Z * 100,
                    'distance': ema_distances[i] * 100
                })
                
                # 화면에 간결하게 표시 (오른쪽 그래프가 자세한 정보 표시)
                y_offset = 180 + i * 80  # 간격 축소
                cv2.putText(frame, f"{point_names[i]}: {ema_distances[i]*100:.2f}cm", 
                           (20, y_offset), FONT, 0.6, color, 2)
                cv2.putText(frame, f"XYZ: ({X*100:+.1f}, {Y*100:+.1f}, {Z*100:.1f})", 
                           (20, y_offset + 25), FONT, 0.45, color, 1)
        
        # 그래프 데이터 업데이트 (그래프가 활성화된 경우)
        if graph_enabled and len(tracked_points) == 3 and len(ema_distances) == 3:
            if all(d is not None for d in ema_distances):
                distances_cm = [d * 100 for d in ema_distances]  # m → cm
                update_graph_data(distances_cm)
        
        # 정렬 상태 측정 (검은 박스 제거, 오른쪽 그래프에만 표시)
        
        # 1초마다 측정 기록
        if measurement_active and tracking_active and len(current_measurements) == 3:
            if current_time - last_measurement_time >= 1.0:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 정렬 정보도 함께 저장
                alignment_info = calculate_alignment_metrics(points_3d) if len(points_3d) == 3 else None
                
                measurement_log.append({
                    'timestamp': timestamp,
                    'points': current_measurements,
                    'alignment': alignment_info
                })
                last_measurement_time = current_time
                
                # 콘솔 출력 (개선된 포맷)
                align_status = "✓ ALIGNED" if (alignment_info and alignment_info['is_aligned']) else "✗ NOT ALIGNED"
                z_range_mm = alignment_info['z_range'] * 1000 if alignment_info else 0
                
                print(f"\n[기록 #{len(measurement_log)}] {timestamp}")
                print(f"  Point 1: {current_measurements[0]['distance']:.2f}cm")
                print(f"  Point 2: {current_measurements[1]['distance']:.2f}cm")
                print(f"  Point 3: {current_measurements[2]['distance']:.2f}cm")
                print(f"  Z-range: {z_range_mm:.2f}mm | Status: {align_status}")
                print(f"  (총 {len(measurement_log)}개 측정 완료, 's' 키로 저장)")
        
        # 실시간 막대그래프 추가
        if show_bar_graph and tracking_active and len(ema_distances) == 3:
            if all(d is not None for d in ema_distances):
                distances_cm = [d * 100 for d in ema_distances]  # m → cm
                # Z값 추출 (points_3d에서)
                z_values_cm = [p[2] * 100 for p in points_3d] if len(points_3d) == 3 else None
                frame = draw_realtime_bar_graph(frame, distances_cm, point_names, colors, 
                                              position=bar_graph_position, z_values_cm=z_values_cm)
        
        # 화면 표시
        cv2.imshow(window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            # 종료 시 측정 중이었다면 자동 저장
            if measurement_log:
                print(f"\n[INFO] 종료 전 측정 데이터 자동 저장 중...")
                save_measurement_log()
            break
        elif key == ord('m') or key == ord('M'):
            # 측정 시작/중지
            if tracking_active:
                measurement_active = not measurement_active
                if measurement_active:
                    last_measurement_time = current_time
                    print("\n" + "="*70)
                    print("[INFO] ✓ 측정 재개 - 1초마다 자동 기록 중...")
                    print("="*70)
                else:
                    print("\n" + "="*70)
                    print(f"[INFO] ⏸ 측정 일시정지 (현재 {len(measurement_log)}개 기록)")
                    print("      다시 'm' 키를 누르면 측정이 재개됩니다")
                    print("="*70)
            else:
                print("[WARNING] 먼저 3점을 선택해주세요!")
        elif key == ord('s') or key == ord('S'):
            # 측정 데이터 저장
            save_measurement_log()
        elif key == ord('b') or key == ord('B'):
            # 막대그래프 ON/OFF
            show_bar_graph = not show_bar_graph
            status = "ON" if show_bar_graph else "OFF"
            print(f"\n[INFO] 📊 실시간 막대그래프: {status}")
        elif key == ord('g') or key == ord('G'):
            # 실시간 선 그래프 시작
            if tracking_active:
                start_graph_thread()
            else:
                print("[WARNING] 먼저 3점을 선택해주세요!")
        elif key == ord('r'):
            # 초기화
            selected_points = []
            tracked_points = []
            tracking_active = False
            measurement_active = False
            freeze_points = False
            last_freeze_update_time = 0
            ema_distances = [None, None, None]
            prev_gray = None
            freeze_reference_gray = None
            print("\n" + "="*70)
            print("[INFO] 🔄 점 선택 초기화 완료")
            print("      다시 마우스로 3점을 클릭하세요")
            print("="*70)
        elif key == ord('z'):
            # Z축 거리 재설정
            z_input = get_z_distance_input()
            if z_input is not None:
                FIXED_Z_DISTANCE = z_input
                print(f"[INFO] Z축 거리 변경: {FIXED_Z_DISTANCE*100:.1f}cm")
                # 거리 재계산을 위해 EMA 초기화
                ema_distances = [None, None, None]
        elif key == ord('f') or key == ord('F'):
            # 점 안정화 모드 토글
            if tracking_active:
                freeze_points = not freeze_points
                if freeze_points:
                    # 안정화 모드로 전환: 1초마다 업데이트
                    selected_points = tracked_points.copy()
                    last_freeze_update_time = current_time
                    freeze_reference_gray = gray.copy()
                    print("\n" + "="*70)
                    print("[INFO] 📌 점 위치 안정화 ON")
                    print("      1초마다 점 위치를 업데이트합니다 (흔들림 없음)")
                    print("      실시간 추적보다 안정적이며, 높이 변화는 반영됩니다")
                    print("      'F' 키를 다시 누르면 실시간 추적 모드로 전환됩니다")
                    print("="*70)
                else:
                    print("\n" + "="*70)
                    freeze_reference_gray = None
                    print("[INFO] 🔓 점 위치 안정화 OFF")
                    print("      실시간 Optical Flow 추적을 재개합니다")
                    print("="*70)
            else:
                print("[WARNING] 먼저 3점을 선택해주세요!")
    
    # 리소스 정리
    if picam is not None:
        try:
            picam.stop()
            picam.close()
            print("[INFO] Raspberry Pi 카메라 종료")
        except:
            pass
    if cap is not None:
        cap.release()
        print("[INFO] USB 카메라 종료")
    cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] 프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n[ERROR] 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cv2.destroyAllWindows()
        print("[INFO] 프로그램 종료")
