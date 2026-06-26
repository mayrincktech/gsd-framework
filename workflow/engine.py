"""
GSD Workflow Engine — Generic State Machine + Gate Verifier

This is the core runtime that enforces process compliance. It is completely
GSD-agnostic — it reads a YAML workflow definition and enforces it.

Key properties:
- State lives in memory (daemon mode) or JSON file (embedded mode)
- State transitions are validated against the YAML definition
- Gates check artifact existence + content criteria
- Rollback invalidates downstream artifacts via dependency DAG
- The LLM cannot edit state directly — only through advance()/rollback()

Usage (embedded):
    from workflow.engine import WorkflowEngine
    engine = WorkflowEngine("gsd-workflow.yaml", project_dir=".planning")
    engine.start()          # initialize phase 0
    engine.advance()        # try to advance to next phase (checks gate)
    engine.get_state()      # current phase + metadata
    engine.rollback("qa")   # rollback to a phase, invalidating downstream

Usage (daemon):
    See workflow/daemon.py — runs engine in a separate process,
    communicating via Unix socket. The LLM has no filesystem access
    to the state, only an API client.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import yaml


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class PhaseState:
    """Tracks the state of a single phase."""
    phase_id: str
    status: str = "pending"  # pending | active | passed | failed | invalidated
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    artifacts: dict = field(default_factory=dict)  # artifact_path -> {hash, valid}
    score: Optional[float] = None  # for score-based gates (UX Review)
    metadata: dict = field(default_factory=dict)  # freeform per-phase data


@dataclass
class WorkflowState:
    """Full workflow state — serialized to JSON or kept in daemon memory."""
    workflow_id: str
    project_dir: str
    current_phase: str
    phases: dict[str, PhaseState] = field(default_factory=dict)
    history: list = field(default_factory=list)  # audit trail of all transitions
    created_at: float = field(default_factory=time.time)
    hmac_key: Optional[str] = None  # if set, state JSON is signed

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "project_dir": self.project_dir,
            "current_phase": self.current_phase,
            "phases": {k: asdict(v) for k, v in self.phases.items()},
            "history": self.history,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        phases = {}
        for pid, pdata in data.get("phases", {}).items():
            phases[pid] = PhaseState(**pdata)
        return cls(
            workflow_id=data["workflow_id"],
            project_dir=data["project_dir"],
            current_phase=data["current_phase"],
            phases=phases,
            history=data.get("history", []),
            created_at=data.get("created_at", time.time()),
        )


# ---------------------------------------------------------------------------
# Gate Verification Result
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Result of a gate check."""
    passed: bool
    phase: str
    missing_artifacts: list = field(default_factory=list)
    invalid_artifacts: list = field(default_factory=list)
    score: Optional[float] = None
    min_score: Optional[float] = None
    failed_checks: list = field(default_factory=list)
    message: str = ""

    def summary(self) -> str:
        if self.passed:
            return f"✅ Gate PASSED for phase '{self.phase}'"
        parts = [f"❌ Gate FAILED for phase '{self.phase}'"]
        if self.missing_artifacts:
            parts.append(f"  Missing artifacts: {', '.join(self.missing_artifacts)}")
        if self.invalid_artifacts:
            parts.append(f"  Invalid artifacts: {', '.join(self.invalid_artifacts)}")
        if self.score is not None and self.min_score is not None:
            parts.append(f"  Score: {self.score}/{self.min_score} (below minimum)")
        for check in self.failed_checks:
            parts.append(f"  Failed: {check}")
        if self.message:
            parts.append(f"  Note: {self.message}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Workflow Engine
# ---------------------------------------------------------------------------

class WorkflowEngine:
    """
    Generic state machine that enforces a workflow defined in YAML.

    The engine does NOT know about GSD. It reads any workflow YAML and
    enforces it. This makes it reusable for any methodology.
    """

    def __init__(
        self,
        workflow_yaml_path: str | Path,
        project_dir: str | Path = ".",
        state: Optional[WorkflowState] = None,
    ):
        self.workflow_yaml_path = Path(workflow_yaml_path)
        self.project_dir = Path(project_dir)
        self.definition = self._load_yaml()
        self.phases: list[dict] = self.definition.get("phases", [])
        self.phase_map: dict[str, dict] = {p["id"]: p for p in self.phases}
        self.phase_order = [p["id"] for p in self.phases]

        # Build dependency DAG for rollback cascade
        self._dependency_graph = self._build_dependency_graph()

        self.state = state or self._load_state()

    # ── YAML Loading ──────────────────────────────────────────────────

    def _load_yaml(self) -> dict:
        with open(self.workflow_yaml_path) as f:
            data = yaml.safe_load(f)
        if not data or "phases" not in data:
            raise ValueError(f"Invalid workflow YAML: {self.workflow_yaml_path}")
        return data

    def _build_dependency_graph(self) -> dict[str, list[str]]:
        """Build a DAG: artifact -> list of phases that depend on it."""
        graph: dict[str, list[str]] = {}
        for phase in self.phases:
            for artifact in phase.get("produces", []):
                graph.setdefault(artifact, [])
            for dep in phase.get("depends_on", []):
                # dep is a phase id — find its produces
                dep_phase = self.phase_map.get(dep, {})
                for artifact in dep_phase.get("produces", []):
                    graph.setdefault(artifact, []).append(phase["id"])
        return graph

    # ── State Management ──────────────────────────────────────────────

    def _state_file(self) -> Path:
        return self.project_dir / "workflow-state.json"

    def _load_state(self) -> WorkflowState:
        sf = self._state_file()
        if sf.exists():
            data = json.loads(sf.read_text())
            return WorkflowState.from_dict(data)
        # Fresh state — not yet started
        return WorkflowState(
            workflow_id=self.definition.get("workflow", "unknown"),
            project_dir=str(self.project_dir),
            current_phase="",
        )

    def _save_state(self):
        """Save state to JSON. In daemon mode, this is in-memory only."""
        sf = self._state_file()
        sf.parent.mkdir(parents=True, exist_ok=True)
        data = self.state.to_dict()
        # Sign if HMAC key is set
        if self.state.hmac_key:
            payload = json.dumps(data, sort_keys=True)
            sig = hmac.new(
                self.state.hmac_key.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()
            data["_hmac"] = sig
        sf.write_text(json.dumps(data, indent=2))

    def _verify_hmac(self, data: dict) -> bool:
        """Verify state integrity."""
        if not self.state.hmac_key:
            return True
        sig = data.pop("_hmac", None)
        if not sig:
            return False
        payload = json.dumps(data, sort_keys=True)
        expected = hmac.new(
            self.state.hmac_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(sig, expected)

    # ── Lifecycle ─────────────────────────────────────────────────────

    def start(self) -> GateResult:
        """Initialize the workflow — set first phase as active."""
        if not self.phases:
            return GateResult(
                passed=False, phase="init",
                message="No phases defined in workflow YAML.",
            )
        first = self.phases[0]
        self.state.current_phase = first["id"]
        for p in self.phases:
            self.state.phases[p["id"]] = PhaseState(phase_id=p["id"])
        self.state.phases[first["id"]].status = "active"
        self.state.phases[first["id"]].started_at = time.time()
        self._log("start", first["id"])
        self._save_state()
        return GateResult(passed=True, phase=first["id"], message="Workflow started.")

    def get_state(self) -> dict:
        """Return current workflow state (read-only)."""
        return self.state.to_dict()

    def get_current_phase(self) -> dict:
        """Return the current phase definition + state."""
        pid = self.state.current_phase
        phase_def = self.phase_map.get(pid, {})
        phase_state = self.state.phases.get(pid)
        return {
            "definition": phase_def,
            "state": asdict(phase_state) if phase_state else None,
        }

    # ── Gate Verification ─────────────────────────────────────────────

    def check_gate(self, phase_id: Optional[str] = None) -> GateResult:
        """
        Check if the gate for the given phase (or current phase) passes.

        Gate types:
        - artifact_check: required files must exist
        - score_check: a score field must meet minimum
        - command_check: shell commands must pass (evaluated externally)
        - composite: multiple checks combined
        """
        pid = phase_id or self.state.current_phase
        phase = self.phase_map.get(pid)
        if not phase:
            return GateResult(
                passed=False, phase=pid,
                message=f"Unknown phase: {pid}",
            )

        gate = phase.get("gate", {})
        gate_type = gate.get("type", "artifact_check")
        result = GateResult(passed=True, phase=pid)

        if gate_type in ("artifact_check", "composite"):
            required = gate.get("requires", [])
            for artifact in required:
                path = self.project_dir / artifact
                if not path.exists():
                    result.missing_artifacts.append(artifact)
                    result.passed = False

        if gate_type in ("score_check", "composite"):
            min_score = gate.get("min_score")
            phase_state = self.state.phases.get(pid)
            score = phase_state.score if phase_state else None
            if min_score is not None:
                if score is None:
                    result.failed_checks.append(
                        f"No score recorded for phase '{pid}' "
                        f"(minimum: {min_score})"
                    )
                    result.passed = False
                    result.min_score = min_score
                elif score < min_score:
                    result.passed = False
                    result.score = score
                    result.min_score = min_score
                    result.failed_checks.append(
                        f"Score {score} below minimum {min_score}"
                    )

        if gate_type in ("kanban_check", "composite"):
            min_cards = gate.get("kanban_cards", 0)
            if min_cards > 0:
                phase_state = self.state.phases.get(pid)
                actual_cards = phase_state.metadata.get("kanban_cards_created", 0) if phase_state else 0
                if actual_cards < min_cards:
                    result.failed_checks.append(
                        f"Kanban: {actual_cards} cards created, need {min_cards}"
                    )
                    result.passed = False

        if gate_type == "command_check":
            # Commands are evaluated externally — just check if results exist
            phase_state = self.state.phases.get(pid)
            cmd_results = phase_state.metadata.get("command_results", {}) if phase_state else {}
            commands = gate.get("commands", [])
            all_must_pass = gate.get("all_must_pass", True)
            any_passed = False
            for cmd in commands:
                if cmd in cmd_results:
                    if cmd_results[cmd]:
                        any_passed = True
                    else:
                        if all_must_pass:
                            result.failed_checks.append(f"Command failed: {cmd}")
                            result.passed = False
                else:
                    result.failed_checks.append(f"Command not run: {cmd}")
                    result.passed = False

        return result

    # ── Phase Transitions ─────────────────────────────────────────────

    def advance(self) -> GateResult:
        """
        Attempt to advance to the next phase.

        First checks if the current phase's gate passes.
        If it does, marks current as passed and activates next phase.
        If it doesn't, returns the failure with details.
        """
        if not self.state.current_phase:
            return self.start()

        # Check current phase gate
        result = self.check_gate()
        if not result.passed:
            self.state.phases[self.state.current_phase].status = "failed"
            self._save_state()
            return result

        # Mark current as passed
        cur = self.state.current_phase
        self.state.phases[cur].status = "passed"
        self.state.phases[cur].completed_at = time.time()

        # Find next phase
        idx = self.phase_order.index(cur)
        if idx + 1 >= len(self.phase_order):
            self._log("complete", cur)
            self._save_state()
            return GateResult(
                passed=True, phase=cur,
                message="Workflow COMPLETE — all phases passed.",
            )

        next_pid = self.phase_order[idx + 1]
        self.state.current_phase = next_pid
        self.state.phases[next_pid].status = "active"
        self.state.phases[next_pid].started_at = time.time()
        self._log("advance", next_pid)
        self._save_state()

        return GateResult(
            passed=True, phase=next_pid,
            message=f"Advanced to phase '{next_pid}'.",
        )

    def set_score(self, phase_id: str, score: float):
        """Set a score for a phase (e.g., UX Review score)."""
        if phase_id in self.state.phases:
            self.state.phases[phase_id].score = score
            self._save_state()

    def set_metadata(self, phase_id: str, key: str, value: Any):
        """Set metadata for a phase."""
        if phase_id not in self.state.phases:
            self.state.phases[phase_id] = PhaseState(phase_id=phase_id)
        self.state.phases[phase_id].metadata[key] = value
        self._save_state()

    def record_command_result(self, phase_id: str, command: str, passed: bool):
        """Record the result of a command check."""
        if phase_id not in self.state.phases:
            self.state.phases[phase_id] = PhaseState(phase_id=phase_id)
        self.state.phases[phase_id].metadata.setdefault("command_results", {})[command] = passed
        self._save_state()

    # ── Rollback ──────────────────────────────────────────────────────

    def rollback(self, target_phase: str, reason: str = "") -> GateResult:
        """
        Rollback to a target phase, invalidating all phases after it.

        Uses the dependency DAG to determine which artifacts to invalidate.
        Respects preserve lists in rollback policies.
        """
        if target_phase not in self.phase_map:
            return GateResult(
                passed=False, phase=target_phase,
                message=f"Unknown phase: {target_phase}",
            )

        target_idx = self.phase_order.index(target_phase)
        cur_idx = self.phase_order.index(self.state.current_phase)

        if target_idx > cur_idx:
            return GateResult(
                passed=False, phase=target_phase,
                message="Cannot rollback forward — use advance() instead.",
            )

        # Collect phases to invalidate (everything after target)
        to_invalidate = self.phase_order[target_idx + 1: cur_idx + 1]

        # Check for conditional rollback policy
        cur_phase_def = self.phase_map.get(self.state.current_phase, {})
        rollback_policy = cur_phase_def.get("rollback", {})

        # Conditional rollback (e.g., architecture_drift → deeper rollback)
        conditionals = rollback_policy.get("conditional", [])
        for cond in conditionals:
            trigger = cond.get("trigger", "")
            # Simple matching — if reason contains trigger keyword
            if trigger.lower() in reason.lower():
                target_phase = cond.get("target", target_phase)
                target_idx = self.phase_order.index(target_phase)
                to_invalidate = self.phase_order[target_idx + 1:]
                break

        # Preserve list — phases whose artifacts stay valid
        preserve = set(rollback_policy.get("preserve", []))

        # Invalidate phases
        invalidated = []
        for pid in to_invalidate:
            phase_def = self.phase_map.get(pid, {})
            # Skip if explicitly preserved
            if pid in preserve:
                continue
            # Mark as invalidated
            if pid in self.state.phases:
                self.state.phases[pid].status = "invalidated"
                self.state.phases[pid].score = None
                # Clear command results
                self.state.phases[pid].metadata.pop("command_results", None)
            invalidated.append(pid)

        # Set target as active again
        for pid in to_invalidate:
            if pid not in preserve:
                self.state.phases[pid].status = "invalidated"

        # Reset target phase to active
        target_phase_def = self.phase_map.get(target_phase, {})
        # If target was "passed", we need to re-run it
        self.state.phases[target_phase].status = "active"
        self.state.phases[target_phase].started_at = time.time()
        self.state.phases[target_phase].completed_at = None
        self.state.current_phase = target_phase

        self._log("rollback", target_phase, {
            "reason": reason,
            "invalidated": invalidated,
        })
        self._save_state()

        return GateResult(
            passed=True, phase=target_phase,
            message=f"Rolled back to '{target_phase}'. Invalidated: {', '.join(invalidated)}",
        )

    # ── Tool Guard Query ──────────────────────────────────────────────

    def check_tool_permission(self, tool_name: str, tool_args: dict | None = None) -> dict:
        """
        Check if a tool call is permitted in the current phase.

        Returns dict with:
        - allowed: bool
        - reason: str (if blocked)
        - current_phase: str
        """
        phase_def = self.phase_map.get(self.state.current_phase, {})
        allowed_tools = phase_def.get("allowed_tools", [])
        blocked_tools = phase_def.get("blocked_tools", [])

        # If no tool restrictions defined for this phase, allow all
        if not allowed_tools and not blocked_tools:
            return {"allowed": True, "current_phase": self.state.current_phase}

        # Check blocklist first
        if tool_name in blocked_tools:
            return {
                "allowed": False,
                "reason": f"Tool '{tool_name}' is blocked in phase '{self.state.current_phase}'",
                "current_phase": self.state.current_phase,
            }

        # Check allowlist (if defined, only listed tools pass)
        if allowed_tools and tool_name not in allowed_tools:
            return {
                "allowed": False,
                "reason": (
                    f"Tool '{tool_name}' is not allowed in phase "
                    f"'{self.state.current_phase}'. Allowed: {', '.join(allowed_tools)}"
                ),
                "current_phase": self.state.current_phase,
            }

        # Deploy-command guard: block deploy commands unless in deploy phase
        if tool_name == "terminal" and self.state.current_phase != "deploy":
            cmd = (tool_args or {}).get("command", "")
            is_deploy = any(p in cmd for p in [
                "vercel deploy", "vercel --prod", "git push heroku",
                "fly deploy", "railway up",
            ])
            if is_deploy:
                return {
                    "allowed": False,
                    "reason": (
                        f"Deploy commands are blocked in phase '{self.state.current_phase}'. "
                        f"Deploy is only allowed in the 'deploy' phase."
                    ),
                    "current_phase": self.state.current_phase,
                }

        return {"allowed": True, "current_phase": self.state.current_phase}

    # ── Audit Log ─────────────────────────────────────────────────────

    def _log(self, action: str, phase: str, extra: dict | None = None):
        entry = {
            "timestamp": time.time(),
            "action": action,  # start | advance | rollback | complete
            "phase": phase,
        }
        if extra:
            entry.update(extra)
        self.state.history.append(entry)

    def get_history(self) -> list:
        return self.state.history

    # ── HMAC ──────────────────────────────────────────────────────────

    def set_hmac_key(self, key: str):
        """Set HMAC key for state signing (tamper detection)."""
        self.state.hmac_key = key
        self._save_state()

    def verify_integrity(self) -> bool:
        """Verify that state.json hasn't been tampered with."""
        sf = self._state_file()
        if not sf.exists():
            return True  # No state = nothing to verify
        data = json.loads(sf.read_text())
        return self._verify_hmac(data)
