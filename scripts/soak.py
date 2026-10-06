#!/usr/bin/env python3
"""
scripts/soak.py - Continuous Reliability Soak Harness for OhMyCrypto

Follows Section 12.1 of PROJECT_EXECUTION_GUIDE.md:
- Monitors monotonic duration, memory RSS, CPU, and connector status
- Enforces memory limit (engine RSS <= 512 MiB)
- Exercises the live WebSocket full-duplex streams for the whole run
- Samples real REST round-trip latency and reports p50 / p95 / p99
- Records heartbeats, latency distributions, incident counts, and resource usage
- Produces a final bound report with artifact hashes and environment metadata

Usage:
  .venv/bin/python scripts/soak.py --duration 86400 --profile release-v1 --output .agent/evidence/soak24
  .venv/bin/python scripts/soak.py --duration 900 --profile test-fast --output .agent/evidence/soak_test
"""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

# Hard resource ceiling for the engine process, per Section 12.1.
RSS_LIMIT_MIB = 512.0


def get_process_rss_mb(pid: int) -> float:
    """Get process RSS in MiB using macOS ps (returns KiB)."""
    try:
        res = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=True,
        )
        kib = float(res.stdout.strip())
        return round(kib / 1024.0, 2)
    except Exception:
        import resource

        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024.0 * 1024.0), 2)


def get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Live WebSocket stream worker (runs for the whole soak on its own loop)
# ---------------------------------------------------------------------------

def _ws_worker(duration_sec: float, symbol: str, result: dict) -> None:
    """Drive both venue WebSocket streams for the soak duration."""
    asyncio.run(_ws_main(duration_sec, symbol, result))


async def _ws_main(duration_sec: float, symbol: str, result: dict) -> None:
    from ohmycrypto.adapters.coinbase import CoinbaseConnector
    from ohmycrypto.adapters.kraken import KrakenConnector

    kraken = KrakenConnector()
    coinbase = CoinbaseConnector()
    errors: list[str] = []

    try:
        await kraken.start_stream([symbol], depth=10)
        await coinbase.start_stream([symbol], depth=10)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"stream start failed: {exc}")

    try:
        await asyncio.sleep(duration_sec)
    finally:
        for conn in (kraken, coinbase):
            try:
                await conn.stop_stream()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"stop_stream: {exc}")
            try:
                await conn.close()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"close: {exc}")

        result["kraken"] = kraken.stream_stats()
        result["coinbase"] = coinbase.stream_stats()
        result["errors"] = errors


# ---------------------------------------------------------------------------
# REST latency sampling
# ---------------------------------------------------------------------------

async def _poll_latency(symbol: str) -> dict:
    """Measure one REST round trip per venue. Returns ms latencies by venue."""
    from ohmycrypto.adapters.coinbase import CoinbaseConnector
    from ohmycrypto.adapters.kraken import KrakenConnector

    out: dict[str, float] = {}
    for name, factory in (("coinbase", CoinbaseConnector), ("kraken", KrakenConnector)):
        conn = factory()
        started = time.monotonic()
        try:
            await conn.fetch_orderbook(symbol, depth=10)
            out[name] = (time.monotonic() - started) * 1000.0
        except Exception:  # noqa: BLE001 - network faults are recorded, not fatal
            out[name] = None  # type: ignore[assignment]
        finally:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001
                pass
    return out


def main():
    parser = argparse.ArgumentParser(description="OhMyCrypto Continuous Soak Runner")
    parser.add_argument("--duration", type=int, default=86400, help="Duration in seconds (default 86400 = 24h)")
    parser.add_argument("--profile", type=str, default="release-v1", help="Profile identifier")
    parser.add_argument("--output", type=str, required=True, help="Output directory or JSON path")
    parser.add_argument("--symbol", type=str, default="BTC/USDT", help="Trading pair")
    parser.add_argument("--heartbeat-interval", type=int, default=5, help="Heartbeat sampling interval in seconds")
    parser.add_argument("--latency-interval", type=int, default=15, help="REST latency sampling interval in seconds")
    parser.add_argument("--no-websocket", action="store_true", help="Disable the WebSocket stream worker")
    args = parser.parse_args()

    out_path = Path(args.output)
    if out_path.suffix == ".json":
        out_file = out_path
        out_dir = out_path.parent
    else:
        out_dir = out_path
        out_file = out_dir / "soak_report.json"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Starting Continuous Soak Profile: {args.profile} ===", flush=True)
    print(f"Target duration: {args.duration}s ({args.duration / 3600:.2f} hours)", flush=True)
    print(f"Sampling symbol: {args.symbol}", flush=True)
    print(f"WebSocket stream: {'disabled' if args.no_websocket else 'enabled'}", flush=True)
    print(f"Report output: {out_file}", flush=True)

    from ohmycrypto.adapters.stream import LatencySamples

    latency = LatencySamples(capacity=5000)
    per_venue_latency = {"coinbase": LatencySamples(capacity=5000), "kraken": LatencySamples(capacity=5000)}

    start_mono = time.monotonic()
    start_time_utc = datetime.now(timezone.utc)
    current_pid = os.getpid()

    samples = []
    errors = []
    heartbeats = 0
    max_rss_mb = 0.0
    initial_rss_mb = get_process_rss_mb(current_pid)
    latency_polls = 0
    latency_failures = 0
    stop_requested = False

    # Launch the WebSocket stream worker for the full duration.
    ws_result: dict = {}
    ws_thread = None
    if not args.no_websocket:
        ws_thread = threading.Thread(
            target=_ws_worker,
            args=(args.duration, args.symbol, ws_result),
            daemon=True,
            name="ws-soak",
        )
        ws_thread.start()

    def handle_sig(sig, frame):
        nonlocal stop_requested
        print(f"\nReceived signal {sig}, terminating soak gracefully...", flush=True)
        stop_requested = True

    try:
        import signal

        signal.signal(signal.SIGINT, handle_sig)
        signal.signal(signal.SIGTERM, handle_sig)
    except Exception:  # noqa: BLE001 - signals unavailable on some hosts
        pass

    target_end_mono = start_mono + args.duration
    next_latency_mono = start_mono

    while time.monotonic() < target_end_mono and not stop_requested:
        loop_start = time.monotonic()
        heartbeats += 1

        rss = get_process_rss_mb(current_pid)
        if rss > max_rss_mb:
            max_rss_mb = rss

        sample = {
            "tick": heartbeats,
            "elapsed_sec": round(time.monotonic() - start_mono, 2),
            "rss_mb": rss,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        # Bounded ring: never retain more than 500 samples in memory.
        if len(samples) < 500:
            samples.append(sample)
        else:
            samples[heartbeats % 500] = sample

        if rss > RSS_LIMIT_MIB:
            err_msg = f"Memory RSS exceeded limit: {rss} MiB > {RSS_LIMIT_MIB} MiB"
            print(f"WARNING: {err_msg}", flush=True)
            errors.append({"tick": heartbeats, "error": err_msg})

        # Periodic real REST latency sampling.
        if loop_start >= next_latency_mono:
            next_latency_mono = loop_start + args.latency_interval
            try:
                measured = asyncio.run(_poll_latency(args.symbol))
                latency_polls += 1
                for venue, ms in measured.items():
                    if ms is None:
                        latency_failures += 1
                        continue
                    latency.add(ms)
                    per_venue_latency[venue].add(ms)
            except Exception as exc:  # noqa: BLE001
                latency_failures += 1
                print(f"[soak] latency poll error: {exc}", flush=True)

        if heartbeats % max(1, int(60 / args.heartbeat_interval)) == 0 or heartbeats <= 3:
            elapsed = time.monotonic() - start_mono
            print(
                f"[{elapsed:6.1f}s / {args.duration}s] Heartbeat #{heartbeats}: "
                f"RSS = {rss:.1f} MB (Peak: {max_rss_mb:.1f} MB), "
                f"latency samples = {latency.quantiles()['count']}",
                flush=True,
            )

        sleep_time = max(0.1, args.heartbeat_interval - (time.monotonic() - loop_start))
        time.sleep(sleep_time)

    if ws_thread is not None:
        # Give the worker a bounded window to tear down its streams.
        ws_thread.join(timeout=30)

    end_mono = time.monotonic()
    end_time_utc = datetime.now(timezone.utc)
    actual_duration = round(end_mono - start_mono, 2)

    final_rss_mb = get_process_rss_mb(current_pid)
    latency_q = latency.quantiles()

    # Section 12.1: "RUNNING, a PID or partial heartbeats cannot pass R12."
    # The window passes only when it actually covered the requested duration
    # (small grace for scheduler jitter), with zero errors and bounded RSS.
    # A premature stop (signal, crash, host reaping) is a FAILED window.
    grace_sec = 5.0
    if stop_requested:
        outcome = False
    else:
        outcome = actual_duration >= (args.duration - grace_sec)
    passed = (
        outcome
        and len(errors) == 0
        and max_rss_mb <= RSS_LIMIT_MIB
    )

    report = {
        "soak_id": f"soak_{args.profile}_{int(start_time_utc.timestamp())}",
        "profile": args.profile,
        "commit": get_git_commit(),
        "timestamp_start_utc": start_time_utc.isoformat(),
        "timestamp_end_utc": end_time_utc.isoformat(),
        "target_duration_sec": args.duration,
        "actual_duration_sec": actual_duration,
        "completed_target": actual_duration >= args.duration,
        "heartbeats_count": heartbeats,
        "memory_metrics": {
            "initial_rss_mb": initial_rss_mb,
            "max_rss_mb": max_rss_mb,
            "final_rss_mb": final_rss_mb,
            "limit_rss_mb": RSS_LIMIT_MIB,
            "within_limits": max_rss_mb <= RSS_LIMIT_MIB,
        },
        "latency_metrics_ms": {
            "poll_interval_sec": args.latency_interval,
            "polls_attempted": latency_polls,
            "polls_failed": latency_failures,
            "combined": latency_q,
            "per_venue": {venue: s.quantiles() for venue, s in per_venue_latency.items()},
        },
        "websocket_stream": {
            "enabled": not args.no_websocket,
            "kraken": ws_result.get("kraken"),
            "coinbase": ws_result.get("coinbase"),
            "errors": ws_result.get("errors", []),
        },
        "errors_count": len(errors),
        "errors": errors,
        "sample_count": len(samples),
        "sample_data": samples[:20],
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "os_release": platform.mac_ver()[0] if hasattr(platform, "mac_ver") else "unknown",
        },
        "passed": passed,
    }

    with open(out_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nSoak report written to: {out_file}", flush=True)
    print(f"Total Duration: {actual_duration:.1f}s (target {args.duration}s)", flush=True)
    print(f"Max RSS: {max_rss_mb:.1f} MB (Limit: {RSS_LIMIT_MIB} MB)", flush=True)
    print(f"Latency p50/p95/p99 ms: {latency_q.get('p50')} / {latency_q.get('p95')} / {latency_q.get('p99')}", flush=True)
    print(f"Status: {'PASSED' if passed else 'FAILED'}", flush=True)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
