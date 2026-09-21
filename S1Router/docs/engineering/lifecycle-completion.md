# Lifecycle code completion — 2026-09-21

Sources: [model spec](../s1m/spec.md), [router spec](../s1router/spec.md),
[delivery policy](delivery.md), [semantic review](review-2026-09-21.md).
Owner explicitly lifted the FEAT-007/008 code deferral in this conversation.
Production promotion remains gated on reviewed real data and measured resource evidence.

## Scope and acceptance

- M-004: real offline sparse multiclass training; train-only gradients and vocabulary,
  validation-only checkpoint selection, fixed seed and actual content identities,
  train-fitted majority baseline measured independently. Tiny fixtures prove software only.
- M-007: estimate scalar temperature using calibration-only reviewed labels and scores;
  return fitted parameter and immutable binding. Never train or calibrate while scoring.
- M-008: validated distributions, full classification/calibration metrics, exact risk bound,
  frozen baseline and candidate/data references. No test-label-fitted baseline.
- M-009/M-010: export/install a trained experimental candidate with verified weights,
  tokenizer, preprocessing and license; offline scoring remains available without promotion.
- M-011/M-012: controlled candidate lifecycle, artifact-bound calibration/evaluation/review
  records; changed precision/export identity starts experimental. Rejected transitions
  preserve the prior candidate. Model cards state actual state and evidence limits.
- R-013: 10,000-request bounded-memory observation independent of inference, using a
  non-retaining fake audit sink. Retained traced Python growth after warmup must stay
  below 1 MiB (new diagnostic leak-regression budget, not a process RSS certification).

## Architecture and review boundary

Training and evaluation remain offline model application modules; immutable artifacts
are the boundary into inference. The router keeps policy and never imports training.
Use the existing sparse linear baseline and Python standard library before adding an
encoder dependency. Production promotion is an explicit operator action after evidence
validation, never an automatic consequence of a successful training run. No generated
labels count as independent human ground truth. Full release gates remain unchanged.
