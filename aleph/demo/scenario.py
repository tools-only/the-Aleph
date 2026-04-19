from __future__ import annotations

import shutil
from pathlib import Path

from aleph.demo.helpers import create_engine, format_state


def _print_stream(events: list[dict]) -> None:
    for event in events:
        payload = event["payload"]
        if event["event_kind"] == "delta":
            print(f"{event['source']}> {payload['text']}")
        elif event["event_kind"] == "handoff":
            print(f"[handoff] {payload['explanation']}")
            print(payload["handoff_summary"])
        elif event["event_kind"] == "status":
            print(f"[status] {payload['message']}")
        elif event["event_kind"] == "tool_event":
            print(f"[tool] {payload['tool_id']} -> {payload['summary']}")


def main() -> None:
    workspace_tmp = Path.cwd() / ".aleph-tmp" / "scenario-workdir"
    shutil.rmtree(workspace_tmp, ignore_errors=True)
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    engine = create_engine(workspace_tmp)
    try:
        print("Aleph scripted scenario")
        print("-----------------------")
        print(format_state(engine.inspect_state()))

        turns = [
            "请记住，我答应今晚之前给合作方一个版本。",
            "你来拍板并且推进这件事。",
            "我刚才说重了，关系有点僵。",
        ]
        for index, turn in enumerate(turns, start=1):
            print(f"\n=== Turn {index} ===")
            result = engine.process_user_turn(turn)
            _print_stream(result["stream"])

        print("\n=== Final state ===")
        print(format_state(engine.inspect_state()))
    finally:
        engine.store.close()
        shutil.rmtree(workspace_tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
