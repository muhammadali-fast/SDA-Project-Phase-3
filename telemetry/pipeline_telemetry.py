import time
import threading
from multiprocessing import Queue
from typing import Any, Dict, List

from utils.interfaces import TelemetrySubject, TelemetryObserver


class PipelineTelemetry(TelemetrySubject):

    def __init__(self, raw_queue: Queue, processed_queue: Queue,
                 max_size: int, poll_interval: float = 0.5) -> None:
        self.raw_queue       = raw_queue
        self.processed_queue = processed_queue
        self.max_size        = max_size
        self.poll_interval   = poll_interval
        self.observers: List[TelemetryObserver] = []
        self.running         = False
        self.thread          = None

    def attach(self, observer: TelemetryObserver) -> None:
        if observer not in self.observers:
            self.observers.append(observer)

    def detach(self, observer: TelemetryObserver) -> None:
        self.observers.remove(observer)

    def notify(self) -> None:
        raw_size  = self.raw_queue.qsize()
        proc_size = self.processed_queue.qsize()

        data: Dict[str, Any] = {
            "raw_queue_size":       raw_size,
            "processed_queue_size": proc_size,
            "max_size":             self.max_size,
            "raw_pct":              (raw_size  / self.max_size * 100) if self.max_size else 0,
            "proc_pct":             (proc_size / self.max_size * 100) if self.max_size else 0,
            "raw_status":           self._classify(raw_size,  self.max_size),
            "proc_status":          self._classify(proc_size, self.max_size),
        }
        for obs in self.observers:
            obs.on_telemetry_update(data)

    def start(self) -> None:
        self.running = True
        self.thread  = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def _loop(self) -> None:
        while self.running:
            self.notify()
            time.sleep(self.poll_interval)

    @staticmethod
    def _classify(size: int, max_size: int) -> str:
        if max_size == 0:
            return "green"
        pct = size / max_size
        if pct < 0.5:
            return "green"
        if pct < 0.8:
            return "yellow"
        return "red"
