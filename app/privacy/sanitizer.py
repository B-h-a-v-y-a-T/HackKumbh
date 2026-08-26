"""
Privacy Sanitizer — Ensures no PII leaks into logs or evidence.

Only anonymous identifiers allowed: track_id, seat_id, camera_id.
No names, faces, biometrics, roll numbers, or identity information.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Patterns that might indicate PII
PII_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b\d{10,12}\b"),  # phone numbers
    re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),  # US phone
    re.compile(r"\bname\s*[:=]\s*[\"'][^\"']+[\"']", re.IGNORECASE),  # name fields
    re.compile(r"\broll[_\s]?no", re.IGNORECASE),  # roll number references
    re.compile(r"\bstudent[_\s]?id", re.IGNORECASE),  # student ID references
    re.compile(r"\bface[_\s]?(embed|encod|recogni|id)", re.IGNORECASE),  # face recognition
    re.compile(r"\bbiometric", re.IGNORECASE),  # biometric references
]

# Allowed identifier patterns
ALLOWED_ID_PATTERN = re.compile(r"^[A-Z]{1,4}[-_]?\d{1,6}$")  # T17, CAM_01, B4


def sanitize_log_message(message: str) -> str:
    """Remove potential PII from log messages."""
    for pattern in PII_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message


def validate_no_pii(data: Dict[str, Any]) -> List[str]:
    """
    Check a data dictionary for potential PII.
    Returns list of warnings (empty if clean).
    """
    warnings = []
    pii_keys = {
        "name", "student_name", "full_name", "first_name", "last_name",
        "email", "phone", "mobile", "roll_number", "roll_no",
        "student_id", "aadhaar", "ssn", "face_embedding", "face_id",
        "biometric", "fingerprint", "iris",
    }

    for key in data:
        if key.lower() in pii_keys:
            warnings.append(f"Potential PII field detected: '{key}'")

    # Check string values for PII patterns
    for key, value in data.items():
        if isinstance(value, str):
            for pattern in PII_PATTERNS:
                if pattern.search(value):
                    warnings.append(f"Potential PII in field '{key}'")
                    break

    return warnings


def sanitize_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize evidence data to ensure no PII.
    Removes any fields that might contain identifying information.
    """
    forbidden_keys = {
        "name", "student_name", "full_name", "first_name", "last_name",
        "email", "phone", "roll_number", "roll_no", "student_id",
        "face_embedding", "face_id", "biometric", "audio",
    }

    sanitized = {}
    for key, value in evidence.items():
        if key.lower() in forbidden_keys:
            logger.warning(f"Stripped PII field '{key}' from evidence")
            continue
        sanitized[key] = value

    return sanitized


class PrivacySanitizer:
    """Stateful privacy sanitizer for the application."""

    def __init__(self) -> None:
        self._violations: List[str] = []

    def check_and_sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for PII and sanitize the data."""
        warnings = validate_no_pii(data)
        if warnings:
            self._violations.extend(warnings)
            for w in warnings:
                logger.warning(f"Privacy violation: {w}")
        return sanitize_evidence(data)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    def get_violations(self) -> List[str]:
        return list(self._violations)

    def clear_violations(self) -> None:
        self._violations.clear()
