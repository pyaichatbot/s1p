"""Immutable candidate lifecycle with artifact-bound evidence and explicit review.

Evidence is a local operator attestation. Hash binding prevents accidental reuse;
it does not authenticate a reviewer or establish dataset rights. The repository
release gate and owner review remain mandatory before any production deployment.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from s1m.artifacts.manifest import load
from s1m.artifacts.promotion import check_hardware, check_quality, number


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def reference(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


@dataclass(frozen=True)
class Candidate:
    artifact_ref: str
    fixture: bool = False
    events: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not reference(self.artifact_ref)
            or type(self.fixture) is not bool
            or type(self.events) is not tuple
        ):
            raise ValueError("invalid candidate identity")
        state = "experimental"
        prior: dict[str, str] = {}
        for event in self.events:
            if not isinstance(event, str) or len(event) > 1_048_576:
                raise ValueError("invalid lifecycle event")
            value = json.loads(event)
            if set(value) != {"state", "evidence"}:
                raise ValueError("invalid lifecycle event")
            target, evidence = value["state"], value["evidence"]
            allowed = {
                "experimental": "calibrated",
                "calibrated": "evaluated",
                "evaluated": "approved",
            }
            if state == "retired" or (target != "retired" and allowed.get(state) != target):
                raise ValueError("invalid lifecycle transition")
            if not isinstance(evidence, dict) or evidence.get("artifact_ref") != self.artifact_ref:
                raise ValueError("artifact identity mismatch")
            if target in {"calibrated", "evaluated"}:
                if (
                    not reference(evidence.get("dataset_ref"))
                    or evidence.get("review_status") != "human_reviewed"
                ):
                    raise ValueError("reviewed dataset evidence required")
                if evidence.get("split") != (
                    "calibration" if target == "calibrated" else "final_test"
                ):
                    raise ValueError("invalid evidence split")
            if target == "calibrated" and not number(evidence.get("temperature"), 0.01, 100):
                raise ValueError("invalid fitted temperature")
            if target == "evaluated":
                if evidence.get("calibration_ref") != digest(prior["calibrated"]):
                    raise ValueError("calibration identity mismatch")
                if evidence["dataset_ref"] == json.loads(prior["calibrated"])["dataset_ref"]:
                    raise ValueError("evaluation dataset leakage")
                if not isinstance(evidence.get("quality"), dict):
                    raise ValueError("quality evidence required")
            if target == "approved":
                self._check_approval(evidence, prior)
            prior[target] = canonical(evidence)
            state = target

    def _check_approval(self, evidence: dict[str, Any], prior: dict[str, str]) -> None:
        if self.fixture:
            raise ValueError("fixture cannot be approved")
        hardware, review = evidence.get("hardware"), evidence.get("review")
        if not isinstance(hardware, dict) or not isinstance(review, dict):
            raise ValueError("hardware and human review required")
        if (
            hardware.get("artifact_ref") != self.artifact_ref
            or review.get("artifact_ref") != self.artifact_ref
        ):
            raise ValueError("approval identity mismatch")
        if review.get("evaluation_ref") != digest(prior["evaluated"]) or review.get(
            "hardware_ref"
        ) != digest(canonical(hardware)):
            raise ValueError("review evidence identity mismatch")
        if review.get("decision") != "approve" or not reference(review.get("owner_decision_ref")):
            raise ValueError("explicit owner decision required")
        reviewers = review.get("reviewer_ids")
        if (
            not isinstance(reviewers, list)
            or len(reviewers) < 2
            or any(not isinstance(r, str) or not r.strip() for r in reviewers)
            or len(set(reviewers)) != len(reviewers)
        ):
            raise ValueError("independent human review required")
        check_quality(json.loads(prior["evaluated"])["quality"])
        check_hardware(hardware)

    @classmethod
    def register(cls, bundle: Path) -> Candidate:
        ref, manifest, _ = load(bundle)
        return cls(ref, manifest["status"] == "experimental_fixture")

    @property
    def state(self) -> str:
        return json.loads(self.events[-1])["state"] if self.events else "experimental"

    def _evidence(self, state: str) -> str:
        for event in self.events:
            value = json.loads(event)
            if value["state"] == state:
                return canonical(value["evidence"])
        raise ValueError("lifecycle evidence missing")

    @property
    def calibration_json(self) -> str:
        return self._evidence("calibrated")

    @property
    def calibration_ref(self) -> str:
        return digest(self.calibration_json)

    @property
    def evaluation_ref(self) -> str:
        return digest(self._evidence("evaluated"))

    def _advance(self, state: str, evidence: dict[str, Any]) -> Candidate:
        return replace(
            self, events=self.events + (canonical({"state": state, "evidence": evidence}),)
        )

    def calibrate(self, evidence: dict[str, Any]) -> Candidate:
        return self._advance("calibrated", evidence)

    def evaluate(self, evidence: dict[str, Any]) -> Candidate:
        return self._advance("evaluated", evidence)

    def approve(self, hardware: dict[str, Any], review: dict[str, Any]) -> Candidate:
        return self._advance(
            "approved", {"artifact_ref": self.artifact_ref, "hardware": hardware, "review": review}
        )

    def retire(self) -> Candidate:
        return self._advance("retired", {"artifact_ref": self.artifact_ref})
