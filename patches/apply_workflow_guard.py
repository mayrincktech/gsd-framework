#!/usr/bin/env python3
"""
Workflow Guard Patch — Injects GSD workflow enforcement into Hermes core.

This patch adds a pre-flight check to TWO critical tools:
1. delegate_task() — blocks delegation unless phase == execute
2. terminal_tool() — blocks deploy commands unless phase == deploy

The guard client (workflow/guard.py) talks to the workflow daemon via Unix socket.
If the daemon is not running, the guard is permissive (Hermes works normally).
Only when a GSD workflow is active does enforcement kick in.

Patch locations:
  - delegate_tool.py: after parent_agent None check (line ~2091)
  - terminal_tool.py: after function signature + docstring (line ~1873)

Usage:
    python3 apply_workflow_guard.py           # Apply patch
    python3 apply_workflow_guard.py --check   # Check if patch is applied
    python3 apply_workflow_guard.py --revert  # Revert patch

After applying: restart Hermes gateway for changes to take effect.
After hermes update: re-run this patch (post_update_patches.py handles this).
"""

import sys
import shutil
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────

HERMES_HOME = Path.home() / ".hermes" / "hermes-agent"
GSD_FRAMEWORK = Path.home() / "workspace" / "hermes-gsd-framework"

DELEGATE_TOOL = HERMES_HOME / "tools" / "delegate_tool.py"
TERMINAL_TOOL = HERMES_HOME / "tools" / "terminal_tool.py"

# ── Patch markers ──────────────────────────────────────────────────────

PATCH_TAG = "# GSD-WORKFLOW-GUARD"
PATCH_START = f"{PATCH_TAG}-START"
PATCH_END = f"{PATCH_TAG}-END"

# ── Delegate Task Patch ────────────────────────────────────────────────
# Injected right after `if parent_agent is None:` check

DELEGATE_MARKER = '    if parent_agent is None:\n        return tool_error("delegate_task requires a parent agent context.")'

DELEGATE_PATCH = f'''

    {PATCH_START}
    # GSD Workflow Guard — blocks delegate_task unless in execute phase.
    # If workflow daemon is not running, this is a no-op (permissive).
    try:
        import sys as _sys
        _sys.path.insert(0, "{GSD_FRAMEWORK}")
        from workflow.guard import check_before_delegate
        _guard_result = check_before_delegate()
        if not _guard_result["allowed"]:
            import json as _json
            return _json.dumps({{
                "error": "BLOCKED by GSD Workflow Guard",
                "reason": _guard_result["reason"],
                "current_phase": _guard_result.get("current_phase"),
                "hint": "Complete the current phase gate and advance before delegating code tasks. "
                        "The workflow daemon enforces this — you cannot bypass it.",
            }}, ensure_ascii=False)
    except ImportError:
        pass  # Workflow guard not installed — permissive
    except Exception as _e:
        pass  # Fail safe — don't block on guard errors
    {PATCH_END}'''


# ── Terminal Tool Patch ────────────────────────────────────────────────
# Injected after the docstring, before the first real code

TERMINAL_MARKER = "# Execute a simple command"

TERMINAL_PATCH = f'''    {PATCH_START}
    # GSD Workflow Guard — blocks deploy commands unless in deploy phase.
    # If workflow daemon is not running, this is a no-op (permissive).
    try:
        import sys as _sys
        _sys.path.insert(0, "{GSD_FRAMEWORK}")
        from workflow.guard import check_before_terminal
        _terminal_guard = check_before_terminal(command)
        if not _terminal_guard["allowed"]:
            import json as _json
            return _json.dumps({{
                "error": "BLOCKED by GSD Workflow Guard",
                "reason": _terminal_guard["reason"],
                "current_phase": _terminal_guard.get("current_phase"),
                "command": command,
                "hint": "Deploy commands are only allowed in the 'deploy' phase. "
                        "Complete all gates (QA, tests) before deploying.",
            }}, ensure_ascii=False)
    except ImportError:
        pass  # Workflow guard not installed — permissive
    except Exception:
        pass  # Fail safe
    {PATCH_END}

    {TERMINAL_MARKER}'''


# ── Apply / Check / Revert ─────────────────────────────────────────────

def is_patched(filepath: Path) -> bool:
    """Check if a file already has the patch."""
    if not filepath.exists():
        return False
    return PATCH_START in filepath.read_text()


def apply_patch(filepath: Path, marker: str, replacement: str) -> bool:
    """Apply a patch by replacing marker text with patched version."""
    if not filepath.exists():
        print(f"  [ERROR] File not found: {filepath}")
        return False

    content = filepath.read_text()

    if PATCH_START in content:
        print(f"  [SKIP] Already patched: {filepath.name}")
        return True

    if marker not in content:
        print(f"  [ERROR] Marker not found in {filepath.name}")
        print(f"          Looking for: {marker[:80]}...")
        return False

    # Replace marker with marker + patch
    patched = content.replace(marker, marker + replacement, 1)

    # Backup
    backup = filepath.with_suffix(".py.workflow-backup")
    if not backup.exists():
        shutil.copy2(filepath, backup)

    filepath.write_text(patched)
    print(f"  [OK] Patched: {filepath.name}")
    return True


def revert_patch(filepath: Path) -> bool:
    """Revert a patch by removing injected code and restoring backup."""
    if not filepath.exists():
        print(f"  [ERROR] File not found: {filepath}")
        return False

    backup = filepath.with_suffix(".py.workflow-backup")
    if backup.exists():
        shutil.copy2(backup, filepath)
        backup.unlink()
        print(f"  [OK] Reverted from backup: {filepath.name}")
        return True
    else:
        # Manual removal
        content = filepath.read_text()
        while PATCH_START in content:
            start_idx = content.find(PATCH_START)
            # Find the start of the line
            start_idx = content.rfind("\n", 0, start_idx) + 1
            end_idx = content.find(PATCH_END, start_idx)
            if end_idx == -1:
                break
            end_idx = content.find("\n", end_idx) + 1
            content = content[:start_idx] + content[end_idx:]

        filepath.write_text(content)
        print(f"  [OK] Reverted (manual): {filepath.name}")
        return True


# ── Main ──────────────────────────────────────────────────────────────

def main():
    check_only = "--check" in sys.argv
    revert = "--revert" in sys.argv

    print("=" * 60)
    print("  GSD Workflow Guard Patch")
    print("  Enforces GSD phases via daemon-isolated state machine")
    print("=" * 60)

    if revert:
        print("\nReverting patches...")
        revert_patch(DELEGATE_TOOL)
        revert_patch(TERMINAL_TOOL)
        print("\nDone. Restart Hermes gateway to apply.")
        return

    if check_only:
        print("\nChecking patch status...")
        d = is_patched(DELEGATE_TOOL)
        t = is_patched(TERMINAL_TOOL)
        print(f"  delegate_tool.py: {'✅ APPLIED' if d else '❌ NOT APPLIED'}")
        print(f"  terminal_tool.py: {'✅ APPLIED' if t else '❌ NOT APPLIED'}")
        sys.exit(0 if (d and t) else 1)

    print("\nApplying patches...\n")

    # 1. Patch delegate_task
    print("[1/2] Patching delegate_tool.py...")
    ok1 = apply_patch(DELEGATE_TOOL, DELEGATE_MARKER, DELEGATE_PATCH)

    # 2. Patch terminal_tool
    print("\n[2/2] Patching terminal_tool.py...")
    ok2 = apply_patch(TERMINAL_TOOL, TERMINAL_MARKER, TERMINAL_PATCH)

    print("\n" + "=" * 60)
    if ok1 and ok2:
        print("  ✅ All patches applied successfully!")
        print()
        print("  Restart Hermes gateway to activate:")
        print("    hermes gateway restart")
        print()
        print("  To start the workflow daemon for a project:")
        print(f"    python3 {GSD_FRAMEWORK}/workflow/daemon.py \\")
        print(f"      --project-dir .planning \\")
        print(f"      --workflow {GSD_FRAMEWORK}/workflow/gsd-workflow.yaml")
    else:
        print("  ❌ Some patches failed. Check errors above.")
    print("=" * 60)

    sys.exit(0 if (ok1 and ok2) else 1)


if __name__ == "__main__":
    main()
