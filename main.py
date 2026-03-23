import os
import sys
import logging
import platform
import multiprocessing
from multiprocessing import Queue, Process, Manager
from typing import List

from utils.config_loader import ConfigLoader
from utils.interfaces import (
    AbstractInputModule, AbstractCoreWorker,
    AbstractAggregator, AbstractOutputModule, TelemetrySubject,
)

from input_module.csv_reader        import CSVInputModule
from core_module.worker             import CoreWorker
from core_module.aggregator         import Aggregator
from output_module.dashboard        import Dashboard
from telemetry.pipeline_telemetry   import PipelineTelemetry

logging.basicConfig(level=logging.INFO,
                    format="[MAIN] %(asctime)s %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def _run_input(m):  m.run()
def _run_worker(w): w.run()
def _run_agg(a):    a.run()
def _run_output(o): o.run()


def main() -> None:

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    cfg = ConfigLoader(config_path)

    logger.info("Dataset          : %s", cfg.dataset_path)
    logger.info("Workers          : %d", cfg.core_parallelism)
    logger.info("Input delay      : %.3f s", cfg.input_delay_seconds)
    logger.info("Queue max size   : %d", cfg.stream_queue_max_size)
    logger.info("Window size      : %d", cfg.window_size)

    max_q = cfg.stream_queue_max_size
    n_workers = cfg.core_parallelism

    raw_queue       = Queue(maxsize=max_q)   # Input  → CoreWorkers
    verified_queue  = Queue(maxsize=max_q)   # CoreWorkers → Aggregator
    processed_queue = Queue(maxsize=max_q)   # Aggregator  → Dashboard

    dataset_abs = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               cfg.dataset_path)
    if not os.path.exists(dataset_abs):
        logger.error("Dataset not found: %s", dataset_abs)
        sys.exit(1)

    # Manager dict is visible to ALL processes — this is how telemetry
    # updates from the main process reach the Dashboard child process.
    manager = Manager()
    shared_telemetry = manager.dict({
        "raw_queue_size": 0, "processed_queue_size": 0,
        "raw_pct": 0, "proc_pct": 0,
        "raw_status": "green", "proc_status": "green",
        "max_size": max_q,
    })

    input_module: AbstractInputModule = CSVInputModule(
        raw_queue      = raw_queue,
        dataset_path   = dataset_abs,
        schema_columns = cfg.schema_columns,
        input_delay    = cfg.input_delay_seconds,
        num_consumers  = n_workers,
    )

    workers: List[AbstractCoreWorker] = [
        CoreWorker(i + 1, raw_queue, verified_queue,
                   cfg.secret_key, cfg.hash_iterations)
        for i in range(n_workers)
    ]

    aggregator: AbstractAggregator = Aggregator(
        verified_queue  = verified_queue,
        processed_queue = processed_queue,
        window_size     = cfg.window_size,
        num_workers     = n_workers,
    )

    dashboard: AbstractOutputModule = Dashboard(
        processed_queue  = processed_queue,
        chart_configs    = cfg.data_charts,
        telemetry_config = cfg.telemetry_config,
        max_queue_size   = max_q,
        shared_telemetry = shared_telemetry,
    )

    # Observer pattern: PipelineTelemetry (Subject) writes into shared_telemetry.
    # Dashboard (Observer) reads from it on every animation frame.
    telemetry: TelemetrySubject = PipelineTelemetry(
        raw_queue       = raw_queue,
        processed_queue = processed_queue,
        max_size        = max_q,
        poll_interval   = 0.3,
    )
    telemetry.attach(dashboard)    # type: ignore[arg-type]
    telemetry.start()

    processes: List[Process] = (
        [Process(target=_run_output, args=(dashboard,),  name="Output-Dashboard")]
      + [Process(target=_run_agg,    args=(aggregator,), name="Core-Aggregator")]
      + [Process(target=_run_worker, args=(w,),          name=f"Core-Worker-{i+1}")
         for i, w in enumerate(workers)]
      + [Process(target=_run_input,  args=(input_module,), name="Input-CSV")]
    )

    logger.info("Starting %d processes …", len(processes))
    for p in processes:
        p.start()
        logger.info("  Started %-20s  pid=%s", p.name, p.pid)

    try:
        for p in processes:
            p.join()
            logger.info("  Finished %-20s  exit=%s", p.name, p.exitcode)
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down.")
        for p in processes:
            p.terminate()
    finally:
        telemetry.stop()
        manager.shutdown()
        logger.info("Pipeline finished.")


if __name__ == "__main__":
    method = "fork" if platform.system() == "Linux" else "spawn"
    multiprocessing.set_start_method(method, force=True)
    main()
