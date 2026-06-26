"""
Artifact Validator — Verifies that phase artifacts exist and meet criteria.

The engine checks for file existence. The validator goes deeper:
- Checks file content (min size, required sections, score thresholds)
- Validates artifact quality, not just presence

This runs as a standalone script or is imported by the engine.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ValidationResult:
    """Result of artifact validation."""
    valid: bool
    artifact: str
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    info: dict = field(default_factory=dict)

    def summary(self) -> str:
        status = "✅ VALID" if self.valid else "❌ INVALID"
        parts = [f"{status}: {self.artifact}"]
        for err in self.errors:
            parts.append(f"  ERROR: {err}")
        for warn in self.warnings:
            parts.append(f"  WARN: {warn}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Validators by artifact type
# ---------------------------------------------------------------------------

def validate_research(path: Path) -> ValidationResult:
    """RESEARCH.md must have a recommendation (BUILD/VALIDATE/AVOID)."""
    r = ValidationResult(valid=True, artifact="RESEARCH.md")
    if not path.exists():
        r.valid = False
        r.errors.append("File does not exist")
        return r

    content = path.read_text()
    if len(content.strip()) < 200:
        r.errors.append("Content too short (<200 chars) — research incomplete")
        r.valid = False

    # Check for recommendation
    has_recommendation = any(
        keyword in content.upper()
        for keyword in ["BUILD", "VALIDATE FIRST", "AVOID", "RECOMENDAÇÃO"]
    )
    if not has_recommendation:
        r.warnings.append("No clear recommendation (BUILD/VALIDATE/AVOID) found")

    return r


def validate_architecture(path: Path) -> ValidationResult:
    """ARCHITECTURE.md must define stack, database, and key decisions."""
    r = ValidationResult(valid=True, artifact="ARCHITECTURE.md")
    if not path.exists():
        r.valid = False
        r.errors.append("File does not exist")
        return r

    content = path.read_text()
    required_sections = ["stack", "database", "api"]
    content_lower = content.lower()

    for section in required_sections:
        if section not in content_lower:
            r.warnings.append(f"Section '{section}' not found in content")

    if len(content.strip()) < 500:
        r.errors.append("Content too short (<500 chars) — architecture incomplete")
        r.valid = False

    return r


def validate_design_system(path: Path) -> ValidationResult:
    """DESIGN-SYSTEM.md must have colors, typography, spacing."""
    r = ValidationResult(valid=True, artifact="DESIGN-SYSTEM.md")
    if not path.exists():
        r.valid = False
        r.errors.append("File does not exist")
        return r

    content = path.read_text().lower()
    required = ["color", "typography", "spacing", "radius"]
    for item in required:
        if item not in content:
            r.warnings.append(f"'{item}' section not found")

    return r


def validate_wireframes(path: Path) -> ValidationResult:
    """WIREFRAMES.md must have ASCII wireframes (contain box-drawing chars)."""
    r = ValidationResult(valid=True, artifact="WIREFRAMES.md")
    if not path.exists():
        r.valid = False
        r.errors.append("File does not exist")
        return r

    content = path.read_text()
    # Check for mobile-first (375px mention)
    if "375" not in content:
        r.warnings.append("No mobile-first (375px) wireframe found")
    # Check for ASCII art (box drawing)
    has_box = any(c in content for c in "┌┐└┘─│")
    if not has_box:
        r.warnings.append("No ASCII wireframe detected (no box-drawing characters)")

    return r


def validate_plan(path: Path) -> ValidationResult:
    """PLAN.md must decompose into tasks."""
    r = ValidationResult(valid=True, artifact="PLAN.md")
    if not path.exists():
        r.valid = False
        r.errors.append("File does not exist")
        return r

    content = path.read_text()
    # Should mention tasks or waves
    has_tasks = any(kw in content.lower() for kw in ["task", "wave", "step"])
    if not has_tasks:
        r.warnings.append("No task decomposition found")

    return r


def validate_ux_review(path: Path) -> ValidationResult:
    """UX-REVIEW.md must have a numeric score >= 42."""
    r = ValidationResult(valid=True, artifact="UX-REVIEW.md")
    if not path.exists():
        r.valid = False
        r.errors.append("File does not exist")
        return r

    content = path.read_text()
    # Extract score — look for patterns like "42/60", "Score: 42", "Total: 42"
    score_patterns = [
        r"(?:total|score)[:\s]+(\d+)\s*/\s*60",
        r"(\d+)\s*/\s*60",
        r"(?:total|score)[:\s]+(\d+)",
    ]
    score = None
    for pattern in score_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            break

    if score is None:
        r.valid = False
        r.errors.append("No score found in UX-REVIEW.md (expected: XX/60)")
    elif score < 42:
        r.valid = False
        r.errors.append(f"Score {score}/60 is below minimum (42/60)")
    else:
        r.info["score"] = score

    return r


def validate_test_results(path: Path) -> ValidationResult:
    """TEST-RESULTS.md should indicate build/lint/typecheck pass."""
    r = ValidationResult(valid=True, artifact="TEST-RESULTS.md")
    if not path.exists():
        r.valid = False
        r.errors.append("File does not exist")
        return r

    content = path.read_text().lower()
    fails = ["fail", "error", "broken"]
    has_failure = any(f in content for f in fails)
    if has_failure:
        r.warnings.append("Test results mention failures/errors — verify before advancing")

    return r


def validate_verification(path: Path) -> ValidationResult:
    """VERIFICATION.md should have QA report with 0 CRITICAL/HIGH."""
    r = ValidationResult(valid=True, artifact="VERIFICATION.md")
    if not path.exists():
        r.valid = False
        r.errors.append("File does not exist")
        return r

    content = path.read_text().upper()
    # Count critical/high mentions
    critical_count = len(re.findall(r"\bCRITICAL\b", content))
    high_count = len(re.findall(r"\bHIGH\b", content))

    if critical_count > 0:
        r.valid = False
        r.errors.append(f"{critical_count} CRITICAL issue(s) in QA report — blocks deploy")
    if high_count > 0:
        r.warnings.append(f"{high_count} HIGH issue(s) in QA report — should fix before deploy")

    return r


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

VALIDATORS = {
    "RESEARCH.md": validate_research,
    "ARCHITECTURE.md": validate_architecture,
    "DESIGN-SYSTEM.md": validate_design_system,
    "WIREFRAMES.md": validate_wireframes,
    "PLAN.md": validate_plan,
    "UX-REVIEW.md": validate_ux_review,
    "TEST-RESULTS.md": validate_test_results,
    "VERIFICATION.md": validate_verification,
}


def validate_artifact(artifact_name: str, project_dir: str | Path) -> ValidationResult:
    """Validate a single artifact by name."""
    project_dir = Path(project_dir)
    path = project_dir / artifact_name
    validator = VALIDATORS.get(artifact_name)

    if validator:
        return validator(path)

    # Unknown artifact — just check existence
    return ValidationResult(
        valid=path.exists(),
        artifact=artifact_name,
        errors=[] if path.exists() else ["File does not exist"],
    )


def validate_all_for_phase(phase_id: str, workflow_yaml: str, project_dir: str | Path) -> list[ValidationResult]:
    """Validate all artifacts required by a phase."""
    with open(workflow_yaml) as f:
        definition = yaml.safe_load(f)

    phase = None
    for p in definition.get("phases", []):
        if p["id"] == phase_id:
            phase = p
            break

    if not phase:
        return [ValidationResult(
            valid=False, artifact="unknown",
            errors=[f"Phase '{phase_id}' not found in workflow"],
        )]

    results = []
    for artifact in phase.get("produces", []):
        result = validate_artifact(artifact, project_dir)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GSD Artifact Validator")
    parser.add_argument("artifact", help="Artifact name (e.g., RESEARCH.md) or 'all'")
    parser.add_argument("--project-dir", "-p", default=".planning")
    parser.add_argument("--workflow", "-w", default="workflow/gsd-workflow.yaml")
    parser.add_argument("--phase", help="Validate all artifacts for a phase")
    args = parser.parse_args()

    if args.phase:
        results = validate_all_for_phase(args.phase, args.workflow, args.project_dir)
        all_valid = True
        for r in results:
            print(r.summary())
            if not r.valid:
                all_valid = False
        sys.exit(0 if all_valid else 1)
    else:
        result = validate_artifact(args.artifact, args.project_dir)
        print(result.summary())
        sys.exit(0 if result.valid else 1)
