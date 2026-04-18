from __future__ import annotations

import shutil
from pathlib import Path

from aleph.demo.helpers import create_engine, format_state


def _print_turn(label: str, result: dict) -> None:
    print(f"\n=== {label} ===")
    print(f"Active persona: {result['active_client_name']} ({result['active_persona_id']})")
    switch_decision = result.get("switch_decision")
    if switch_decision and switch_decision.get("approved"):
        print(f"Switch: {switch_decision['explanation']}")
        print(switch_decision["handoff_summary"])
    print(f"Reply: {result['reply']}")


def main() -> None:
    workspace_tmp = Path.cwd() / ".aleph-tmp" / "scenario-workdir"
    shutil.rmtree(workspace_tmp, ignore_errors=True)
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    root_dir = workspace_tmp
    engine = create_engine(root_dir)
    try:
        print("Aleph scripted scenario")
        print("-----------------------")
        print(format_state(engine.inspect_state()))

        first = engine.process_user_turn("我刚刚答应合作方今晚之前给他回一版方案，但我现在开始慌了。")
        _print_turn("Turn 1", first)

        second = engine.process_user_turn("你来拍板并接管吧，我们必须推进，不然这个承诺会失控。")
        _print_turn("Turn 2", second)

        third = engine.process_user_turn("另外我刚刚说重了话，关系有点僵，这件事不会因为换人就消失。")
        _print_turn("Turn 3", third)

        print("\n=== Final state ===")
        print(format_state(engine.inspect_state()))
    finally:
        engine.store.close()
        shutil.rmtree(root_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
