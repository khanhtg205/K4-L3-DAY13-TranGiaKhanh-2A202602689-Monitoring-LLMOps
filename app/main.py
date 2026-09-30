from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from structlog.contextvars import bind_contextvars

from .agent import LabAgent
from .incidents import disable, enable, status
from .logging_config import configure_logging, get_logger
from .metrics import record_error, snapshot
from .middleware import CorrelationIdMiddleware
from .pii import hash_user_id, summarize_text
from .schemas import ChatRequest, ChatResponse
from .tracing import tracing_enabled

configure_logging()
log = get_logger()
agent = LabAgent()


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info(
        "app_started",
        service=os.getenv("APP_NAME", "day13-monitoring-llmops-lab"),
        env=os.getenv("APP_ENV", "dev"),
        payload={"tracing_enabled": tracing_enabled()},
    )
    yield


app = FastAPI(title="Day 13 Monitoring & LLMOps Lab", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)


from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
from statistics import mean
import json


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "tracing_enabled": tracing_enabled(), "incidents": status()}


@app.get("/metrics")
async def metrics() -> dict:
    return snapshot()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view() -> str:
    log_file = Path("data/logs.jsonl")
    records = []
    if log_file.exists():
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue

    def pct(values: list[int | float], p: int) -> float:
        if not values:
            return 0.0
        items = sorted(values)
        idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
        return float(items[idx])

    latencies = [r["latency_ms"] for r in records if r.get("event") == "response_sent" and "latency_ms" in r]
    ttfts = [r["ttft_ms"] for r in records if r.get("event") == "response_sent" and "ttft_ms" in r]
    p50 = pct(latencies, 50)
    p95 = pct(latencies, 95)
    p99 = pct(latencies, 99)
    ttft_p95 = pct(ttfts, 95)
    latest_lat = latencies[-1] if latencies else 0

    traffic_reqs = [r for r in records if r.get("event") == "request_received"]
    traffic_cnt = len(traffic_reqs)

    failed_reqs = [r for r in records if r.get("event") == "request_failed"]
    error_rate = (len(failed_reqs) / max(1, traffic_cnt)) * 100
    tool_events = [r for r in records if r.get("event") == "response_sent" and r.get("tool_success") is not None]
    tool_success_rate = (
        sum(1 for r in tool_events if r.get("tool_success") is True) / max(1, len(tool_events)) * 100
    )

    costs = [r["cost_usd"] for r in records if r.get("event") == "response_sent" and "cost_usd" in r]
    total_cost = sum(costs)

    tokens_in = sum(r["tokens_in"] for r in records if r.get("event") == "response_sent" and "tokens_in" in r)
    tokens_out = sum(r["tokens_out"] for r in records if r.get("event") == "response_sent" and "tokens_out" in r)

    qualities = [r["quality_score"] for r in records if r.get("event") == "response_sent" and "quality_score" in r]
    avg_quality = mean(qualities) if qualities else 0.0

    lat_ok = p95 <= 3000
    traff_ok = traffic_cnt >= 1
    err_ok = error_rate <= 2.0
    cost_ok = total_cost <= 2.5
    tok_ok = max(tokens_in, tokens_out) <= 50000
    qual_ok = avg_quality >= 0.75

    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    def badge(ok: bool) -> str:
        color = "#10b981" if ok else "#ef4444"
        bg = "rgba(16, 185, 129, 0.15)" if ok else "rgba(239, 68, 68, 0.15)"
        text = "PASS" if ok else "ALERT"
        return f'<span style="background:{bg};color:{color};padding:4px 10px;border-radius:9999px;font-size:12px;font-weight:600;border:1px solid {color}33;">{text}</span>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="10">
    <title>K4-L3B Day 13 Monitoring & LLMOps Dashboard</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: #0f172a; color: #f8fafc; padding: 28px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #334155; }}
        .title h1 {{ font-size: 24px; font-weight: 700; color: #f1f5f9; }}
        .meta {{ display: flex; gap: 12px; font-size: 13px; color: #94a3b8; align-items: center; }}
        .meta-tag {{ background: #1e293b; padding: 6px 12px; border-radius: 6px; border: 1px solid #334155; }}
        .btn-refresh {{ background: #3b82f6; color: white; border: none; padding: 6px 14px; border-radius: 6px; font-weight: 600; cursor: pointer; }}
        .btn-refresh:hover {{ background: #2563eb; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 20px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 22px; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
        .card-title {{ font-size: 14px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
        .metric-main {{ font-size: 32px; font-weight: 700; color: #f8fafc; margin-bottom: 12px; }}
        .metric-unit {{ font-size: 16px; font-weight: 400; color: #94a3b8; }}
        .sub-metrics {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; padding-top: 12px; border-top: 1px solid #334155; }}
        .sub-item {{ background: #0f172a; padding: 8px 12px; border-radius: 6px; font-size: 12px; color: #cbd5e1; flex: 1; min-width: 100px; }}
        .sub-item strong {{ display: block; font-size: 14px; color: #f8fafc; margin-top: 2px; }}
        .threshold {{ font-size: 12px; color: #64748b; margin-top: 8px; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title">
            <h1>K4-L3B Day 13 Monitoring & LLMOps Dashboard</h1>
            <p style="font-size: 13px; color: #64748b; margin-top: 4px;">Live Metrics from <code>data/logs.jsonl</code> (6 Panels Contract)</p>
        </div>
        <div class="meta">
            <div class="meta-tag">Updated: <strong>{now_str}</strong></div>
            <div class="meta-tag">Time Range: <strong>60m</strong></div>
            <div class="meta-tag">Total Logs: <strong>{len(records)}</strong></div>
            <button class="btn-refresh" onclick="location.reload()">Refresh</button>
        </div>
    </div>

    <div class="grid">
        <!-- Panel 1: Latency -->
        <div class="card">
            <div class="card-header">
                <span class="card-title">1. Latency & TTFT</span>
                {badge(lat_ok)}
            </div>
            <div class="metric-main">{p95:.1f} <span class="metric-unit">ms (P95)</span></div>
            <div class="sub-metrics">
                <div class="sub-item">P50<strong>{p50:.1f} ms</strong></div>
                <div class="sub-item">Latest Req<strong>{latest_lat:.1f} ms</strong></div>
                <div class="sub-item">P99<strong>{p99:.1f} ms</strong></div>
                <div class="sub-item">TTFT P95<strong>{ttft_p95:.1f} ms</strong></div>
            </div>
            <div class="threshold">Threshold: P95 &le; 3000 ms</div>
        </div>

        <!-- Panel 2: Traffic -->
        <div class="card">
            <div class="card-header">
                <span class="card-title">2. Request Traffic</span>
                {badge(traff_ok)}
            </div>
            <div class="metric-main">{traffic_cnt} <span class="metric-unit">requests</span></div>
            <div class="sub-metrics">
                <div class="sub-item">Total Received<strong>{traffic_cnt}</strong></div>
                <div class="sub-item">Active Window<strong>60m</strong></div>
            </div>
            <div class="threshold">Threshold: Rate &ge; 1 req/min</div>
        </div>

        <!-- Panel 3: Errors -->
        <div class="card">
            <div class="card-header">
                <span class="card-title">3. Errors & Retrieval Success</span>
                {badge(err_ok)}
            </div>
            <div class="metric-main">{error_rate:.2f} <span class="metric-unit">%</span></div>
            <div class="sub-metrics">
                <div class="sub-item">Failed Reqs<strong>{len(failed_reqs)}</strong></div>
                <div class="sub-item">Retrieval Success<strong>{tool_success_rate:.1f}%</strong></div>
            </div>
            <div class="threshold">Threshold: Error Rate &le; 2.0% | Retrieval &ge; 90%</div>
        </div>

        <!-- Panel 4: Cost -->
        <div class="card">
            <div class="card-header">
                <span class="card-title">4. Cost Over Time</span>
                {badge(cost_ok)}
            </div>
            <div class="metric-main">${total_cost:.4f} <span class="metric-unit">USD</span></div>
            <div class="sub-metrics">
                <div class="sub-item">Total Window<strong>${total_cost:.4f}</strong></div>
                <div class="sub-item">Avg / Request<strong>${(total_cost / max(1, traffic_cnt)):.4f}</strong></div>
            </div>
            <div class="threshold">Threshold: Total Cost &le; $2.50 USD</div>
        </div>

        <!-- Panel 5: Tokens -->
        <div class="card">
            <div class="card-header">
                <span class="card-title">5. Input & Output Tokens</span>
                {badge(tok_ok)}
            </div>
            <div class="metric-main">{tokens_in + tokens_out:,} <span class="metric-unit">total tokens</span></div>
            <div class="sub-metrics">
                <div class="sub-item">Tokens In<strong>{tokens_in:,}</strong></div>
                <div class="sub-item">Tokens Out<strong>{tokens_out:,}</strong></div>
            </div>
            <div class="threshold">Threshold: Sum by field &le; 50,000 tokens</div>
        </div>

        <!-- Panel 6: Quality -->
        <div class="card">
            <div class="card-header">
                <span class="card-title">6. Quality Proxy</span>
                {badge(qual_ok)}
            </div>
            <div class="metric-main">{avg_quality:.2f} <span class="metric-unit">/ 1.00</span></div>
            <div class="sub-metrics">
                <div class="sub-item">Quality Score Mean<strong>{avg_quality:.2f}</strong></div>
                <div class="sub-item">Evaluated Reqs<strong>{len(qualities)}</strong></div>
            </div>
            <div class="threshold">Threshold: Mean &ge; 0.75</div>
        </div>
    </div>
</body>
</html>"""
    return html


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    bind_contextvars(
        user_id_hash=hash_user_id(body.user_id),
        session_id=body.session_id,
        feature=body.feature,
        model=agent.model,
        env=os.getenv("APP_ENV", "dev"),
    )
    
    log.info(
        "request_received",
        service="api",
        payload={"message_preview": summarize_text(body.message)},
    )
    try:
        result = agent.run(
            user_id=body.user_id,
            feature=body.feature,
            session_id=body.session_id,
            message=body.message,
            correlation_id=request.state.correlation_id,
        )
        log.info(
            "response_sent",
            service="api",
            latency_ms=result.latency_ms,
            ttft_ms=result.ttft_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
            tool_name="retrieval",
            tool_success=True,
            payload={"answer_preview": summarize_text(result.answer)},
        )
        return ChatResponse(
            answer=result.answer,
            correlation_id=request.state.correlation_id,
            latency_ms=result.latency_ms,
            ttft_ms=result.ttft_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
        )
    except Exception as exc:  # pragma: no cover
        error_type = type(exc).__name__
        record_error(error_type)
        log.error(
            "request_failed",
            service="api",
            error_type=error_type,
            tool_name="retrieval" if isinstance(exc, RuntimeError) else None,
            tool_success=False if isinstance(exc, RuntimeError) else None,
            payload={"detail": str(exc), "message_preview": summarize_text(body.message)},
        )
        raise HTTPException(status_code=500, detail=error_type) from exc


@app.post("/incidents/{name}/enable")
async def enable_incident(name: str) -> JSONResponse:
    try:
        enable(name)
        log.warning("incident_enabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/incidents/{name}/disable")
async def disable_incident(name: str) -> JSONResponse:
    try:
        disable(name)
        log.warning("incident_disabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
