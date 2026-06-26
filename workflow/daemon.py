"""
Workflow Daemon — Process-isolated state machine server.

Runs as a SEPARATE process from the Hermes agent. The LLM cannot access
the state directly — it can only interact through this daemon's Unix socket API.

This is the critical security boundary:
- State lives in daemon memory (not a file the LLM can edit)
- HMAC key is generated at daemon startup (not visible to LLM)
- The LLM can only call: get_state, advance, rollback, set_score, check_tool_permission
- The LLM CANNOT: edit state.json, kill the daemon, or bypass the socket API

Starting:
    python3 workflow/daemon.py --project-dir .planning --workflow workflow/gsd-workflow.yaml

Socket: /tmp/gsd-workflow.sock (configurable via --socket)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

# Allow importing engine.py from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from engine import WorkflowEngine, GateResult

logger = logging.getLogger("gsd.workflow.daemon")

SOCKET_PATH = "/tmp/gsd-workflow.sock"
BUFFER_SIZE = 65536  # 64KB — state is small, but history can grow


class WorkflowDaemon:
    """
    Holds the WorkflowEngine instance and handles requests via Unix socket.

    Each request is a JSON object with:
    - "action": one of the API methods
    - "args": dict of arguments

    Response is JSON with:
    - "ok": bool
    - "data": result data (if ok)
    - "error": error message (if not ok)
    """

    def __init__(
        self,
        workflow_yaml: str,
        project_dir: str,
        socket_path: str = SOCKET_PATH,
    ):
        # Generate HMAC key — only lives in this process
        self.hmac_key = secrets.token_hex(32)

        self.engine = WorkflowEngine(
            workflow_yaml_path=workflow_yaml,
            project_dir=project_dir,
        )
        self.engine.set_hmac_key(self.hmac_key)
        self.socket_path = socket_path
        self._lock = threading.Lock()

    def handle_request(self, request: dict) -> dict:
        """Process a single API request. Thread-safe."""
        action = request.get("action")
        args = request.get("args", {})

        with self._lock:
            handler = getattr(self, f"_api_{action}", None)
            if not handler:
                return {"ok": False, "error": f"Unknown action: {action}"}

            try:
                return handler(args)
            except Exception as e:
                logger.exception(f"Error handling action '{action}'")
                return {"ok": False, "error": str(e)}

    # ── API Methods ──────────────────────────────────────────────────

    def _api_start(self, args) -> dict:
        result = self.engine.start()
        return {"ok": result.passed, "data": {"message": result.message, "phase": result.phase}}

    def _api_get_state(self, args) -> dict:
        return {"ok": True, "data": self.engine.get_state()}

    def _api_get_current_phase(self, args) -> dict:
        return {"ok": True, "data": self.engine.get_current_phase()}

    def _api_check_gate(self, args) -> dict:
        phase = args.get("phase")
        result = self.engine.check_gate(phase)
        return {
            "ok": result.passed,
            "data": {
                "passed": result.passed,
                "phase": result.phase,
                "missing_artifacts": result.missing_artifacts,
                "score": result.score,
                "min_score": result.min_score,
                "failed_checks": result.failed_checks,
                "message": result.message,
                "summary": result.summary(),
            },
        }

    def _api_advance(self, args) -> dict:
        result = self.engine.advance()
        return {
            "ok": result.passed,
            "data": {
                "passed": result.passed,
                "phase": result.phase,
                "missing_artifacts": result.missing_artifacts,
                "failed_checks": result.failed_checks,
                "message": result.message,
                "summary": result.summary(),
            },
        }

    def _api_rollback(self, args) -> dict:
        target = args.get("target_phase", "")
        reason = args.get("reason", "")
        if not target:
            return {"ok": False, "error": "target_phase is required for rollback"}
        result = self.engine.rollback(target, reason)
        return {
            "ok": result.passed,
            "data": {
                "passed": result.passed,
                "phase": result.phase,
                "message": result.message,
                "summary": result.summary(),
            },
        }

    def _api_set_score(self, args) -> dict:
        phase = args.get("phase")
        score = args.get("score")
        if phase is None or score is None:
            return {"ok": False, "error": "phase and score are required"}
        self.engine.set_score(phase, float(score))
        return {"ok": True, "data": {"phase": phase, "score": score}}

    def _api_set_metadata(self, args) -> dict:
        phase = args.get("phase")
        key = args.get("key")
        value = args.get("value")
        if not all([phase, key]):
            return {"ok": False, "error": "phase and key are required"}
        self.engine.set_metadata(phase, key, value)
        return {"ok": True}

    def _api_record_command_result(self, args) -> dict:
        phase = args.get("phase")
        command = args.get("command")
        passed = args.get("passed", False)
        if not all([phase, command]):
            return {"ok": False, "error": "phase and command are required"}
        self.engine.record_command_result(phase, command, passed)
        return {"ok": True}

    def _api_check_tool_permission(self, args) -> dict:
        tool_name = args.get("tool_name")
        tool_args = args.get("tool_args", {})
        if not tool_name:
            return {"ok": False, "error": "tool_name is required"}
        result = self.engine.check_tool_permission(tool_name, tool_args)
        return {"ok": True, "data": result}

    def _api_get_history(self, args) -> dict:
        return {"ok": True, "data": self.engine.get_history()}

    def _api_verify_integrity(self, args) -> dict:
        return {"ok": True, "data": {"intact": self.engine.verify_integrity()}}


# ---------------------------------------------------------------------------
# Unix Socket Server
# ---------------------------------------------------------------------------

class SocketHandler(socketserver.BaseRequestHandler):
    """Handle a single client connection."""

    daemon_ref: WorkflowDaemon = None  # set by server factory

    def handle(self):
        try:
            data = b""
            while True:
                chunk = self.request.recv(4096)
                if not chunk:
                    break
                data += chunk
                if len(data) > BUFFER_SIZE:
                    break
                # Simple framing: newline-delimited JSON
                if b"\n" in data:
                    break

            if not data.strip():
                return

            request = json.loads(data.decode("utf-8").strip())
            response = self.daemon_ref.handle_request(request)

            response_data = json.dumps(response) + "\n"
            self.request.sendall(response_data.encode("utf-8"))

        except json.JSONDecodeError:
            self.request.sendall(
                json.dumps({"ok": False, "error": "Invalid JSON"}).encode() + b"\n"
            )
        except Exception as e:
            logger.exception("Socket handler error")
            try:
                self.request.sendall(
                    json.dumps({"ok": False, "error": str(e)}).encode() + b"\n"
                )
            except Exception:
                pass


class WorkflowSocketServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    parser = argparse.ArgumentParser(description="GSD Workflow Daemon")
    parser.add_argument(
        "--workflow", "-w",
        default="workflow/gsd-workflow.yaml",
        help="Path to workflow YAML definition",
    )
    parser.add_argument(
        "--project-dir", "-p",
        default=".planning",
        help="Project directory (where artifacts live)",
    )
    parser.add_argument(
        "--socket", "-s",
        default=SOCKET_PATH,
        help=f"Unix socket path (default: {SOCKET_PATH})",
    )
    parser.add_argument(
        "--foreground", "-f",
        action="store_true",
        help="Run in foreground (don't fork)",
    )
    args = parser.parse_args()

    # Clean up stale socket
    if os.path.exists(args.socket):
        os.unlink(args.socket)

    daemon = WorkflowDaemon(
        workflow_yaml=args.workflow,
        project_dir=args.project_dir,
        socket_path=args.socket,
    )

    # Make handler reference the daemon
    SocketHandler.daemon_ref = daemon

    server = WorkflowSocketServer(args.socket, SocketHandler)
    os.chmod(args.socket, 0o600)  # only owner can read/write

    logger.info(
        f"Workflow daemon started. Socket: {args.socket}\n"
        f"Workflow: {args.workflow}\n"
        f"Project dir: {args.project_dir}\n"
        f"HMAC key: {daemon.hmac_key[:8]}... (hidden)\n"
        f"Waiting for connections..."
    )
    print(
        f"GSD Workflow Daemon\n"
        f"  Socket: {args.socket}\n"
        f"  Workflow: {args.workflow}\n"
        f"  Project: {args.project_dir}\n"
        f"  PID: {os.getpid()}\n"
        f"  Ready. Waiting for connections...",
        flush=True,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
    finally:
        if os.path.exists(args.socket):
            os.unlink(args.socket)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    main()
