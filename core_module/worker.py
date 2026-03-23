import logging
from multiprocessing import Queue
from typing import Any, Dict

from utils.interfaces import AbstractCoreWorker
from core_module.functional_core import verify_packet

logger = logging.getLogger(__name__)


class CoreWorker(AbstractCoreWorker):
    """
    One stateless worker process in the Core Module.

    Pulls raw packets from raw_queue, verifies the signature using a pure
    function, and forwards only valid packets to verified_queue.
    Invalid packets are silently dropped.

    Multiple instances of this class run in parallel (core_parallelism from config).
    """

    SENTINEL = None

    def __init__(self, worker_id: int, raw_queue: Queue, verified_queue: Queue,
                 secret_key: str, iterations: int) -> None:
        self.worker_id      = worker_id
        self.raw_queue      = raw_queue
        self.verified_queue = verified_queue
        self.secret_key     = secret_key
        self.iterations     = iterations

    def run(self) -> None:
        logging.basicConfig(level=logging.INFO,
                            format=f"[CORE-W{self.worker_id}] %(asctime)s %(message)s",
                            datefmt="%H:%M:%S")
        logger.info("Worker %d started.", self.worker_id)
        accepted = rejected = 0

        while True:
            packet: Dict[str, Any] | None = self.raw_queue.get()

            if packet is self.SENTINEL:
                self.verified_queue.put(self.SENTINEL)
                logger.info("Worker %d done. accepted=%d  rejected=%d",
                            self.worker_id, accepted, rejected)
                break

            if verify_packet(packet, self.secret_key, self.iterations):
                self.verified_queue.put(packet)
                accepted += 1
                logger.info("W%d ACCEPTED  entity=%s  t=%s  val=%s",
                            self.worker_id, packet.get("entity_name"),
                            packet.get("time_period"), packet.get("metric_value"))
            else:
                rejected += 1
                logger.warning("W%d REJECTED  entity=%s  t=%s  val=%s",
                               self.worker_id, packet.get("entity_name"),
                               packet.get("time_period"), packet.get("metric_value"))
