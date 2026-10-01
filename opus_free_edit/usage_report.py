"""Summarise token usage and cost from a `claude -p --output-format stream-json` log."""
import json
import sys
from pathlib import Path


def load(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def main(path: Path) -> None:
    events = load(path)
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    tool_calls = sum(1 for e in events if e.get("type") == "assistant"
                     for c in e.get("message", {}).get("content", []) if c.get("type") == "tool_use")
    print("# Agent usage\n")
    if result is None:
        print("No result event was written (the agent did not finish normally).")
        return
    print(f"- status: {result.get('subtype')} / is_error={result.get('is_error')}")
    print(f"- turns: {result.get('num_turns')} / tool calls: {tool_calls}")
    print(f"- agent wall time: {result.get('duration_ms', 0) / 60000:.1f} min "
          f"(API time {result.get('duration_api_ms', 0) / 60000:.1f} min)")
    print(f"- API-equivalent cost: ${result.get('total_cost_usd', 0):.2f} "
          "(billed to the subscription, shown for scale only)\n")
    print("| model | input | cache write | cache read | output | cost USD |")
    print("|---|---:|---:|---:|---:|---:|")
    for model, u in (result.get("modelUsage") or {}).items():
        print(f"| {model} | {u.get('inputTokens', 0):,} | {u.get('cacheCreationInputTokens', 0):,} | "
              f"{u.get('cacheReadInputTokens', 0):,} | {u.get('outputTokens', 0):,} | {u.get('costUSD', 0):.2f} |")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
