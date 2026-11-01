#!/usr/bin/env python3
"""Raspberry Pi 4 + Arducam IMX519 autofocus diagnostic.
Run with the system Python that provides Picamera2.
"""
import time
from datetime import datetime
import cv2
from picamera2 import Picamera2

WIDTH, HEIGHT = 1280, 720


def main():
    picam = Picamera2()
    print('Detected:', Picamera2.global_camera_info())
    config = picam.create_video_configuration(main={'size': (WIDTH, HEIGHT), 'format': 'BGR888'}, controls={'FrameRate': 30})
    picam.configure(config)
    available = picam.camera_controls
    for key in ('AfMode', 'AfTrigger', 'AfRange', 'LensPosition', 'AfMetering', 'AfWindows'):
        print(f'{key}: {available.get(key, "NOT AVAILABLE")}')
    has_af = 'AfMode' in available
    has_lens = 'LensPosition' in available
    lo, hi, default = available.get('LensPosition', (0.0, 10.0, 0.0))
    lens_pos = float(default)
    mode = 'NOT SUPPORTED'
    picam.start()
    time.sleep(1)

    def set_mode(name):
        nonlocal mode
        if not has_af:
            print('[WARN] AfMode is not advertised. Lens/driver may not support AF.')
            return
        try:
            picam.set_controls({'AfMode': {'manual': 0, 'auto': 1, 'continuous': 2}[name]})
            mode = name.upper()
            print('AF mode:', mode)
        except Exception as exc:
            print('[ERROR] Failed to set AF mode:', exc)

    def single_af():
        nonlocal mode
        if not has_af or 'AfTrigger' not in available:
            print('[WARN] Single AF not supported')
            return
        set_mode('auto')
        try:
            picam.set_controls({'AfTrigger': 0})  # Start
            print('Single autofocus triggered')
        except Exception as exc:
            print('[ERROR] AF trigger:', exc)

    def manual(delta):
        nonlocal lens_pos, mode
        if not has_lens or not has_af:
            print('[WARN] Manual focus controls not available')
            return
        lens_pos = min(float(hi), max(float(lo), lens_pos + delta))
        try:
            picam.set_controls({'AfMode': 0, 'LensPosition': lens_pos})
            mode = 'MANUAL'
            print(f'Manual focus: {lens_pos:.2f} (available {lo}..{hi})')
        except Exception as exc:
            print('[ERROR] Manual lens positioning:', exc)

    if has_af:
        set_mode('continuous')
    print('Keys: c=continuous AF, a=single AF, m=manual, +/-=manual focus, s=save, q=quit')
    print('IMPORTANT: Manual focus numbers are dioptres, not millimetres of acrylic movement.')
    cv2.namedWindow('IMX519 Focus Test', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('IMX519 Focus Test', WIDTH, HEIGHT)
    try:
        frame_count = 0
        while True:
            frame = picam.capture_array()
            if frame is None:
                continue
            frame_count += 1
            metadata = picam.capture_metadata() if frame_count % 8 == 0 else metadata if frame_count > 1 else {}
            h, w = frame.shape[:2]
            # Center ROI for a rough relative sharpness score (not an absolute focus metric).
            side = min(h, w) // 3
            x0, y0 = (w-side)//2, (h-side)//2
            roi = frame[y0:y0+side, x0:x0+side]
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray_roi, cv2.CV_64F).var()
            cv2.rectangle(frame, (x0, y0), (x0+side, y0+side), (0, 255, 255), 2)
            lines = [f'Focus mode: {mode}',
                     f'AF state: {metadata.get("AfState", "N/A")}',
                     f'Lens position: {metadata.get("LensPosition", "N/A")}',
                     f'Center sharpness score: {sharpness:.1f}',
                     'C continuous | A single AF | M manual | +/- focus | S save | Q quit']
            for i, line in enumerate(lines):
                cv2.putText(frame, line, (15, 30 + i*27), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(frame, line, (15, 30 + i*27), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (240, 240, 240), 1, cv2.LINE_AA)
            cv2.imshow('IMX519 Focus Test', frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            if key == ord('c'):
                set_mode('continuous')
            elif key == ord('a'):
                single_af()
            elif key == ord('m'):
                manual(0)
            elif key in (ord('+'), ord('=')):
                manual(0.5)
            elif key in (ord('-'), ord('_')):
                manual(-0.5)
            elif key == ord('s'):
                filename = f'imx519_focus_{datetime.now():%Y%m%d_%H%M%S}.jpg'
                cv2.imwrite(filename, frame)
                print('Saved:', filename)
    finally:
        picam.stop()
        picam.close()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
