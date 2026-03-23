import hashlib
from typing import Any, Dict, List


def compute_signature(raw_value: float, secret_key: str, iterations: int) -> str:
    """
    Pure function. Computes PBKDF2-HMAC-SHA256 for a given metric value.

    The salt is the value formatted to exactly 2 decimal places (e.g. '44.30'),
    which matches how the data generator produces signatures.
    """
    raw_str  = f"{raw_value:.2f}"
    password = secret_key.encode("utf-8")
    salt     = raw_str.encode("utf-8")
    digest   = hashlib.pbkdf2_hmac("sha256", password, salt, iterations)
    return digest.hex()


def verify_packet(packet: Dict[str, Any], secret_key: str, iterations: int) -> bool:
    """Pure function. Returns True only if the packet's signature is valid."""
    expected = compute_signature(packet["metric_value"], secret_key, iterations)
    return expected == packet.get("security_hash", "")


def compute_running_average(window: List[float]) -> float:
    """Pure function. Returns the mean of the window, or 0.0 if empty."""
    return sum(window) / len(window) if window else 0.0
