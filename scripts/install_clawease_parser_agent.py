from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(r"E:\aNB\Ease-claw")
CONFIG_PATH = Path(r"C:\Users\ZHUyi\.openclaw\openclaw.json")
WORKSPACE = ROOT / "openclaw" / "clawease-intent-workspace"
AGENT_DIR = Path(r"C:\Users\ZHUyi\.openclaw\agents\clawease-intent\agent")
SYSTEM_PROMPT_PATH = ROOT / "openclaw" / "clawease-intent-system-prompt.txt"


def main() -> int:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"OpenClaw config not found: {CONFIG_PATH}")
    if not WORKSPACE.exists():
        raise SystemExit(f"Parser workspace not found: {WORKSPACE}")
    if not SYSTEM_PROMPT_PATH.exists():
        raise SystemExit(f"System prompt file not found: {SYSTEM_PROMPT_PATH}")

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg.setdefault("agents", {})
    cfg["agents"].setdefault("defaults", {})
    cfg["agents"].setdefault("list", [])

    prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    agents = cfg["agents"]["list"]
    agent = next((entry for entry in agents if entry.get("id") == "clawease-intent"), None)
    if agent is None:
        agent = {
            "id": "clawease-intent",
            "name": "clawease-intent",
            "workspace": str(WORKSPACE),
            "agentDir": str(AGENT_DIR),
            "model": "google/gemini-2.5-flash",
            "systemPromptOverride": prompt,
        }
        agents.append(agent)
    else:
        agent["workspace"] = str(WORKSPACE)
        agent["agentDir"] = str(AGENT_DIR)
        agent["model"] = "google/gemini-2.5-flash"
        agent["systemPromptOverride"] = prompt

    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[clawease-parser] installed into {CONFIG_PATH}")
    print("[clawease-parser] agent id: clawease-intent")
    print(f"[clawease-parser] workspace: {WORKSPACE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
