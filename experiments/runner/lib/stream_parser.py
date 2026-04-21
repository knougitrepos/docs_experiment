"""cursor-agent ``--output-format stream-json`` 결과를 파싱한다.

stream-json 포맷은 한 줄에 한 개의 JSON 이벤트.
공식 스키마는 ``https://cursor.com/docs/cli/headless`` 참고.
본 파서는 아래 이벤트를 가장 중요하게 본다:

- ``type == "assistant"``/``"user"`` turn 수 → 재프롬프트 횟수 추정 (#6)
- ``type == "tool_use"`` / ``"tool_result"`` step 수 → 전체 작업 비용 (#8)
- ``event == "error"``/``"apply_failed"``/``"retry"`` → 수동 수정 대체 지표 (#7)
- usage / cost 이벤트 → 토큰 사용량 (#8)

스키마가 version 에 따라 조금씩 다를 수 있어, 키 누락에 관대하게 읽는다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StreamStats:
    """stream.jsonl 1 개 run 의 요약."""

    user_turns: int = 0          # (#6) 재프롬프트
    assistant_turns: int = 0
    tool_calls: int = 0          # (#8) step 수
    retry_events: int = 0        # (#7) apply_failed / retry 대체
    error_events: int = 0
    prompt_tokens: int = 0       # (#8) cost
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    first_event_ts: str | None = None
    last_event_ts: str | None = None
    raw_event_count: int = 0
    unknown_events: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["unknown_events"] = sorted(set(self.unknown_events))
        return d


_RETRY_EVENT_SUBSTR = ("apply_failed", "retry", "tool_error", "recovered_from")


def parse_stream(stream_path: Path) -> StreamStats:
    """stream.jsonl 을 읽어 통계를 반환한다. 파일이 없으면 빈 통계."""
    stats = StreamStats()
    if not stream_path.exists():
        return stats

    with stream_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                # 비-JSON 라인 (콘솔 프롬프트 등)은 원시 에러로 카운트
                stats.error_events += 1
                continue
            stats.raw_event_count += 1

            ts = evt.get("timestamp") or evt.get("ts")
            if ts:
                if stats.first_event_ts is None:
                    stats.first_event_ts = ts
                stats.last_event_ts = ts

            # user/assistant turn
            etype = (evt.get("type") or evt.get("event") or "").lower()
            role = (evt.get("role") or "").lower()
            if etype == "user" or role == "user":
                stats.user_turns += 1
            elif etype == "assistant" or role == "assistant":
                stats.assistant_turns += 1

            # tool call / step
            if etype in ("tool_use", "tool_call", "tool") or "tool_use" in evt:
                stats.tool_calls += 1

            # retry / apply failed
            joined = json.dumps(evt, ensure_ascii=False).lower()
            if any(k in joined for k in _RETRY_EVENT_SUBSTR):
                stats.retry_events += 1

            # error
            if etype == "error" or "error" in evt:
                stats.error_events += 1

            # usage
            usage = evt.get("usage") or {}
            if isinstance(usage, dict):
                stats.prompt_tokens += int(usage.get("input_tokens", 0) or 0)
                stats.completion_tokens += int(usage.get("output_tokens", 0) or 0)
                stats.total_tokens += int(usage.get("total_tokens", 0) or 0)
            cost = evt.get("cost") or evt.get("total_cost_usd")
            if isinstance(cost, (int, float)):
                stats.total_cost_usd += float(cost)

            if etype and etype not in {
                "user",
                "assistant",
                "tool_use",
                "tool_call",
                "tool_result",
                "tool",
                "error",
                "message",
                "completion",
                "result",
                "start",
                "end",
                "system",
                "usage",
            }:
                stats.unknown_events.append(etype)

    # 완결값 보정
    if stats.total_tokens == 0:
        stats.total_tokens = stats.prompt_tokens + stats.completion_tokens
    return stats
