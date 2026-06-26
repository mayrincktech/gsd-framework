"""
Workflow Guard Client — The bridge between Hermes tools and the Workflow Daemon.

This module is imported by the Hermes patch (patches/apply_workflow_guard.py).
It provides a thin client that talks to the daemon via Unix socket.

If the daemon is not running, the guard is permissive (returns allowed=True).
This ensures Hermes works normally when no GSD workflow is active.
Only when a workflow daemon IS running does enforcement kick in.

Usage from patched Hermes tools:
    from workflow.guard import check_before_delegate, check_before_terminal

    result = check_before_delegate()
    if not result["allowed"]:
        return tool_error(result["reason"])
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from typing import Any, Optional

logger = logging.getLogger("gsd.workflow.guard")

SOCKET_PATH = "/tmp/gsd-workflow.sock"
TIMEOUT = 2.0  # seconds — daemon should respond fast


# ---------------------------------------------------------------------------
# Low-level socket client
# ---------------------------------------------------------------------------

def _send_request(action: str, args: dict | None = None) -> Optional[dict]:
    """
    Send a request to the workflow daemon. Returns response dict or None
    if daemon is not running.
    """
    if not os.path.exists(SOCKET_PATH):
        return None

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect(SOCKET_PATH)
            request = json.dumps({"action": action, "args": args or {}})
            s.sendall((request + "\n").encode("utf-8"))

            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            if not data.strip():
                return None

            return json.loads(data.decode("utf-8").strip())
    except (ConnectionRefusedError, socket.timeout, FileNotFoundError, OSError) as e:
        logger.debug(f"Workflow daemon not reachable: {e}")
        return None
    except Exception as e:
        logger.warning(f"Workflow daemon error: {e}")
        return None


# ---------------------------------------------------------------------------
# Public API — called by Hermes tool patches
# ---------------------------------------------------------------------------

def is_daemon_running() -> bool:
    """Check if the workflow daemon is running."""
    return _send_request("get_state") is not None


def get_current_phase() -> Optional[str]:
    """Return the current GSD phase, or None if no workflow active."""
    resp = _send_request("get_state")
    if resp and resp.get("ok"):
        return resp["data"].get("current_phase")
    return None


def check_tool_permission(tool_name: str, tool_args: dict | None = None) -> dict:
    """
    Check if a tool call is allowed in the current phase.

    Returns:
        {
            "allowed": bool,
            "reason": str (if blocked),
            "current_phase": str | None,
            "daemon_active": bool,
        }
    """
    # If daemon not running, allow everything (Hermes works normally)
    resp = _send_request("check_tool_permission", {
        "tool_name": tool_name,
        "tool_args": tool_args or {},
    })

    if resp is None:
        return {
            "allowed": True,
            "reason": "",
            "current_phase": None,
            "daemon_active": False,
        }

    if not resp.get("ok"):
        # Daemon returned error — fail safe (allow, but log)
        logger.warning(f"Workflow daemon error: {resp.get('error')}")
        return {
            "allowed": True,
            "reason": "",
            "current_phase": None,
            "daemon_active": True,
        }

    data = resp["data"]
    return {
        "allowed": data.get("allowed", True),
        "reason": data.get("reason", ""),
        "current_phase": data.get("current_phase"),
        "daemon_active": True,
    }


def check_before_delegate() -> dict:
    """
    Pre-flight check before delegate_task().

    This is the CRITICAL guard. If this returns allowed=False, delegate_task
    MUST refuse to execute and return the block reason to the LLM.
    """
    return check_tool_permission("delegate_task")


def check_before_terminal(command: str = "") -> dict:
    """
    Pre-flight check before terminal().

    Blocks deploy commands (vercel, git push, etc.) unless in deploy phase.
    """
    # Only check for deploy-sensitive commands
    deploy_patterns = ["vercel deploy", "vercel --prod", "git push heroku"]
    is_deploy_cmd = any(p in command for p in deploy_patterns)

    if is_deploy_cmd:
        return check_tool_permission("terminal", {"command": command, "deploy": True})

    # Non-deploy terminal commands — check general phase permission
    return check_tool_permission("terminal")


def advance_phase() -> dict:
    """
    Advance to the next GSD phase. Called by the orchestrator after gate
    checks pass.

    Returns the gate result with details about what passed/failed.
    """
    resp = _send_request("advance")
    if resp is None:
        return {"ok": False, "error": "Workflow daemon not running"}
    return resp


def check_gate(phase: str | None = None) -> dict:
    """Check the gate for the current (or specified) phase without advancing."""
    resp = _send_request("check_gate", {"phase": phase} if phase else {})
    if resp is None:
        return {"ok": False, "error": "Workflow daemon not running"}
    return resp


def rollback(target_phase: str, reason: str = "") -> dict:
    """Rollback to a target phase."""
    resp = _send_request("rollback", {"target_phase": target_phase, "reason": reason})
    if resp is None:
        return {"ok": False, "error": "Workflow daemon not running"}
    return resp


def set_score(phase: str, score: float) -> dict:
    """Set a score for a phase (e.g., UX Review)."""
    resp = _send_request("set_score", {"phase": phase, "score": score})
    if resp is None:
        return {"ok": False, "error": "Workflow daemon not running"}
    return resp


def get_state() -> dict:
    """Get full workflow state."""
    resp = _send_request("get_state")
    if resp is None:
        return {"ok": False, "error": "Workflow daemon not running"}
    return resp


def get_history() -> dict:
    """Get audit log."""
    resp = _send_request("get_history")
    if resp is None:
        return {"ok": False, "error": "Workflow daemon not running"}
    return resp
