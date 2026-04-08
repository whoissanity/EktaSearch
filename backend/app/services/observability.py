from __future__ import annotations

import time
from collections import defaultdict

_adapter_count = defaultdict(int)
_adapter_error = defaultdict(int)
_adapter_latency_ms_sum = defaultdict(float)
_cache_hits = 0
_cache_misses = 0
_started_at = int(time.time())


def record_adapter(site: str, latency_ms: float, ok: bool) -> None:
    _adapter_count[site] += 1
    _adapter_latency_ms_sum[site] += latency_ms
    if not ok:
        _adapter_error[site] += 1


def record_cache(hit: bool) -> None:
    global _cache_hits, _cache_misses
    if hit:
        _cache_hits += 1
    else:
        _cache_misses += 1


def snapshot() -> dict:
    total_cache = _cache_hits + _cache_misses
    adapters = {}
    for site, count in _adapter_count.items():
        err = _adapter_error.get(site, 0)
        avg = (_adapter_latency_ms_sum[site] / count) if count else 0.0
        adapters[site] = {
            "calls": count,
            "errors": err,
            "error_rate": (err / count) if count else 0.0,
            "avg_latency_ms": round(avg, 2),
            "error_budget_remaining": max(0.0, 1.0 - (err / max(1, count))),
        }
    return {
        "uptime_seconds": int(time.time()) - _started_at,
        "cache": {
            "hits": _cache_hits,
            "misses": _cache_misses,
            "hit_ratio": (_cache_hits / total_cache) if total_cache else 0.0,
        },
        "adapters": adapters,
    }


def prometheus_text() -> str:
    s = snapshot()
    lines = [
        "# HELP ektasearch_uptime_seconds Process uptime in seconds",
        "# TYPE ektasearch_uptime_seconds gauge",
        f"ektasearch_uptime_seconds {s['uptime_seconds']}",
        "# HELP ektasearch_cache_hits_total Cache hit count",
        "# TYPE ektasearch_cache_hits_total counter",
        f"ektasearch_cache_hits_total {s['cache']['hits']}",
        "# HELP ektasearch_cache_misses_total Cache miss count",
        "# TYPE ektasearch_cache_misses_total counter",
        f"ektasearch_cache_misses_total {s['cache']['misses']}",
        "# HELP ektasearch_cache_hit_ratio Cache hit ratio",
        "# TYPE ektasearch_cache_hit_ratio gauge",
        f"ektasearch_cache_hit_ratio {s['cache']['hit_ratio']}",
    ]
    for site, row in s["adapters"].items():
        lines.append(f'ektasearch_adapter_calls_total{{site="{site}"}} {row["calls"]}')
        lines.append(f'ektasearch_adapter_errors_total{{site="{site}"}} {row["errors"]}')
        lines.append(f'ektasearch_adapter_error_rate{{site="{site}"}} {row["error_rate"]}')
        lines.append(f'ektasearch_adapter_avg_latency_ms{{site="{site}"}} {row["avg_latency_ms"]}')
        lines.append(
            f'ektasearch_adapter_error_budget_remaining{{site="{site}"}} {row["error_budget_remaining"]}'
        )
    return "\n".join(lines) + "\n"
