"""
OpenTelemetry 链路追踪配置
追踪全链路：HTTP 请求 → 意图分类 → LLM 调用 → SQL 执行 → 回答生成
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import FastAPI

from app.config import OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT

# 全局 TracerProvider
_tracer: trace.Tracer | None = None


def setup_tracing(app: FastAPI) -> None:
    """初始化 OpenTelemetry，为 FastAPI 应用接入全链路追踪"""
    resource = Resource(attributes={
        SERVICE_NAME: OTEL_SERVICE_NAME,
    })

    provider = TracerProvider(resource=resource)

    # 控制台导出（开发/调试用）
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # OTLP 导出（生产环境，对接 Jaeger/Grafana Tempo 等）
    if OTEL_EXPORTER_OTLP_ENDPOINT:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        otlp_exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    trace.set_tracer_provider(provider)

    # FastAPI 自动埋点
    FastAPIInstrumentor.instrument_app(app)

    global _tracer
    _tracer = trace.get_tracer(__name__)

    print(f"  OpenTelemetry: 就绪 (service={OTEL_SERVICE_NAME})")


def get_tracer() -> trace.Tracer:
    """获取全局 Tracer 实例"""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(__name__)
    return _tracer
