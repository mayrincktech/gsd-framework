"""
Hermes Kanban Bridge — Integrates GSD Workflow Engine with native Hermes Kanban.

Instead of maintaining a separate Kanban board (kanban.py), this module
syncs GSD workflow state to the Hermes native Kanban system via CLI.

Usage:
    from kanban_hermes import HermesKanbanBridge
    
    bridge = HermesKanbanBridge(board="gsd-biblia-ia")
    bridge.create_task("01", "Refactor search page", assignee="default", tags=["frontend"])
    bridge.move_to_in_progress("01")
    bridge.move_to_review("01")
    bridge.move_to_done("01")
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Optional


class HermesKanbanBridge:
    """
    Bridges GSD Workflow Engine phases to Hermes native Kanban.
    
    Hermes Kanban statuses: triage → todo → ready → running → blocked → done → archived
    
    GSD phase mapping:
        research/architecture/ux_design/plan → todo (backlog)
        execute → running (in_progress)
        ux_review/test/verify → running with comment "in review"
        deploy → done
        rollback → ready (re-queue for execution)
    """

    def __init__(self, board: str = "default"):
        self.board = board
        self._task_map: dict[str, str] = {}  # gsd_card_id → hermes_task_id

    def _kanban(self, *args, json_output: bool = False) -> dict:
        """Run hermes kanban command and return parsed JSON."""
        cmd = ["hermes", "kanban", "--board", self.board] + list(args)
        if json_output:
            cmd.append("--json")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                if json_output:
                    try:
                        return json.loads(result.stdout.strip())
                    except json.JSONDecodeError:
                        return {"raw": result.stdout.strip()}
                return {"raw": result.stdout.strip(), "success": True}
            return {"error": result.stderr.strip() or result.stdout.strip()}
        except Exception as e:
            return {"error": str(e)}

    def create_task(
        self,
        card_id: str,
        title: str,
        assignee: str = "default",
        body: str = "",
        tags: list = None,
        parents: list = None,
    ) -> Optional[str]:
        """Create a Hermes Kanban task. Returns task_id (e.g., t_abc123)."""
        args = ["create", title, "--assignee", assignee]
        if body:
            args.extend(["--body", body])
        if parents:
            for p in parents:
                args.extend(["--parent", p])
        
        result = self._kanban(*args, json_output=True)
        task_id = result.get("id") if isinstance(result, dict) else None
        
        if task_id:
            self._task_map[card_id] = task_id
        
        return task_id

    def _update_status(self, task_id: str, action: str, *args) -> bool:
        """Update a task's status via CLI."""
        cmd_args = [action, task_id] + list(args)
        result = self._kanban(*cmd_args)
        return result.get("success", False) or "error" not in result

    def move_to_todo(self, card_id: str) -> bool:
        """Move task to todo status (backlog)."""
        task_id = self._task_map.get(card_id)
        if not task_id:
            return False
        return self._update_status(task_id, "status", "todo")

    def move_to_running(self, card_id: str) -> bool:
        """Move task to running status (in_progress)."""
        task_id = self._task_map.get(card_id)
        if not task_id:
            return False
        # Hermes Kanban moves todo→ready→running via dispatcher,
        # but we can force with 'status' command
        return self._update_status(task_id, "status", "ready")

    def move_to_done(self, card_id: str, summary: str = "") -> bool:
        """Complete a task."""
        task_id = self._task_map.get(card_id)
        if not task_id:
            return False
        args = ["complete", task_id]
        if summary:
            args.extend(["--result", summary])
        result = self._kanban(*args)
        return "error" not in result

    def add_comment(self, card_id: str, comment: str) -> bool:
        """Add a comment to a task."""
        task_id = self._task_map.get(card_id)
        if not task_id:
            return False
        result = self._kanban("comment", task_id, comment)
        return "error" not in result

    def block(self, card_id: str, reason: str) -> bool:
        """Block a task."""
        task_id = self._task_map.get(card_id)
        if not task_id:
            return False
        result = self._kanban("block", task_id, "--reason", reason)
        return "error" not in result

    def unblock(self, card_id: str) -> bool:
        """Unblock a task."""
        task_id = self._task_map.get(card_id)
        if not task_id:
            return False
        result = self._kanban("unblock", task_id)
        return "error" not in result

    # ── Phase-driven auto-transitions ──────────────────────────────

    PHASE_ACTIONS = {
        "research": "todo",
        "architecture": "todo",
        "ux_design": "todo",
        "plan": "todo",
        "execute": "running",
        "ux_review": "comment",
        "test": "comment",
        "verify": "comment",
        "deploy": "done",
        "done": "done",
    }

    def on_phase_change(self, new_phase: str, reason: str = "", is_rollback: bool = False):
        """
        Auto-transition all tracked tasks when the workflow phase changes.
        """
        action = self.PHASE_ACTIONS.get(new_phase, "")
        
        if not action:
            return

        if is_rollback:
            for card_id in list(self._task_map.keys()):
                self.move_to_running(card_id)
                self.add_comment(card_id, f"🔄 Rollback: {reason}")
            return

        if action == "running":
            for card_id in list(self._task_map.keys()):
                self.move_to_running(card_id)

        elif action == "comment":
            for card_id in list(self._task_map.keys()):
                self.add_comment(card_id, f"📋 Phase: {new_phase}")

        elif action == "done":
            for card_id in list(self._task_map.keys()):
                self.move_to_done(card_id, summary=f"Completed in phase {new_phase}")

    def list_tasks(self) -> list:
        """List all tasks on the board."""
        result = self._kanban("list")
        if isinstance(result, dict) and "tasks" in result:
            return result["tasks"]
        return []

    def get_stats(self) -> dict:
        """Get board statistics."""
        result = self._kanban("stats")
        return result if isinstance(result, dict) else {}
