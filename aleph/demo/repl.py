from __future__ import annotations

from pathlib import Path

from aleph.demo.helpers import create_engine, format_state


def main() -> None:
    engine = create_engine(Path.cwd())
    print("Aleph REPL")
    print("Type /clients, /state, /switch <id>, or /quit")
    print(format_state(engine.inspect_state()))
    try:
        while True:
            line = input("\nYou> ").strip()
            if not line:
                continue
            if line in {"/quit", "/exit"}:
                break
            if line == "/clients":
                for client in engine.list_clients():
                    domains = ", ".join(client["declared_capability"].get("domains", []))
                    print(f"- {client['id']}: {client['display_name']} | domains={domains}")
                continue
            if line == "/state":
                print(format_state(engine.inspect_state()))
                continue
            if line.startswith("/switch "):
                target = line[len("/switch ") :].strip()
                events = engine.edge_gateway.submit_text(f"switch to {target}", requested_client_id=target)
            else:
                events = engine.edge_gateway.submit_text(line)

            for event in events:
                payload = event["payload"]
                if event["event_kind"] == "delta":
                    print(f"{event['source']}> {payload['text']}")
                elif event["event_kind"] == "status":
                    print(f"[status] {payload['message']}")
                elif event["event_kind"] == "handoff":
                    print(f"[handoff] {payload['explanation']}")
                elif event["event_kind"] == "tool_event":
                    print(f"[tool] {payload['summary']}")
    finally:
        engine.store.close()
