from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio

LOG_PATH = Path("data/logs.jsonl")


def percentile(values: list[int | float], p: int) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[idx])


def main() -> None:
    configure_utf8_stdio()
    if not LOG_PATH.exists():
        print(f"Error: {LOG_PATH} not found. Run load_test.py first.")
        return

    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except Exception:
                continue

    # 1. Latency Panel
    latencies = [r["latency_ms"] for r in records if r.get("event") == "response_sent" and "latency_ms" in r]
    ttfts = [r["ttft_ms"] for r in records if r.get("event") == "response_sent" and "ttft_ms" in r]
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    ttft_p95 = percentile(ttfts, 95)
    latency_status = "[OK]" if p95 <= 3000 else "[ALERT]"

    # 2. Traffic Panel
    requests_received = [r for r in records if r.get("event") == "request_received"]
    traffic_count = len(requests_received)
    traffic_status = "[OK]" if traffic_count >= 1 else "[ALERT]"

    # 3. Errors Panel
    requests_failed = [r for r in records if r.get("event") == "request_failed"]
    error_rate = (len(requests_failed) / max(1, traffic_count)) * 100
    tool_events = [r for r in records if r.get("event") == "response_sent" and r.get("tool_success") is not None]
    tool_success_rate = (
        sum(1 for r in tool_events if r.get("tool_success") is True) / max(1, len(tool_events)) * 100
    )
    error_status = "[OK]" if error_rate <= 2.0 else "[ALERT]"

    # 4. Cost Panel
    costs = [r["cost_usd"] for r in records if r.get("event") == "response_sent" and "cost_usd" in r]
    total_cost = sum(costs)
    cost_status = "[OK]" if total_cost <= 2.5 else "[ALERT]"

    # 5. Tokens Panel
    tokens_in = sum(r["tokens_in"] for r in records if r.get("event") == "response_sent" and "tokens_in" in r)
    tokens_out = sum(r["tokens_out"] for r in records if r.get("event") == "response_sent" and "tokens_out" in r)
    tokens_status = "[OK]" if max(tokens_in, tokens_out) <= 50000 else "[ALERT]"

    # 6. Quality Panel
    qualities = [r["quality_score"] for r in records if r.get("event") == "response_sent" and "quality_score" in r]
    avg_quality = mean(qualities) if qualities else 0.0
    quality_status = "[OK]" if avg_quality >= 0.75 else "[ALERT]"

    print("=" * 70)
    print("      K4-L3B Day 13 Monitoring & LLMOps - RUNTIME DASHBOARD (6 Panels)")
    print("=" * 70)
    print(f"Time Range: 60 minutes | Total Records: {len(records)} | Refresh: 30s")
    print("-" * 70)
    print(f"1. LATENCY (Threshold: P95 <= 3000 ms)                        {latency_status}")
    print(f"   • P50: {p50:.1f} ms | P95: {p95:.1f} ms | P99: {p99:.1f} ms | TTFT P95: {ttft_p95:.1f} ms")
    print("-" * 70)
    print(f"2. TRAFFIC (Threshold: >= 1 req/min)                         {traffic_status}")
    print(f"   • Total Requests Received: {traffic_count} requests")
    print("-" * 70)
    print(f"3. ERRORS (Threshold: Error Rate <= 2%)                       {error_status}")
    print(f"   • Error Rate: {error_rate:.2f}% | Failed Requests: {len(requests_failed)}")
    print(f"   • Retrieval Success Rate: {tool_success_rate:.1f}%")
    print("-" * 70)
    print(f"4. COST (Threshold: Total <= $2.50)                           {cost_status}")
    print(f"   • Total Cost: ${total_cost:.4f} USD")
    print("-" * 70)
    print(f"5. TOKENS (Threshold: Max Field <= 50,000 tokens)             {tokens_status}")
    print(f"   • Tokens In: {tokens_in:,} | Tokens Out: {tokens_out:,} | Total: {tokens_in + tokens_out:,}")
    print("-" * 70)
    print(f"6. QUALITY (Threshold: Avg Quality >= 0.75)                   {quality_status}")
    print(f"   • Quality Score Mean: {avg_quality:.2f} / 1.00")
    print("=" * 70)


if __name__ == "__main__":
    main()
