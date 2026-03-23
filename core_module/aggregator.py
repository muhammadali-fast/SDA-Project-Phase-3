import logging
from collections import deque
from multiprocessing import Queue
from typing import Any, Dict

from utils.interfaces import AbstractAggregator
from core_module.functional_core import compute_running_average

logger = logging.getLogger(__name__)


class Aggregator(AbstractAggregator):
    """
    Single stateful process that maintains a sliding window of metric values.

    Pulls verified packets from verified_queue, updates the window (mutable
    state lives only here), calls compute_running_average() (pure function),
    attaches the result as computed_metric, and pushes to processed_queue.

    Waits for a sentinel from every CoreWorker before shutting down, so no
    packet is lost when workers finish at different times.
    """

    SENTINEL = None

    def __init__(self, verified_queue: Queue, processed_queue: Queue,
                 window_size: int, num_workers: int) -> None:
        self.verified_queue  = verified_queue
        self.processed_queue = processed_queue
        self.window_size     = window_size
        self.num_workers     = num_workers
        self.window          = deque(maxlen=window_size)

    def run(self) -> None:
        logging.basicConfig(level=logging.INFO,
                            format="[AGGREGATOR] %(asctime)s %(message)s",
                            datefmt="%H:%M:%S")
        logger.info("Aggregator started. window_size=%d", self.window_size)
        sentinels_seen = processed = 0

        while True:
            packet: Dict[str, Any] | None = self.verified_queue.get()

            if packet is self.SENTINEL:
                sentinels_seen += 1
                logger.info("Received sentinel %d/%d.", sentinels_seen, self.num_workers)
                if sentinels_seen >= self.num_workers:
                    self.processed_queue.put(self.SENTINEL)
                    logger.info("Aggregator done. processed=%d", processed)
                    break
                continue

            self.window.append(packet["metric_value"])
            packet["computed_metric"] = compute_running_average(list(self.window))
            self.processed_queue.put(packet)
            processed += 1
            logger.info("entity=%s  t=%s  val=%s  avg=%.4f",
                        packet.get("entity_name"), packet.get("time_period"),
                        packet.get("metric_value"), packet["computed_metric"])
