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

_tracer: trace.Tracer | None = None
_setup_done: bool = False


def setup_tracing(app: FastAPI) -> None:
    """初始化 OpenTelemetry；幂等，避免 reload 重复 set_tracer_provider。"""
    global _tracer, _setup_done

    if _setup_done:
        if _tracer is None:
            _tracer = trace.get_tracer("smartqa")
        return

    current = trace.get_tracer_provider()
    # 仅在尚未安装 SDK Provider 时设置，防止 reload 报
    # "Overriding of current TracerProvider is not allowed"
    if not isinstance(current, TracerProvider):
        resource = Resource(attributes={SERVICE_NAME: OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        # 开发环境默认不往控制台刷 span，避免噪音；有 OTLP 再导出
        if OTEL_EXPORTER_OTLP_ENDPOINT:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            otlp_exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        else:
            # 静默 provider：无 exporter，仅保证 get_tracer 可用
            pass
        trace.set_tracer_provider(provider)

    # 避免重复 instrument
    if not getattr(app.state, "_otel_instrumented", False):
        try:
            FastAPIInstrumentor.instrument_app(app)
            app.state._otel_instrumented = True
        except Exception:
            # 已 instrument 时忽略
            app.state._otel_instrumented = True

    _tracer = trace.get_tracer("smartqa")
    _setup_done = True
    print(f"  OpenTelemetry: 就绪 (service={OTEL_SERVICE_NAME})")


def get_tracer() -> trace.Tracer:
    """获取全局 Tracer 实例"""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("smartqa")
    return _tracer
