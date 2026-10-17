## 1. Research Question

**Does SignalGate improve fraud detection over risk-only ranking at the same review workload?**

B2 ranks transactions by predicted fraud risk. SignalGate (P5) adds model disagreement as a supplementary signal. The hypothesis is that disagreement may help prioritize cases that risk ranking alone overlooks; this must be demonstrated experimentally.

**Primary metric:** Fraud recall at a matched touched rate.

## 2. Routing Policy Comparison

| Policy | Decision rule | Main limitation |
|---|---|---|
| Fixed threshold | Escalate transactions whose risk scores exceed a predefined threshold. | Review volume changes with the score distribution. |
| B2 — Top-budget ranking | Select the highest-risk transactions up to the review budget. | Relies on the quality of risk ranking. |
| SignalGate (P5) | Combine risk and model disagreement under the implemented scoring rule. | Disagreement may add no useful information beyond risk. |

B2 is the primary baseline because it explicitly accounts for review capacity. P5 must be compared with B2 on the same test transactions and at the same touched rate.

## 3. Interpreting the Signals

| Concept | Meaning | Important limitation |
|---|---|---|
| Fraud risk | Model-estimated likelihood or score associated with fraud. | A high score is not confirmed fraud. |
| Model disagreement | Differences between model predictions. | Models can agree and still be wrong; disagreement does not prove fraud. |
| Predictive uncertainty | Uncertainty associated with a prediction. | Disagreement is only a possible proxy, not a complete uncertainty measure. |
| Calibration | Agreement between predicted probabilities and observed frequencies. | Calibration does not necessarily improve ranking or fixed-budget recall. |
| Review capacity | Maximum workload available for investigation. | Both policies must be evaluated under comparable workload constraints. |

The key question is whether disagreement contributes information beyond the risk score. Its value cannot be assumed from the literature.

## 4. Evidence Audit

| Source or evidence | What it supports | What it does not establish |
|---|---|---|
| Dal Pozzolo et al. (2018) | Realistic fraud evaluation under class imbalance, temporal change, and limited investigation capacity. | That SignalGate improves recall. |
| Jitkrittum et al. (2023) | Evaluating deferral policies beyond simple confidence thresholds in classifier cascades. | That disagreement is a reliable uncertainty measure or that P5 outperforms B2. |
| Guo et al. (2017) | Measuring probability calibration where relevant. | That SignalGate is miscalibrated or that calibration improves recall. |
| Saito & Rehmsmeier (2015) | Using precision–recall analysis for imbalanced classification. | That PR-AUC alone demonstrates better performance at a fixed review budget. |
| B2 evaluation output | Baseline performance under the recorded configuration. | Performance beyond the evaluated data and conditions. |
| P5 evaluation output | Performance of the implemented SignalGate policy. | Improvement unless compared fairly against B2. |
| Matched-budget test results | Difference in recall and workload between B2 and P5. | Production effectiveness or universal generalization. |
| Synthetic shift tests, if available | Performance under the specified simulated perturbation. | Robustness to all real-world distribution shifts. |

**Project evidence status:** Numerical results and implementation artifacts must be checked against the existing phase reports and saved outputs. No project-level performance result is considered verified by this document alone.

For every available result, record its source, dataset, configuration, whether it is **real-data or synthetic**, and the specific conclusion it supports. Do not present planned experiments as completed results.

## 5. Essential Evaluation Checks

| Check | Requirement |
|---|---|
| Data partitioning | Sort chronologically before splitting. The proposed split is 60% training, 10% calibration, 10% validation, and 20% test. Record actual boundaries and counts. |
| Leakage prevention | Exclude raw identifiers and raw timestamps from model features; fit preprocessing and auxiliary components only on permitted partitions. |
| Test isolation | Freeze the model, scoring rule, and thresholds before final testing. Never tune against test results. |
| Review budget | The proposed primary budget is 1.5× training-set fraud prevalence. Calculate prevalence from the actual data. |
| Workload matching | Evaluate B2 and P5 on identical test rows at the same touched rate. Report actual rates if exact matching is impossible. |
| Required metrics | Recall, fraud detected/missed, precision, PR-AUC, touched rate, and route counts. Report calibration and latency only if measured. |
| Statistical uncertainty | Report the recall difference and a paired-bootstrap confidence interval if correctly implemented. |
| Routing safety | Account explicitly for `FRAUD_ALERT`, `MANUAL_REVIEW`, `ROUTINE`, and `HELD/DEFERRED`. Do not silently count deferred cases as routine or reviewed. |

The split percentages and budget multiplier are project design choices, not values prescribed by the cited papers.

## 6. Technical Questions for Review

1. What is the exact P5 scoring formula, and how is model disagreement calculated?
2. Does disagreement add predictive information beyond risk, or is it largely correlated with the risk score?
3. Are model outputs calibrated probabilities or ranking scores? If calibration is used, was it fitted without test-set access?
4. Were temporal ordering, feature leakage, preprocessing, and test isolation verified?
5. Are B2 and P5 evaluated on identical transactions at matched touched rates?
6. How many fraudulent transactions are missed or routed to `ROUTINE` by each policy?
7. Does P5 improve recall without increasing review workload?
8. What is the measured recall difference, and what uncertainty interval supports it?
9. Are real-data results clearly separated from synthetic stress tests?
10. Do the results support the claimed improvement, or is the evidence inconclusive?

## 7. Audit Conclusion

The cited literature motivates workload-aware fraud evaluation, appropriate metrics for imbalanced data, and investigation of alternative deferral signals. It does not validate SignalGate's particular disagreement-based policy.

The conclusion must follow the measured B2/P5 comparison:

- **Supported:** P5 meets the predefined improvement criterion at a matched workload.
- **Not supported:** P5 does not improve on B2 under the tested conditions.
- **Inconclusive:** Available evidence is insufficient to determine whether the improvement is reliable.

Do not alter the evaluation to obtain a preferred outcome. Report only what the available evidence establishes.

## References

1. A. Dal Pozzolo et al., “Credit Card Fraud Detection: A Realistic Modeling and a Novel Learning Strategy,” *IEEE Transactions on Neural Networks and Learning Systems*, 29(8), 3784–3797, 2018. https://doi.org/10.1109/TNNLS.2017.2736643
2. W. Jitkrittum et al., “When Does Confidence-Based Cascade Deferral Suffice?” *NeurIPS 36*, 2023. https://arxiv.org/abs/2307.02764
3. C. Guo et al., “On Calibration of Modern Neural Networks,” *ICML*, PMLR 70, 1321–1330, 2017.
4. T. Saito and M. Rehmsmeier, “The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets,” *PLOS ONE*, 10(3), e0118432, 2015. https://doi.org/10.1371/journal.pone.0118432
