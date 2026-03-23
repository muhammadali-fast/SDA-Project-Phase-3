import queue
import logging
from multiprocessing import Queue
from multiprocessing.managers import DictProxy
from typing import Any, Dict, List

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.animation import FuncAnimation

from utils.interfaces import AbstractOutputModule, TelemetryObserver

logger = logging.getLogger(__name__)

COLOURS   = {"green": "#2ecc71", "yellow": "#f39c12", "red": "#e74c3c"}
DARK_BG   = "#1e1e2e"
PANEL_BG  = "#2a2a3e"
TEXT_CLR  = "#cdd6f4"
GRID_CLR  = "#45475a"
LINE_VAL  = "#89b4fa"
LINE_AVG  = "#a6e3a1"


class Dashboard(AbstractOutputModule, TelemetryObserver):
    """
    Reads processed packets from the queue and draws:
      - A telemetry bar showing raw_queue and processed_queue fill level
      - A live line chart of metric_value
      - A live line chart of the running average

    Telemetry data arrives through a shared Manager dict so updates from the
    main process are visible inside this child process.
    """

    SENTINEL = None

    def __init__(self, processed_queue: Queue, chart_configs: List[Dict],
                 telemetry_config: Dict, max_queue_size: int,
                 shared_telemetry: DictProxy) -> None:
        self.processed_queue  = processed_queue
        self.chart_configs    = chart_configs
        self.telemetry_config = telemetry_config
        self.max_queue_size   = max_queue_size
        self.shared_telemetry = shared_telemetry   # shared across processes

        self.times:  List[int]   = []
        self.values: List[float] = []
        self.avgs:   List[float] = []
        self.done = False

    def on_telemetry_update(self, data: Dict[str, Any]) -> None:
        self.shared_telemetry.update(data)

    def run(self) -> None:
        logging.basicConfig(level=logging.INFO,
                            format="[OUTPUT] %(asctime)s %(message)s",
                            datefmt="%H:%M:%S")
        logger.info("Dashboard process started.")
        self._build_figure()
        self.anim = FuncAnimation(self.fig, self._on_frame,
                                  interval=300, cache_frame_data=False)
        try:
            plt.show()
        except Exception as exc:
            logger.error("Dashboard window closed: %s", exc)

    def _build_figure(self) -> None:
        plt.style.use("dark_background")
        self.fig = plt.figure(figsize=(14, 9), facecolor=DARK_BG)
        self.fig.canvas.manager.set_window_title("Real-Time Pipeline Dashboard")

        n_charts = len(self.chart_configs)
        gs = gridspec.GridSpec(1 + n_charts, 1, figure=self.fig,
                               height_ratios=[1] + [3] * n_charts, hspace=0.45)

        self.ax_tel = self.fig.add_subplot(gs[0])
        self.ax_tel.axis("off")
        self.ax_tel.set_facecolor(PANEL_BG)

        self.chart_axes  = []
        self.chart_lines = []

        for idx, cfg in enumerate(self.chart_configs):
            ax = self.fig.add_subplot(gs[idx + 1])
            ax.set_facecolor(PANEL_BG)
            ax.set_title(cfg.get("title", f"Chart {idx+1}"),
                         color=TEXT_CLR, fontsize=11)
            ax.set_xlabel(cfg.get("x_axis", "x"), color=TEXT_CLR, fontsize=9)
            ax.set_ylabel(cfg.get("y_axis", "y"), color=TEXT_CLR, fontsize=9)
            ax.tick_params(colors=TEXT_CLR, labelsize=8)
            ax.grid(True, color=GRID_CLR, linestyle="--", linewidth=0.5)
            for spine in ax.spines.values():
                spine.set_edgecolor(GRID_CLR)

            colour = LINE_VAL if idx == 0 else LINE_AVG
            line, = ax.plot([], [], color=colour, linewidth=1.8,
                            label=cfg.get("y_axis", "value"))
            ax.legend(facecolor=PANEL_BG, labelcolor=TEXT_CLR, fontsize=8)

            self.chart_axes.append(ax)
            self.chart_lines.append(line)

    def _on_frame(self, _frame: int) -> None:
        if self.done:
            return

        while True:
            try:
                packet = self.processed_queue.get_nowait()
            except queue.Empty:
                break

            if packet is self.SENTINEL:
                self.done = True
                self.fig.suptitle("Pipeline Complete ✓", color=TEXT_CLR, fontsize=13)
                logger.info("Pipeline complete — all packets received.")
                break

            self.times.append(packet["time_period"])
            self.values.append(packet["metric_value"])
            self.avgs.append(packet["computed_metric"])

        for idx, (ax, line, cfg) in enumerate(
                zip(self.chart_axes, self.chart_lines, self.chart_configs)):
            y_data = self.avgs if "average" in cfg.get("type", "") else self.values
            if self.times and y_data:
                line.set_data(self.times, y_data)
                ax.relim()
                ax.autoscale_view()

        self._draw_telemetry()

    def _draw_telemetry(self) -> None:
        tel = dict(self.shared_telemetry)   # read from shared Manager dict
        ax  = self.ax_tel
        ax.cla()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.set_facecolor(PANEL_BG)
        ax.set_title("Pipeline Telemetry  (queue fill level)",
                     color=TEXT_CLR, fontsize=11, pad=6)

        bars = []
        if self.telemetry_config.get("show_raw_stream", True):
            bars.append(("Raw Queue",
                         tel.get("raw_pct",  0),
                         tel.get("raw_status",  "green"),
                         tel.get("raw_queue_size", 0)))
        if self.telemetry_config.get("show_processed_stream", True):
            bars.append(("Processed Queue",
                         tel.get("proc_pct", 0),
                         tel.get("proc_status", "green"),
                         tel.get("processed_queue_size", 0)))

        if not bars:
            return

        x_step = 1.0 / len(bars)
        max_sz = tel.get("max_size", self.max_queue_size) or self.max_queue_size

        for i, (label, pct, status, current_size) in enumerate(bars):
            cx     = x_step * i + x_step / 2
            colour = COLOURS.get(status, COLOURS["green"])
            left   = x_step * i + x_step * 0.075
            width  = x_step * 0.85

            ax.barh(0.5, width, height=0.35, left=left,
                    color=GRID_CLR, zorder=1)
            ax.barh(0.5, max(pct / 100 * width, 0.001), height=0.35,
                    left=left, color=colour, zorder=2)

            ax.text(cx, 0.88, label,
                    ha="center", va="center", color=TEXT_CLR,
                    fontsize=9, fontweight="bold")
            ax.text(cx, 0.12,
                    f"{pct:.0f}%  ({current_size}/{max_sz})  [{status.upper()}]",
                    ha="center", va="center", color=colour, fontsize=8)
