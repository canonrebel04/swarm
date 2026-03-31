"""
Structured output validation for agent responses.

This module validates that agent output conforms to the expected
JSON handoff schema before the coordinator processes task completion.
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from ..messaging.event_bus import event_bus


# Required fields in the handoff JSON block
HANDOFF_REQUIRED_FIELDS = {"role", "status", "summary"}

# Valid status values
VALID_STATUSES = {"done", "failed", "blocked", "partial"}

# Optional fields with type constraints
HANDOFF_OPTIONAL_SCHEMA = {
    "files_changed": list,
    "handoff_to": str,
    "critique": str,
    "risks": list,
    "validation_results": dict,
    "evidence_citations": list,
    "recommendations": list,
    "implementation_notes": str,
    "findings": list,
}


@dataclass
class ValidationResult:
    """Result of output validation."""

    valid: bool
    parsed: Optional[dict] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class OutputValidator:
    """
    Validates structured agent output against the handoff schema.

    Extracts JSON handoff blocks from agent output, validates required
    fields, type-checks optional fields, and enforces status conventions.
    """

    def validate_output(self, output: str, expected_role: str) -> ValidationResult:
        """
        Validate agent output for structured handoff compliance.

        Args:
            output: Raw agent output string.
            expected_role: The role the agent claims to be.

        Returns:
            ValidationResult with parsed data or error list.
        """
        result = ValidationResult(valid=False)

        if not output or not output.strip():
            result.errors.append("Empty output received")
            return result

        # Extract JSON block from output
        parsed = self._extract_json(output)
        if parsed is None:
            result.errors.append("No valid JSON handoff block found in output")
            return result

        result.parsed = parsed

        # Check required fields
        for field in HANDOFF_REQUIRED_FIELDS:
            if field not in parsed:
                result.errors.append(f"Missing required field: {field}")

        if result.errors:
            return result

        # Validate role matches
        if parsed["role"] != expected_role:
            result.errors.append(
                f"Role mismatch: agent is '{expected_role}' but output claims '{parsed['role']}'"
            )

        # Validate status
        status = parsed.get("status", "")
        if status not in VALID_STATUSES:
            result.errors.append(
                f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}"
            )

        # Type-check optional fields
        for field_name, expected_type in HANDOFF_OPTIONAL_SCHEMA.items():
            if field_name in parsed:
                if not isinstance(parsed[field_name], expected_type):
                    result.warnings.append(
                        f"Field '{field_name}' should be {expected_type.__name__}, "
                        f"got {type(parsed[field_name]).__name__}"
                    )

        # Check summary is non-empty
        summary = parsed.get("summary", "")
        if isinstance(summary, str) and len(summary.strip()) < 5:
            result.warnings.append("Summary is too short (< 5 chars)")

        result.valid = len(result.errors) == 0
        return result

    def extract_handoff_to(self, output: str) -> Optional[str]:
        """Extract the handoff_to target role from output."""
        parsed = self._extract_json(output)
        if parsed:
            return parsed.get("handoff_to")
        return None

    def _extract_json(self, output: str) -> Optional[dict]:
        """
        Extract a JSON object from agent output.

        Looks for JSON blocks in order of preference:
        1. Last line that is a complete JSON object
        2. JSON inside ```json code fences
        3. First complete JSON object found
        """
        # Strategy 1: last line that's a complete JSON object
        lines = output.strip().splitlines()
        for line in reversed(lines):
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError:
                    continue

        # Strategy 2: ```json code fence
        json_blocks = re.findall(r"```json\s*\n(.*?)\n```", output, re.DOTALL)
        for block in reversed(json_blocks):
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

        # Strategy 3: find any { ... } block
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None


# Global instance
output_validator = OutputValidator()
