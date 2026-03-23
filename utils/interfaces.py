from abc import ABC, abstractmethod
from typing import Any, Dict


class DataPacket:
    """The single domain-agnostic record that travels through the pipeline."""

    __slots__ = ("entity_name", "time_period", "metric_value",
                 "security_hash", "computed_metric")

    def __init__(self, entity_name: str, time_period: int, metric_value: float,
                 security_hash: str, computed_metric: float = 0.0) -> None:
        self.entity_name     = entity_name
        self.time_period     = time_period
        self.metric_value    = metric_value
        self.security_hash   = security_hash
        self.computed_metric = computed_metric

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_name":     self.entity_name,
            "time_period":     self.time_period,
            "metric_value":    self.metric_value,
            "security_hash":   self.security_hash,
            "computed_metric": self.computed_metric,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DataPacket":
        return cls(d["entity_name"], d["time_period"],
                   d["metric_value"], d["security_hash"],
                   d.get("computed_metric", 0.0))

    def __repr__(self) -> str:
        return (f"DataPacket(entity={self.entity_name!r}, t={self.time_period}, "
                f"val={self.metric_value}, avg={self.computed_metric:.4f})")


class AbstractInputModule(ABC):
    @abstractmethod
    def run(self) -> None: ...


class AbstractCoreWorker(ABC):
    @abstractmethod
    def run(self) -> None: ...


class AbstractAggregator(ABC):
    @abstractmethod
    def run(self) -> None: ...


class AbstractOutputModule(ABC):
    @abstractmethod
    def run(self) -> None: ...


class TelemetryObserver(ABC):
    @abstractmethod
    def on_telemetry_update(self, data: Dict[str, Any]) -> None: ...


class TelemetrySubject(ABC):
    @abstractmethod
    def attach(self, observer: TelemetryObserver) -> None: ...

    @abstractmethod
    def detach(self, observer: TelemetryObserver) -> None: ...

    @abstractmethod
    def notify(self) -> None: ...
