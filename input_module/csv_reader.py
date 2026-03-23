import csv
import time
import logging
from multiprocessing import Queue
from typing import Any, Dict, List

from utils.interfaces import AbstractInputModule

logger = logging.getLogger(__name__)

TYPE_CASTERS = {"string": str, "integer": int, "float": float}


def cast_value(raw: str, data_type: str) -> Any:
    caster = TYPE_CASTERS.get(data_type.lower())
    if caster is None:
        raise ValueError(f"Unsupported data_type '{data_type}' in schema_mapping.")
    return caster(raw)


class CSVInputModule(AbstractInputModule):
    """
    Reads a CSV file row by row and pushes each row (as a dict) onto raw_queue.

    Column names in the CSV are translated to internal names using schema_mapping
    from config.json, so this module works with any dataset without code changes.
    Putting onto a bounded queue blocks automatically when it is full — this is
    how back-pressure works.
    """

    SENTINEL = None

    def __init__(self, raw_queue: Queue, dataset_path: str,
                 schema_columns: List[Dict[str, str]],
                 input_delay: float, num_consumers: int) -> None:
        self.raw_queue      = raw_queue
        self.dataset_path   = dataset_path
        self.schema_columns = schema_columns
        self.input_delay    = input_delay
        self.num_consumers  = num_consumers

    def run(self) -> None:
        logging.basicConfig(level=logging.INFO,
                            format="[INPUT] %(asctime)s %(message)s",
                            datefmt="%H:%M:%S")
        logger.info("Input Module started. Reading: %s", self.dataset_path)
        sent = skipped = 0

        try:
            with open(self.dataset_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    packet = self._map_row(row)
                    if packet is None:
                        skipped += 1
                        continue
                    self.raw_queue.put(packet)      # blocks if queue is full (back-pressure)
                    sent += 1
                    logger.info("Pushed #%d  entity=%s  t=%s  val=%s",
                                sent, packet.get("entity_name"),
                                packet.get("time_period"), packet.get("metric_value"))
                    time.sleep(self.input_delay)
        except FileNotFoundError:
            logger.error("Dataset not found: %s", self.dataset_path)
        finally:
            for _ in range(self.num_consumers):
                self.raw_queue.put(self.SENTINEL)
            logger.info("Input done. sent=%d  skipped=%d", sent, skipped)

    def _map_row(self, row: Dict[str, str]) -> Dict[str, Any] | None:
        packet: Dict[str, Any] = {"computed_metric": 0.0}
        for col in self.schema_columns:
            source   = col["source_name"]
            internal = col["internal_mapping"]
            dtype    = col["data_type"]
            if source not in row:
                logger.warning("Column '%s' missing — skipping row.", source)
                return None
            try:
                packet[internal] = cast_value(row[source], dtype)
            except (ValueError, TypeError) as e:
                logger.warning("Cast error on '%s': %s — skipping row.", source, e)
                return None
        return packet
