"""
backend/camera.py

Threaded non-blocking camera capture [UPGRADE 6, FIX H4].
Guarantees that read() always returns the latest hardware frame and discards stale frames,
preventing latency buildup on video streams.
"""

from __future__ import annotations

import logging
import threading
import time

import cv2
import numpy as np

logger = logging.getLogger("Camera")


class Camera:
    """
    [UPGRADE 6] Threaded camera reader.
    Guarantees that read() always returns the newest frame and drops stale frames.
    """

    def __init__(self, camera_index: int = 0) -> None:
        # [FIX H4] CAP_DSHOW on Windows + buffer size 1 for zero capture lag
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(camera_index)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.frame: np.ndarray | None = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()
        logger.info(f"Threaded camera initialized on device {camera_index}")

    def _capture_worker(self) -> None:
        while not self.stop_event.is_set():
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame
            else:
                time.sleep(0.01)

    def read(self) -> np.ndarray | None:
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def release(self) -> None:
        self.stop_event.set()
        time.sleep(0.05)
        if self.cap.isOpened():
            self.cap.release()
        logger.info("Camera capture thread terminated and hardware released")

