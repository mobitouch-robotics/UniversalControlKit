from __future__ import annotations
import pathlib
import sys
import cv2
import numpy

# Index of the "person" class in the VOC0712 label set used by MobileNet-SSD.
_PERSON_CLASS_ID = 15
_INPUT_SIZE = 300


class PersonDetector:
    """Detects people in video frames using a MobileNet-SSD model."""

    def __init__(self, confidence_threshold: float = 0.5):
        self.confidence_threshold = confidence_threshold
        self._net = cv2.dnn.readNetFromCaffe(
            str(self._model_path("MobileNetSSD_deploy.prototxt")),
            str(self._model_path("MobileNetSSD_deploy.caffemodel")),
        )

    @staticmethod
    def _model_path(filename: str) -> pathlib.Path:
        candidates = [
            pathlib.Path(__file__).with_name("models") / filename,
            pathlib.Path.cwd() / "src" / "vision" / "models" / filename,
        ]

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(pathlib.Path(meipass) / "src" / "vision" / "models" / filename)

        exe_path = pathlib.Path(sys.executable).resolve()
        candidates.append(exe_path.parent.parent / "Resources" / "src" / "vision" / "models" / filename)

        for candidate in candidates:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(f"Person detection model file not found: {filename}")

    def detect(self, frame: numpy.ndarray) -> list[tuple[int, int, int, int, float]]:
        """Detect people in an RGB frame.

        Returns a list of (x, y, width, height, confidence) boxes in frame
        pixel coordinates, one per detected person.
        """
        height, width = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            frame,
            scalefactor=1.0 / 127.5,
            size=(_INPUT_SIZE, _INPUT_SIZE),
            mean=(127.5, 127.5, 127.5),
            swapRB=True,  # frame is RGB, model expects BGR
        )
        self._net.setInput(blob)
        detections = self._net.forward()

        boxes = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence < self.confidence_threshold:
                continue
            class_id = int(detections[0, 0, i, 1])
            if class_id != _PERSON_CLASS_ID:
                continue
            box = detections[0, 0, i, 3:7] * numpy.array([width, height, width, height])
            x1, y1, x2, y2 = box.astype(int)
            x1 = max(0, min(width, x1))
            y1 = max(0, min(height, y1))
            x2 = max(0, min(width, x2))
            y2 = max(0, min(height, y2))
            if x2 <= x1 or y2 <= y1:
                continue
            boxes.append((int(x1), int(y1), int(x2 - x1), int(y2 - y1), confidence))
        return boxes
