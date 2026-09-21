# Open data curation for S1M issue change types

Reviewed: 2026-09-21. This note is research for M-002 and M-003. It does not claim that a dataset has been accepted, that labels are correct, or that any release evidence exists. No raw dataset was downloaded for this review.

## Decision-ready recommendation

The best acquisition plan is a small, rights-reviewed corpus built from one or more projects whose issue taxonomy is close to S1M's four labels, with all labels re-reviewed by two people. The source label is a sampling aid and provenance field; it is not ground truth. A candidate is eligible only after the rights gate below is complete for the actual title/body text, not merely for the repository's software.

There is no immediately release-ready public dataset in the sources reviewed here:

| Candidate | What is useful | Rights/quality status | Recommendation |
| --- | --- | --- | --- |
| [CPython issue tracker](https://github.com/python/cpython) | The Python Developer's Guide defines `type-bug`, `type-feature`, `type-refactor`, and `docs` with meanings that closely match S1M. | CPython's [LICENSE](https://github.com/python/cpython/blob/main/LICENSE) covers the project software. It does not by itself establish a redistribution license for every GitHub issue body written by third parties. | Priority acquisition target after the Python project/author rights question is resolved. Collect only issue title/body and metadata needed for provenance. |
| [GHPR dataset](https://github.com/soroushj/ghpr-dataset) | Publisher declares CC BY 4.0; 14,384 issue/PR-link rows include issue title/body, repository, issue number, timestamps and label IDs. | Its README documents the fields and collection method, but labels are numeric IDs and one issue can occur in several issue/PR links. The dataset's CC BY declaration must be checked against the underlying issue-text rights and each source repository's terms. | Best bounded seed for an acquisition and review pilot after rights review. Deduplicate by canonical issue and do not use linked PR fields as model input. |
| [NLBSE'24 issue report classification](https://github.com/nlbse2024/issue-report-classification) | 3,000 English title/body rows from five projects, with `bug`, `feature`, and `question` labels and a reproducible extraction notebook. | The repository's [LICENSE](https://github.com/nlbse2024/issue-report-classification/blob/main/LICENSE) is empty in the reviewed revision. The README says the rows are publicly available, which is not a dataset license. Its pre-made 50/50 split is not a leakage guarantee. | Use for method comparison or candidate discovery only. Do not copy issue text into S1 training/evidence until a rights holder grants permission or every upstream text license is verified. |
| [PyTorch Lightning issue-label mirror](https://huggingface.co/datasets/Rami/multi-label-class-github-issues-text-classification) | The viewer shows real issue title/body examples with `bug`, `feature`, `docs`, and `refactor` labels. | The reviewed dataset card supplies no clear license or source revision and includes multi-label, resolution/status and workflow labels. The card's examples are not enough to establish rights or a single target label. | Reject for S1 provenance until the publisher supplies immutable source, license evidence and a single-label curation manifest. |

The CPython and Kubernetes-style taxonomies show that the requested four-way task exists in real project triage. The [Python labels guide](https://devguide.python.org/triage/labels/) defines bug as unexpected behavior, feature as a feature request or enhancement, refactor as code restructuring without user-facing behavior change, and `docs` as documentation in the documentation tree, docstrings, and comments. Kubernetes documents analogous `kind/bug`, `kind/feature`, `kind/documentation`, and `kind/cleanup` labels in its [issue triage guide](https://github.com/kubernetes/ingress-nginx/blob/main/ISSUE_TRIAGE.md). These definitions support source selection; they do not turn maintainer labels into independent human truth.

## What was verified

The NLBSE repository's README states that it contains 3,000 rows with repository, label, title and body and that labels are `bug`, `feature`, and `question`; its extraction notebook shows the five source repositories, label mapping, closed-issue filter and exclusion of issues with multiple type labels. The same notebook obtains data through the GitHub API and does not establish an issue-text license. The repository is therefore useful evidence about a classification task, but its advertised split and labels cannot be accepted as S1M provenance or test truth.

GHPR's README identifies a stable schema containing `issue_title`, `issue_body_md`, `issue_body_plain`, issue number, repository ID, timestamps and numeric label IDs. It also states that the rows are built by following GitHub keyword links from merged pull requests and that an issue/PR pair may be repeated across links. That construction creates a useful source of resolved issue reports, but also selection bias toward issues linked to merged changes and a direct duplicate/lineage hazard. The repository advertises a CC-BY-4.0 license for the dataset. Preserve the exact license text, commit or release identifier, attribution and upstream-repository list if it is used; do not infer that the declaration removes third-party author or privacy obligations.

The GitHub Terms of Service say that users own their user-generated content, that public issues and comments may be viewed by others, and that public-repository content may be used through GitHub functionality. They also say that content added to a repository with a license is licensed under that license unless a separate agreement supersedes it. This is why a public URL, a software license, and a dataset redistribution license must be recorded as separate provenance facts. See [GitHub Terms, user-generated content](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service) and [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).

## Rights and privacy gate

An acquisition is `rights_status=eligible` only when every row can be traced to an immutable source and all of the following are recorded in a manifest:

1. Canonical source URL, repository owner/name, API or archive endpoint, retrieval date, immutable revision or query, and a SHA-256 digest of the exact input export.
2. The dataset publisher's license URL and license text hash, plus each upstream repository's license, contribution agreement or explicit data-use statement that applies to issue text. Record `unknown` when the text grant cannot be established; `public`, `open source`, or `available on GitHub` is not a license value.
3. Required attribution, share-alike, non-commercial, no-derivatives, notice, database-rights and takedown conditions. Do not combine incompatible sources under one blanket project license. A software license for source code does not automatically license issue prose, screenshots, pasted logs, attachments or comments.
4. A content review that removes credentials, access tokens, private URLs, email addresses, customer data, screenshots and unrelated comments. Retain the canonical issue URL and a content hash for audit, but do not put raw text or author handles in logs. Keep a removal/withdrawal process that can invalidate an example and the affected split manifest.
5. A declaration of the allowed use: research only, internal training, redistribution, or commercial use. If the rights grant is narrower than the intended use, the candidate remains ineligible for that use.

The source license and label provenance must be captured before model fitting. A later label correction or license interpretation change creates a new dataset version and invalidates dependent split, calibration and evaluation identities.

## Human review protocol

Use the following protocol for a real curation run. It is a procedure, not a claim that any labels have been collected.

### Ingest and freeze

Create one immutable record per canonical issue with `example_id`, `group_id`, source URI, source revision, source license, capture timestamp, title, body, language, and `label_origin`. For GitHub, `group_id` must include the repository and canonical issue number; all linked pull requests and mirrors map to that same group. Do not use PR title, PR body, commit message, changed files, resolution, closure reason, maintainer label, or later comments as model features when the intended input is the issue title/body at creation time.

Normalize whitespace only for fingerprinting. Compute exact fingerprints over title plus body, then cluster near duplicates and template copies before any split. Keep source repository, canonical issue, duplicate/template cluster and temporal bucket as grouping keys. Freeze the candidate ID list and split manifest before reading model predictions or selecting exclusions.

Remove rows that are not real software-development issues: spam, empty reports, pure questions/support requests, security disclosures that require restricted handling, personal data, inaccessible text, or mixed requests that cannot be assigned one primary change type. Record every exclusion and its reason. Do not drop a difficult row after seeing a model prediction.

### Independent labels

Give each reviewer the same versioned rubric and the sanitized issue title/body, with source labels and any existing predicted label hidden. Reviewers work independently and record one of `bug`, `feature`, `documentation`, `refactor`, or `exclude`, with a short evidence note and an ambiguity flag. The rubric is:

* `bug`: the report identifies behavior that is broken, incorrect or unexpectedly failing; a fix restores the behavior the issue describes.
* `feature`: the report requests new behavior or a material enhancement that is not currently provided.
* `documentation`: the requested change is explanatory content, docs, examples, docstrings or comments and does not intend runtime behavior change.
* `refactor`: the requested change reorganizes implementation or removes technical debt while preserving intended user-visible behavior.

When more than one type is present, reviewers label the primary requested outcome only if one is clearly dominant. Otherwise they choose `exclude` with `mixed_or_ambiguous`. A documentation typo that fixes a documented behavior claim can be a bug if the issue describes incorrect runtime behavior; the rationale must state which evidence controls the decision. A refactor that also changes behavior is not a refactor under this rubric. These boundary cases should be included in adjudication examples rather than resolved by keywords.

### Adjudication and evidence

Every final-test row receives two independent labels. A disagreement is sent to a third adjudicator, who sees both rationales and records the selected label, reason, rubric version and adjudication timestamp. Do not let the adjudicator silently rewrite either original label. If only one reviewer is available, mark the entire dataset `experimental` and do not use it as production-release evidence, as required by M-002/M-008 policy.

For train and validation rows, retain both raw labels, agreement/disagreement, adjudication state, reviewer pseudonyms and rubric version. Report counts by final label, source repository, group and exclusion reason, plus agreement before adjudication. Do not manufacture an agreement score or quality result; it is produced only from recorded labels. Source labels may be reported as weak metadata and compared with human labels, but cannot replace independent review.

### Split and leakage review

Assign groups before labels are exposed to model developers. Keep every exact duplicate, near duplicate, template cluster, canonical issue, linked PR lineage and repository group in one partition. A practical first manifest is 70% train, 10% validation, 10% calibration and 10% untouched final test, with group integrity taking precedence over exact percentages. A temporal cutoff may be added for deployment realism, but it must not split a lineage group.

The final-test manifest is read-only after the first model fit. Reviewers label final-test rows without model predictions, and model developers do not inspect final-test text while tuning preprocessing, architecture, thresholds or calibration. If a final-test row is used to resolve a rubric ambiguity or repair a data rule, create a new versioned final-test set and report the prior one as development evidence. Validate exact, near-duplicate, template, repository/issue and temporal overlap before any gradient step; fail the run with example IDs and group IDs when overlap is found.

Before accepting a split, run a manual sample check of each label and each source group, inspect the largest duplicate/template clusters, and verify that metadata fields used for grouping are not present in the model text. A model may use the issue title/body only; post-resolution artifacts are evidence for review and lineage, not input features.

## Evidence limits and next action

The reviewed sources establish that open issue corpora and compatible project taxonomies exist. They do not establish a clean, four-class, independently human-labeled, rights-cleared S1M dataset. The next bounded action is a small CPython or GHPR rights-and-schema pilot: obtain the immutable export and license evidence, sample a few hundred rows without training, run the provenance/dedup/split checks, and have two reviewers label a frozen pilot. Only that pilot's recorded outcomes can decide whether to proceed to the full dataset. No performance, agreement, coverage or release claim should be made from the sources listed above.

### Primary sources reviewed

* [S1M specification](../s1m/spec.md), M-002/M-003 and the four-label rubric.
* [S1M design](../s1m/design.md), provenance fields, group splits and reviewer policy.
* [CPython/Python labels guide](https://devguide.python.org/triage/labels/).
* [CPython LICENSE](https://github.com/python/cpython/blob/main/LICENSE).
* [GHPR README and license](https://github.com/soroushj/ghpr-dataset).
* [NLBSE'24 README](https://github.com/nlbse2024/issue-report-classification), [dataset notebook](https://github.com/nlbse2024/issue-report-classification/blob/main/1-Dataset.ipynb), and [LICENSE](https://github.com/nlbse2024/issue-report-classification/blob/main/LICENSE).
* [PyTorch Lightning issue mirror dataset card](https://huggingface.co/datasets/Rami/multi-label-class-github-issues-text-classification).
* [Kubernetes issue triage labels](https://github.com/kubernetes/ingress-nginx/blob/main/ISSUE_TRIAGE.md).
* [GitHub Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service) and [licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
