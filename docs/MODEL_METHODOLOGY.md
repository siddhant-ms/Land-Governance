# Model methodology — `land_record_digitization` v1.0.0 (normalized-index family)

**Purpose:** show how explicit assumptions propagate to indexed outcomes. **It is not a validated forecasting model** and does not prove that digitization reduces disputes.

## Inputs
`c0` current coverage % · `c1` target coverage % · `k` implementation capacity (0.1–1) · `q` data quality (0.5–1) · `p0` baseline processing pressure (index) · `d0` baseline dispute pressure (index). `c0`, `p0`, `d0` default from the selected region's latest observation (state = mean of districts; `p0` = mutation days ÷ all-district mean × 100).

## Equations
```
e = c0 + (c1 − c0)·k                         delivered coverage
b = ((e − c0)/100)·q                          effective benefit
coverage_gap = 100 − e
processing_pressure P = p0·(1 − α_p·b)
workload W = p0·(1 − α_w·b) + τ·(1 − k)·(c1 − c0)/100        τ = transition burden
dispute D = d0·(1 − α_d·b)
composite I = 100·(w_c·e/100 + w_w·(1 − clamp(W/200)) + w_d·(1 − clamp(D/200)))
```
Baseline = same model with `c1 = c0` (no intervention). Coefficients: `α_p=0.6, α_w=0.9, α_d=0.5, τ=25, w=(0.4,0.3,0.3)`.

**Worked example (k=1, q=1, 62→80):** b=0.18 → W = 100·(1−0.9·0.18) = **83.8 (−16.2%)** · D = 91.0 · I: 54.8 → 65.8. Reproduced in `tests/test_simulation.py`.

## Provenance of coefficients
All are **synthetic demo calibrations** chosen for explainability (α_w chosen to reproduce the PRD example). Each carries a provenance string shown in the UI and exports. Replacing them requires domain-expert calibration against evaluated programmes; `PATCH /admin/models/{id}` creates a new version (never edits in place) and experts record review notes.

## Supported range (rejects instead of extrapolating)
Parameters within their min/max; target ≥ current; expansion ≤ 60 points. Otherwise `422 SIMULATION_OUT_OF_RANGE` with the exact problems.

## Sensitivity
(1) Sweep of one input across its supported range (target coverage on a 5-point grid), re-running the full model; (2) tornado: ±10 % of each input, one at a time, on the composite index. Shows assumption-dependence, **not** statistical uncertainty.

## Limitations
Linear, additive, no interactions beyond those above, no spatial spillovers, no time dynamics, concurrent reforms held constant, no uncertainty intervals, not validated against observed outcomes. Outputs carry the disclaimer *"This is a scenario estimate, not a guaranteed real-world outcome."* and input/output SHA-256 hashes for reproducibility.
