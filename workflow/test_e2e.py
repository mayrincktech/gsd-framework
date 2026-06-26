#!/usr/bin/env python3
"""
GSD Workflow Engine — End-to-End Test

Demonstrates:
1. Daemon starts in background
2. delegate_task is BLOCKED in research phase
3. Gate blocks advance without RESEARCH.md
4. Gate allows advance WITH RESEARCH.md
5. Full pipeline progression to execute phase
6. delegate_task ALLOWED in execute phase
7. UX Review score < 42 blocks advance
8. UX Review score >= 42 allows advance
9. Rollback invalidates downstream artifacts
10. LLM bypass attempt (edit state.json) → HMAC mismatch detected
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── Setup ──────────────────────────────────────────────────────────────

FRAMEWORK = Path.home() / "workspace" / "hermes-gsd-framework"
WORKFLOW_YAML = FRAMEWORK / "workflow" / "gsd-workflow.yaml"
DAEMON_SCRIPT = FRAMEWORK / "workflow" / "daemon.py"
GUARD_SCRIPT = FRAMEWORK / "workflow" / "guard.py"

SOCKET = "/tmp/gsd-workflow-test.sock"
PROJECT_DIR = tempfile.mkdtemp(prefix="gsd-test-")

passed = 0
failed = 0


def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    status = "✅ PASS" if condition else "❌ FAIL"
    print(f"  {status}: {name}" + (f" — {detail}" if detail else ""))
    if condition:
        passed += 1
    else:
        failed += 1


def socket_send(action: str, args: dict = None) -> dict:
    """Send request to daemon via Unix socket."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect(SOCKET)
    req = json.dumps({"action": action, "args": args or {}})
    s.sendall((req + "\n").encode())
    data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
        if b"\n" in data:
            break
    s.close()
    return json.loads(data.decode().strip())


# ── 1. Start daemon ────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  GSD WORKFLOW ENGINE — END-TO-END TEST")
print("=" * 60)

print(f"\nProject dir: {PROJECT_DIR}")
os.makedirs(PROJECT_DIR, exist_ok=True)

# Clean stale socket
if os.path.exists(SOCKET):
    os.unlink(SOCKET)

print("Starting daemon...")
daemon_proc = subprocess.Popen(
    [
        sys.executable, str(DAEMON_SCRIPT),
        "--project-dir", PROJECT_DIR,
        "--workflow", str(WORKFLOW_YAML),
        "--socket", SOCKET,
        "--foreground",
    ],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
time.sleep(1.5)

if daemon_proc.poll() is not None:
    print(f"❌ Daemon failed to start! Output: {daemon_proc.stdout.read().decode()}")
    sys.exit(1)

test("Daemon starts and listens on socket", os.path.exists(SOCKET))


# ── 2. Initialize workflow ─────────────────────────────────────────────

print("\n── Phase 1: Initialize ──────────────────────────────")

r = socket_send("start")
test("Workflow starts at 'research' phase",
     r["ok"] and r["data"]["phase"] == "research",
     f"phase={r.get('data', {}).get('phase')}")


# ── 3. delegate_task BLOCKED in research ───────────────────────────────

print("\n── Phase 2: Tool Guard (delegate_task blocked) ─────")

r = socket_send("check_tool_permission", {"tool_name": "delegate_task"})
test("delegate_task BLOCKED in research phase",
     not r["data"]["allowed"],
     f"reason: {r['data'].get('reason', '')[:60]}")

r = socket_send("check_tool_permission", {"tool_name": "read_file"})
test("read_file ALLOWED in research phase",
     r["data"]["allowed"])


# ── 4. Gate blocks advance without artifacts ───────────────────────────

print("\n── Phase 3: Gate Enforcement ────────────────────────")

r = socket_send("advance")
test("Advance BLOCKED without RESEARCH.md",
     not r["ok"] and "RESEARCH.md" in str(r["data"].get("missing_artifacts", [])),
     f"missing: {r['data'].get('missing_artifacts', [])}")


# ── 5. Create artifacts and advance through pipeline ──────────────────

print("\n── Phase 4: Pipeline Progression ────────────────────")

artifacts = {
    "RESEARCH.md": "BUILD — Market demand validated through competitor analysis. "
                   "Clear gap in the market. Recommendation: BUILD.\n" * 3,
    "ARCHITECTURE.md": "Stack: Next.js 16 + Drizzle + Neon pgvector\n"
                       "Database: Neon Postgres\n"
                       "API: REST with server actions\n"
                       "Auth: Built-in JWT\n" * 2,
    "DESIGN-SYSTEM.md": "Colors: Indigo primary, gray neutrals\n"
                        "Typography: Inter, 16px base\n"
                        "Spacing: 8px scale\n"
                        "Border Radius: 16px cards, 8px inputs\n",
    "WIREFRAMES.md": "Mobile-first 375px\n"
                     "┌─────────────────────┐\n"
                     "│ ☰  App       👤     │\n"
                     "├─────────────────────┤\n"
                     "│                     │\n"
                     "│  ┌───────────────┐  │\n"
                     "│  │   Content     │  │\n"
                     "│  └───────────────┘  │\n"
                     "└─────────────────────┘\n",
    "PLAN.md": "Task 01: Database schema\n"
              "Task 02: API routes\n"
              "Task 03: UI components\n"
              "Wave 1: Tasks 01-02 (parallel)\n"
              "Wave 2: Task 03 (depends on 01+02)\n",
}

for name, content in artifacts.items():
    Path(PROJECT_DIR, name).write_text(content)

# Set kanban cards
socket_send("set_metadata", {"phase": "plan", "key": "kanban_cards_created", "value": 3})

# Advance through: research → architecture → ux_design → plan → execute
phases_expected = ["architecture", "ux_design", "plan", "execute"]
for expected in phases_expected:
    r = socket_send("advance")
    test(f"Advance to '{expected}'",
         r["ok"] and r["data"]["phase"] == expected,
         r["data"].get("message", "")[:60])


# ── 6. delegate_task ALLOWED in execute ────────────────────────────────

print("\n── Phase 5: Tool Guard (delegate_task allowed) ─────")

r = socket_send("check_tool_permission", {"tool_name": "delegate_task"})
test("delegate_task ALLOWED in execute phase",
     r["data"]["allowed"],
     f"phase={r['data'].get('current_phase')}")

# Terminal (deploy) should still be blocked
r = socket_send("check_tool_permission", {"tool_name": "terminal", "tool_args": {"command": "vercel deploy --prod"}})
test("Deploy command BLOCKED in execute phase",
     not r["data"]["allowed"])


# ── 7. UX Review score gate ────────────────────────────────────────────

print("\n── Phase 6: UX Review Score Gate ────────────────────")

# Advance to ux_review
r = socket_send("advance")
test("Advance to 'ux_review'", r["ok"])

# Set LOW score → advance should fail
socket_send("set_score", {"phase": "ux_review", "score": 35})
r = socket_send("advance")
test("UX Review score 35/60 BLOCKS advance (min 42)",
     not r["ok"],
     f"failed_checks: {r['data'].get('failed_checks', [])[:1]}")

# Set GOOD score → advance should pass
socket_send("set_score", {"phase": "ux_review", "score": 48})
r = socket_send("advance")
test("UX Review score 48/60 ALLOWS advance",
     r["ok"],
     r["data"].get("message", "")[:60])


# ── 8. Rollback with cascade invalidation ──────────────────────────────

print("\n── Phase 7: Rollback + Cascade ──────────────────────")

# We're in 'test' phase now. Rollback to execute
r = socket_send("rollback", {"target_phase": "execute", "reason": "build failed"})
test("Rollback to 'execute' succeeds",
     r["ok"],
     r["data"].get("message", "")[:60])

# Verify ux_review and test are invalidated
state = socket_send("get_state")["data"]
ux_status = state["phases"]["ux_review"]["status"]
test_status = state["phases"]["test"]["status"]
test("ux_review INVALIDATED after rollback", ux_status == "invalidated", f"status={ux_status}")
test("test INVALIDATED after rollback", test_status == "invalidated", f"status={test_status}")

# Verify current phase is execute
test("Current phase is 'execute' after rollback", state["current_phase"] == "execute")


# ── 9. HMAC tamper detection ───────────────────────────────────────────

print("\n── Phase 8: Tamper Detection ────────────────────────")

state_file = Path(PROJECT_DIR, "workflow-state.json")
if state_file.exists():
    # Read original
    original = state_file.read_text()
    # Tamper: change current_phase to "deploy" (bypass!)
    data = json.loads(original)
    data["current_phase"] = "deploy"
    state_file.write_text(json.dumps(data))

    # Verify integrity
    r = socket_send("verify_integrity")
    test("Tampered state.json DETECTED by HMAC",
         not r["data"]["intact"],
         f"intact={r['data']['intact']}")

    # Restore
    state_file.write_text(original)
else:
    test("State file exists for tamper test", False, "No state file")


# ── 10. Audit trail ────────────────────────────────────────────────────

print("\n── Phase 9: Audit Trail ─────────────────────────────")

history = socket_send("get_history")["data"]
test("Audit trail has 5+ entries", len(history) >= 5, f"entries={len(history)}")

actions = [h["action"] for h in history]
test("Audit trail includes 'start'", "start" in actions)
test("Audit trail includes 'advance'", "advance" in actions)
test("Audit trail includes 'rollback'", "rollback" in actions)


# ── Cleanup ────────────────────────────────────────────────────────────

daemon_proc.terminate()
daemon_proc.wait()
if os.path.exists(SOCKET):
    os.unlink(SOCKET)
shutil.rmtree(PROJECT_DIR, ignore_errors=True)


# ── Summary ────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
total = passed + failed
print(f"  RESULTS: {passed}/{total} passed")
if failed:
    print(f"  {failed} FAILED")
else:
    print("  🎉 ALL TESTS PASSED")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
