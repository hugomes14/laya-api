"""Measure cold model load and warm CPU inference latency locally."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time

from app.classifier import LayaClassifier, load_classifier


SAMPLE_TICKET = {
    "subject": "Não consigo entrar no ERP",
    "body": (
        "Desde esta manhã não consigo fazer login no ERP. "
        "Aparece a mensagem invalid credentials."
    ),
}


def _percentile(values: list[float], percentile: float) -> float:
    """Return a linearly interpolated percentile from sorted measurements."""

    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def benchmark(
    classifier: LayaClassifier, warmup: int, runs: int
) -> dict[str, float | int | str]:
    """Warm the loaded model and return repeated inference measurements."""

    for _ in range(warmup):
        classifier.classify(**SAMPLE_TICKET)

    durations = []
    for _ in range(runs):
        started = time.perf_counter()
        classifier.classify(**SAMPLE_TICKET)
        durations.append(time.perf_counter() - started)

    return {
        "model": "laya-multilingual",
        "runs": runs,
        "warmup": warmup,
        "mean_ms": statistics.mean(durations) * 1000,
        "median_ms": statistics.median(durations) * 1000,
        "p95_ms": _percentile(durations, 0.95) * 1000,
        "min_ms": min(durations) * 1000,
        "max_ms": max(durations) * 1000,
    }


def main() -> None:
    """Parse options, load Laya once, and print a JSON benchmark report."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    if args.warmup < 0 or args.runs < 1:
        parser.error("--warmup must be >= 0 and --runs must be >= 1")

    load_started = time.perf_counter()
    classifier = load_classifier()
    load_seconds = time.perf_counter() - load_started
    report = benchmark(classifier, args.warmup, args.runs)
    import torch

    report["model_load_seconds"] = load_seconds
    report["python_version"] = platform.python_version()
    report["torch_version"] = torch.__version__
    report["cpu"] = platform.processor() or platform.machine()
    report["logical_cpus"] = os.cpu_count() or 1
    report["torch_threads"] = torch.get_num_threads()
    report["torch_interop_threads"] = torch.get_num_interop_threads()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
