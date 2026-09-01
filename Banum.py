from picamera2 import Picamera2
from libcamera import controls
import cv2
import time

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={
        "size": (640, 480),
        "format": "RGB888"
    }
)

picam2.configure(config)

# 연속 자동초점
picam2.set_controls({
    "AfMode": controls.AfModeEnum.Continuous
})

picam2.start()

time.sleep(2)

while True:
    frame = picam2.capture_array()

    frame = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2BGR
    )

    cv2.putText(
        frame,
        "Continuous Autofocus",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.imshow("Autofocus Test", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cv2.destroyAllWindows()
picam2.stop()
