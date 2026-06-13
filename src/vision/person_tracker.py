from __future__ import annotations
import threading
import time
from dataclasses import dataclass
import cv2
import numpy

Rect = tuple[int, int, int, int]  # (x, y, width, height) in frame pixel coordinates


@dataclass(frozen=True)
class TrackedPersonSnapshot:
    """Immutable, thread-safe snapshot of a tracked person."""
    id: int
    rect: Rect
    confidence: float


def _create_tracker():
    # MOSSE is much cheaper per-frame than KCF (roughly 5x), which matters
    # because every tracked person gets its own tracker updated each frame.
    if hasattr(cv2, "legacy"):
        if hasattr(cv2.legacy, "TrackerMOSSE_create"):
            return cv2.legacy.TrackerMOSSE_create()
        return cv2.legacy.TrackerKCF_create()
    if hasattr(cv2, "TrackerMOSSE_create"):
        return cv2.TrackerMOSSE_create()
    return cv2.TrackerKCF_create()


def _iou(box_a: Rect, box_b: Rect) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax + aw, bx + bw)
    inter_y2 = min(ay + ah, by + bh)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0
    union_area = aw * ah + bw * bh - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


class _TrackedPerson:
    def __init__(self, person_id: int, rect: Rect, confidence: float):
        self.id = person_id
        self.rect = rect
        self.confidence = confidence
        self.tracker = None
        self.misses = 0


class PersonTracker:
    """Detects and tracks people across video frames.

    Person detection is run on a background thread at a low rate. Between
    detections, every tracked person's bounding box is refreshed each frame
    via a lightweight OpenCV tracker so rectangles move smoothly. Each
    recognized person is represented by a stable instance (id) whose
    coordinates are updated as long as the same person keeps being tracked.
    """

    def __init__(
        self,
        detection_interval: float = 0.5,
        iou_threshold: float = 0.3,
        max_misses: int = 5,
    ):
        self._detection_interval = detection_interval
        self._iou_threshold = iou_threshold
        self._max_misses = max_misses
        self._people: list[_TrackedPerson] = []
        self._lock = threading.Lock()
        self._next_id = 1
        self._detector = None
        self._detect_thread: threading.Thread | None = None
        self._last_detect_start = 0.0
        self._stopped = False

    def cleanup(self):
        self._stopped = True
        with self._lock:
            self._people = []

    def get_people(self) -> list[TrackedPersonSnapshot]:
        """Return a thread-safe snapshot of currently tracked people."""
        with self._lock:
            return [
                TrackedPersonSnapshot(person.id, person.rect, person.confidence)
                for person in self._people
            ]

    def process_frame(self, frame: numpy.ndarray) -> None:
        """Update tracked people for a new frame and kick off detection if due."""
        if self._stopped or frame is None:
            return

        with self._lock:
            for person in self._people:
                if person.tracker is None:
                    continue
                ok, box = person.tracker.update(frame)
                if ok:
                    x, y, w, h = box
                    person.rect = (int(x), int(y), int(w), int(h))

        self._maybe_start_detection(frame)

    def _maybe_start_detection(self, frame: numpy.ndarray) -> None:
        if self._detect_thread is not None and self._detect_thread.is_alive():
            return
        now = time.monotonic()
        if now - self._last_detect_start < self._detection_interval:
            return
        self._last_detect_start = now
        frame_copy = numpy.ascontiguousarray(frame)
        self._detect_thread = threading.Thread(
            target=self._run_detection, args=(frame_copy,), daemon=True
        )
        self._detect_thread.start()

    def _run_detection(self, frame: numpy.ndarray) -> None:
        try:
            if self._detector is None:
                from .person_detector import PersonDetector
                self._detector = PersonDetector()
            detections = self._detector.detect(frame)
        except Exception:
            return
        if self._stopped:
            return
        self._apply_detections(frame, detections)

    def _apply_detections(
        self, frame: numpy.ndarray, detections: list[tuple[int, int, int, int, float]]
    ) -> None:
        with self._lock:
            matched_people: set[int] = set()
            matched_detections: set[int] = set()

            # Match each detection to the best overlapping tracked person.
            for det_idx, (x, y, w, h, _confidence) in enumerate(detections):
                best_iou = 0.0
                best_person: _TrackedPerson | None = None
                for person in self._people:
                    if person.id in matched_people:
                        continue
                    score = _iou(person.rect, (x, y, w, h))
                    if score > best_iou:
                        best_iou = score
                        best_person = person
                if best_person is not None and best_iou >= self._iou_threshold:
                    self._reinit_person(best_person, frame, (x, y, w, h), detections[det_idx][4])
                    matched_people.add(best_person.id)
                    matched_detections.add(det_idx)

            # Unmatched detections are newly recognized people.
            for det_idx, (x, y, w, h, confidence) in enumerate(detections):
                if det_idx in matched_detections:
                    continue
                person = _TrackedPerson(self._next_id, (x, y, w, h), confidence)
                self._next_id += 1
                self._reinit_person(person, frame, (x, y, w, h), confidence)
                self._people.append(person)

            # People not seen in this detection pass age out after enough misses.
            remaining = []
            for person in self._people:
                if person.id not in matched_people:
                    person.misses += 1
                    if person.misses > self._max_misses:
                        continue
                remaining.append(person)
            self._people = remaining

    @staticmethod
    def _reinit_person(person: _TrackedPerson, frame: numpy.ndarray, rect: Rect, confidence: float) -> None:
        person.rect = rect
        person.confidence = confidence
        person.misses = 0
        try:
            tracker = _create_tracker()
            tracker.init(frame, rect)
            person.tracker = tracker
        except Exception:
            person.tracker = None
