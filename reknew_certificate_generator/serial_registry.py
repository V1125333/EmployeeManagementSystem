"""
Serial Number Registry
----------------------
Tracks the last-used serial number per (certificate_type, cohort_code, year)
combination and auto-increments on every issue.

Storage: a simple JSON file at  data/serial_registry.json
Format:
{
  "ReKnew Context Engineer|C1|2026": 5,
  "ReKnew AI Cloud Practitioner|C1|2026": 2,
  ...
}

Thread-safety: a file-level lock is used so concurrent Streamlit reruns
cannot corrupt the registry.
"""

import json
import threading
from pathlib import Path

# ─────────────────────────────────────────────────────────────
#  Storage location
# ─────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
DATA_DIR      = BASE_DIR / "data"
REGISTRY_FILE = DATA_DIR / "serial_registry.json"

# One process-level lock — sufficient for a local Streamlit app.
_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
#  Low-level read / write helpers
# ─────────────────────────────────────────────────────────────

def _load() -> dict:
    """Read the registry from disk, returning {} if missing/corrupt."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        return {}
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(registry: dict) -> None:
    """Write the registry back to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(
        json.dumps(registry, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _key(cert_type: str, cohort_code: str, year: int) -> str:
    """Build a unique string key from the three dimensions."""
    return f"{cert_type.strip()}|{cohort_code.strip().upper()}|{int(year)}"


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────

def peek_next(cert_type: str, cohort_code: str, year: int) -> int:
    """
    Return what the *next* serial number would be WITHOUT consuming it.
    Useful for previewing the Certificate ID in the UI.
    """
    with _lock:
        reg = _load()
        k   = _key(cert_type, cohort_code, year)
        return reg.get(k, 0) + 1


def consume_next(cert_type: str, cohort_code: str, year: int) -> int:
    """
    Atomically increment the counter and return the new serial number.
    Call this exactly once per certificate actually generated.
    """
    with _lock:
        reg      = _load()
        k        = _key(cert_type, cohort_code, year)
        next_sn  = reg.get(k, 0) + 1
        reg[k]   = next_sn
        _save(reg)
        return next_sn


def consume_batch(records: list[dict]) -> list[int]:
    """
    Assign serial numbers to a batch of records atomically.
    Each record must have keys: cert_type, cohort_code, year.
    Returns a list of serial numbers in the same order.

    Serial numbers are assigned per (cert_type, cohort_code, year) group,
    incrementing independently per group.
    """
    with _lock:
        reg     = _load()
        serials = []
        for rec in records:
            k       = _key(rec["cert_type"], rec["cohort_code"], rec["year"])
            next_sn = reg.get(k, 0) + 1
            reg[k]  = next_sn
            serials.append(next_sn)
        _save(reg)
        return serials


def get_all_counters() -> dict:
    """
    Return the full registry as a readable dict, e.g. for the admin view.
    Keys are human-friendly strings, values are the last issued serial.
    """
    with _lock:
        return dict(_load())


def reset_counter(cert_type: str, cohort_code: str, year: int,
                  value: int = 0) -> None:
    """
    Manually set (or reset) a counter — for admin use only.
    Setting value=0 means the next issue will be serial 001.
    """
    with _lock:
        reg = _load()
        k   = _key(cert_type, cohort_code, year)
        reg[k] = max(0, int(value))
        _save(reg)


def set_counter_to(cert_type: str, cohort_code: str, year: int,
                   last_issued: int) -> None:
    """
    Set counter so the *next* issued will be last_issued + 1.
    Useful for seeding the registry when migrating from an old system.
    """
    reset_counter(cert_type, cohort_code, year, last_issued)
