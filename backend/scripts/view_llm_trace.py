from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import indent
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TRACE_PATH = BACKEND_DIR / "storage" / "logs" / "translation_llm_trace.jsonl"


def _last_json_line(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"Trace file is empty: {path}")

    return json.loads(lines[-1])


def _section(title: str, body: str) -> str:
    rule = "=" * len(title)
    return f"\n{title}\n{rule}\n{body.rstrip()}\n"


def _format_metadata(trace: dict[str, Any]) -> str:
    metrics = trace.get("run_metrics") or {}
    lines = [
        f"timestamp: {trace.get('timestamp')}",
        f"page_id: {trace.get('page_id')}",
        f"pipeline_run_id: {trace.get('pipeline_run_id')}",
        f"target_language: {trace.get('target_language')}",
        f"provider_mode: {trace.get('provider_mode')}",
        f"model: {trace.get('model')}",
        f"gateway_calls: {metrics.get('gateway_calls')}",
        f"latency_ms_total: {metrics.get('gateway_latency_ms_total')}",
        f"translated_orders: {metrics.get('translated_orders')}/{metrics.get('requested_orders')}",
        f"helper_image_failed: {metrics.get('helper_image_failed')}",
        f"memory_retrieval_failed: {metrics.get('memory_retrieval_failed')}",
    ]
    return "\n".join(lines)


def _format_memory(trace: dict[str, Any]) -> str:
    stats = (trace.get("run_metrics") or {}).get("memory_stats")
    if not stats:
        return "No memory stats recorded."
    return "\n".join(f"{key}: {value}" for key, value in stats.items())


def _first_event(trace: dict[str, Any]) -> dict[str, Any]:
    events = trace.get("trace_events") or []
    if not events:
        return {}
    return events[0] if isinstance(events[0], dict) else {}


def _format_request(event: dict[str, Any]) -> str:
    messages = event.get("request_messages") or []
    chunks: list[str] = []
    for index, message in enumerate(messages, start=1):
        role = message.get("role", "unknown")
        content = message.get("content")
        chunks.append(f"[{index}] role={role}")

        if isinstance(content, str):
            chunks.append(indent(content.strip(), "  "))
            continue

        if isinstance(content, list):
            for block in content:
                block_type = block.get("type")
                if block_type == "image_url":
                    chunks.append("  [image]")
                    chunks.append(indent(json.dumps(block.get("image_url"), ensure_ascii=False, indent=2), "    "))
                elif block_type == "text":
                    chunks.append("  [text]")
                    chunks.append(indent(str(block.get("text", "")).strip(), "    "))
                else:
                    chunks.append(indent(json.dumps(block, ensure_ascii=False, indent=2), "  "))
            continue

        chunks.append(indent(json.dumps(content, ensure_ascii=False, indent=2), "  "))

    return "\n\n".join(chunks) if chunks else "No request messages recorded."


def _format_response(event: dict[str, Any]) -> str:
    parsed = event.get("response_parsed")
    if not isinstance(parsed, dict):
        return str(event.get("response_raw_text") or "No response recorded.")

    lines = [f"page_summary: {parsed.get('page_summary')}"]
    for item in parsed.get("lines") or []:
        lines.extend(
            [
                "",
                f"[{item.get('order')}] {item.get('source_text')}",
                f"literal: {item.get('literal_translation')}",
                f"natural: {item.get('natural_translation')}",
                f"speaker: {item.get('speaker_context')}",
                f"image: {item.get('image_explanation')}",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pretty-print the latest translation LLM trace.")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_TRACE_PATH,
        help=f"Trace file path. Defaults to {DEFAULT_TRACE_PATH}",
    )
    parser.add_argument(
        "--raw-response",
        action="store_true",
        help="Print the raw LLM response instead of the parsed response summary.",
    )
    args = parser.parse_args()

    trace = _last_json_line(args.path)
    event = _first_event(trace)

    print(_section("TRACE METADATA", _format_metadata(trace)))
    print(_section("TRANSLATION MEMORY STATS", _format_memory(trace)))
    print(_section("REQUEST SENT TO LLM", _format_request(event)))

    if args.raw_response:
        response = str(event.get("response_raw_text") or "No raw response recorded.")
    else:
        response = _format_response(event)
    print(_section("LLM RESPONSE", response))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
