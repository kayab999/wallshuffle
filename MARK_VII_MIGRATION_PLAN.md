# KAYAB MARK VII: MIGRATION PLAN (Heuristic -> Physics)

## Phase 1: Instrumentation (Current)
*   **Objective:** Connect GENESIS runtime to Mark VII telemetry.
*   **Action:** Integrate `kayab_monitor.py` (HamiltonianMonitor).
*   **Metric:** Log "Energy" ($H$) of CLI operations alongside standard logs.

## Phase 2: Hybrid Validation
*   **Objective:** Use SAE (`sae_model.pth`) for critical path validation.
*   **Action:** Load SAE in "Shadow Mode" (inference only, no blocking).
*   **Trigger:** If `RiskEvaluator` > 0.7, run `SAE.decode()` to check semantic consistency.

## Phase 3: Engine Swap
*   **Objective:** Replace Heuristic proxies with Real Physics.
*   **Action:**
    *   `RiskEvaluator` → `HamiltonianMonitor`
    *   `SafetyKernel` → `TopologicalVerifier`
*   **Condition:** Phase 2 data must show >99% correlation between Heuristic and Physics risk scores.
