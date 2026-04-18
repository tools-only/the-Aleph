from __future__ import annotations

from pathlib import Path

from aleph.demo.helpers import create_engine, format_state


def main() -> None:
    engine = create_engine(Path.cwd())
    print("Aleph REPL")
    print("Type /clients, /personas, /switch <id>, /state, or /quit")
    print(format_state(engine.inspect_state()))
    try:
        while True:
            line = input("\nYou> ").strip()
            if not line:
                continue
            if line in {"/quit", "/exit"}:
                break
            if line in {"/clients", "/personas"}:
                for client in engine.list_clients():
                    print(
                        f"- {client['id']}: {client['display_name']} | "
                        f"specialties={', '.join(client['specialties'])} | "
                        f"shared={', '.join(client['shared_domains'])}"
                    )
                continue
            if line == "/state":
                print(format_state(engine.inspect_state()))
                continue
            if line.startswith("/switch "):
                target = line[len("/switch ") :].strip()
                result = engine.process_user_turn(
                    f"Foreground handoff requested to {target}.",
                    requested_client_id=target,
                )
                print(f"{result['active_client_name']}> {result['reply']}")
                switch_decision = result.get("switch_decision")
                if switch_decision and switch_decision.get("approved"):
                    print(switch_decision["explanation"])
                continue

            result = engine.process_user_turn(line)
            print(f"{result['active_client_name']}> {result['reply']}")
            switch_decision = result.get("switch_decision")
            if switch_decision and switch_decision.get("approved"):
                print(switch_decision["explanation"])
    finally:
        engine.store.close()


if __name__ == "__main__":
    main()
