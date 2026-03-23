import json
import os
from typing import Any, Dict, List


class ConfigLoader:
    """Loads config.json and exposes typed accessors for every setting."""

    def __init__(self, config_path: str = "config.json") -> None:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            self._raw: Dict[str, Any] = json.load(f)
        self._check_required_keys()

    def _check_required_keys(self) -> None:
        needed = {"dataset_path", "pipeline_dynamics",
                  "schema_mapping", "processing", "visualizations"}
        missing = needed - self._raw.keys()
        if missing:
            raise ValueError(f"config.json missing keys: {missing}")

    @property
    def dataset_path(self) -> str:
        return self._raw["dataset_path"]

    @property
    def input_delay_seconds(self) -> float:
        return float(self._raw["pipeline_dynamics"]["input_delay_seconds"])

    @property
    def core_parallelism(self) -> int:
        return int(self._raw["pipeline_dynamics"]["core_parallelism"])

    @property
    def stream_queue_max_size(self) -> int:
        return int(self._raw["pipeline_dynamics"]["stream_queue_max_size"])

    @property
    def schema_columns(self) -> List[Dict[str, str]]:
        return self._raw["schema_mapping"]["columns"]

    @property
    def secret_key(self) -> str:
        return str(self._raw["processing"]["stateless_tasks"]["secret_key"])

    @property
    def hash_iterations(self) -> int:
        return int(self._raw["processing"]["stateless_tasks"]["iterations"])

    @property
    def window_size(self) -> int:
        return int(self._raw["processing"]["stateful_tasks"]["running_average_window_size"])

    @property
    def telemetry_config(self) -> Dict[str, bool]:
        return self._raw["visualizations"]["telemetry"]

    @property
    def data_charts(self) -> List[Dict[str, str]]:
        return self._raw["visualizations"]["data_charts"]

    def raw(self) -> Dict[str, Any]:
        return dict(self._raw)
