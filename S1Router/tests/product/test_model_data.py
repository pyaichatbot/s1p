"""M-002/M-003 provenance, independent review and leakage behavior."""

from __future__ import annotations

import hashlib
import json

import pytest

_review = pytest.importorskip(
    "s1m.data.review", reason="M-002/M-003 data-curation module not yet implemented"
)
_split = pytest.importorskip(
    "s1m.data.split", reason="M-002/M-003 data-curation module not yet implemented"
)
_validation = pytest.importorskip(
    "s1m.data.validation", reason="M-002/M-003 data-curation module not yet implemented"
)
ReviewError = _review.ReviewError
build_review_packet = _review.build_review_packet
merge_review_submissions = _review.merge_review_submissions
SplitLeakageError = _split.SplitLeakageError
SplitRole = _split.SplitRole
assign_splits = _split.assign_splits
validate_splits = _split.validate_splits
DataValidationError = _validation.DataValidationError
validate_rows = _validation.validate_rows

pytestmark = [pytest.mark.behavioral]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def row(number: int, **changes: object) -> dict[str, object]:
    body = f"Body for issue {number}."
    result: dict[str, object] = {
        "example_id": f"ghpr:{number}",
        "group_id": f"repo:{number}",
        "source_uri": f"https://example.invalid/issues/{number}",
        "source_revision": "2026-09-21T00:00:00Z",
        "source_license": "CC-BY-4.0",
        "source_license_uri": "https://creativecommons.org/licenses/by/4.0/",
        "source_license_digest": digest("CC-BY-4.0"),
        "source_digest": digest("fixture-export"),
        "collected_at": "2026-09-21T00:00:00Z",
        "task_id": "sdlc.change_type",
        "task_version": "1",
        "language": "en",
        "title": f"Issue {number}",
        "body": body,
        "label": None,
        "label_origin": "source_weak",
        "reviewer_ids": [],
        "adjudication_status": "pending",
        "content_hash": digest(f"Issue {number}\n{body}"),
        "repository": "example/repo",
        "issue_number": str(number),
        "source_label": "bug",
        "duplicate_cluster": None,
        "near_duplicate_cluster": None,
        "template_cluster": None,
        "split": None,
    }
    result.update(changes)
    return result


@pytest.mark.requirement("M-002")
def test_ingestion_reports_example_ids_for_missing_rights_and_invalid_label() -> None:
    invalid = row(1, source_license="", label="question")

    with pytest.raises(DataValidationError) as error:
        validate_rows([invalid])

    assert "ghpr:1" in str(error.value)
    assert "source_license" in str(error.value)
    assert "label" in str(error.value)


@pytest.mark.requirement("M-002")
def test_review_packet_is_deterministic_and_hides_weak_source_label() -> None:
    records = validate_rows([row(2), row(1)])

    packet = build_review_packet(records, reviewer_id="reviewer-a")
    lines = [json.loads(line) for line in packet.splitlines()]

    assert [line["example_id"] for line in lines] == ["ghpr:1", "ghpr:2"]
    assert all("source_label" not in line for line in lines)
    assert build_review_packet(records, reviewer_id="reviewer-a") == packet


@pytest.mark.requirement("M-002")
def test_two_independent_reviews_produce_human_label_and_preserve_origin() -> None:
    records = validate_rows([row(3)])
    first = (
        '{"example_id":"ghpr:3","reviewer_id":"a","label":"bug",'
        '"rationale":"broken behavior","ambiguous":false,"rubric_version":"1"}'
    )
    second = (
        '{"example_id":"ghpr:3","reviewer_id":"b","label":"bug",'
        '"rationale":"unexpected failure","ambiguous":false,"rubric_version":"1"}'
    )

    merged = merge_review_submissions(records, first + "\n", second + "\n")

    assert merged[0].label == "bug"
    assert merged[0].label_origin == "human_independent"
    assert merged[0].adjudication_status == "agreed"
    assert merged[0].reviewer_ids == ("a", "b")
    assert merged[0].source_label == "bug"


@pytest.mark.requirement("M-002")
def test_disagreement_requires_explicit_adjudication() -> None:
    records = validate_rows([row(4)])
    first = (
        '{"example_id":"ghpr:4","reviewer_id":"a","label":"bug",'
        '"rationale":"failure","ambiguous":false,"rubric_version":"1"}'
    )
    second = (
        '{"example_id":"ghpr:4","reviewer_id":"b","label":"feature",'
        '"rationale":"new behavior","ambiguous":true,"rubric_version":"1"}'
    )

    with pytest.raises(ReviewError, match="adjudication"):
        merge_review_submissions(records, first + "\n", second + "\n")

    adjudication = (
        '{"example_id":"ghpr:4","adjudicator_id":"c","label":"bug",'
        '"rationale":"expected behavior is broken","rubric_version":"1"}\n'
    )
    merged = merge_review_submissions(records, first + "\n", second + "\n", adjudication)
    assert merged[0].label == "bug"
    assert merged[0].adjudication_status == "adjudicated"
    assert merged[0].label_origin == "human_adjudicated"


@pytest.mark.requirement("M-003")
def test_split_validation_rejects_repository_and_duplicate_lineage_overlap() -> None:
    records = validate_rows(
        [
            row(5, split="train"),
            row(6, split="final_test", content_hash=row(5)["content_hash"]),
        ]
    )

    with pytest.raises(SplitLeakageError, match="repository|content_hash"):
        validate_splits(records)


@pytest.mark.requirement("M-003")
def test_split_validation_rejects_near_duplicate_and_template_overlap() -> None:
    records = validate_rows(
        [
            row(7, split="validation", near_duplicate_cluster="near-1"),
            row(8, split="calibration", template_cluster="template-1"),
            row(9, split="final_test", template_cluster="template-1"),
        ]
    )

    with pytest.raises(SplitLeakageError, match="template_cluster"):
        validate_splits(records)


@pytest.mark.requirement("M-003")
def test_assignment_is_deterministic_and_role_accessor_rejects_fit_leakage() -> None:
    records = validate_rows(
        [
            row(10, repository="repo-a", group_id="a"),
            row(11, repository="repo-b", group_id="b"),
            row(12, repository="repo-c", group_id="c"),
            row(13, repository="repo-d", group_id="d"),
        ]
    )
    first = assign_splits(records, seed="fixture")
    second = assign_splits(records, seed="fixture")

    assert [item.split for item in first] == [item.split for item in second]
    assert set(item.split for item in first) <= set(SplitRole)
    assert all(item.split not in {SplitRole.CALIBRATION, SplitRole.FINAL_TEST} for item in first)
