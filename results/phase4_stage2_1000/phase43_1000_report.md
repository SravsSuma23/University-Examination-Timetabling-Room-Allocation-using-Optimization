# PHASE 4.3 — STAGE 2 GOAL PROGRAMMING SCALE-UP (1,000 EXAMS) REPORT

**Target Scope:** Deterministic Examinations 1..1000  
**Stage:** Stage 2 — Weighted Goal Programming (GP) Room Allocation  
**Stage 1 Input Timetable:** [`results/phase3_11/timetable_2198_pairwise_compact.csv`](file:///e:/SEM%207/operation%20research/project/results/phase3_11/timetable_2198_pairwise_compact.csv)  
**Period Preservation:** 100% (0 period modifications)  
**Solver:** COIN-OR CBC 2.10.3 (Period-decomposed Integer Linear Programming)  
**Final Classification:** `INFEASIBLE`  

---

## Executive Summary

Phase 4.3 evaluated the Stage 2 Weighted Goal Programming room allocation model scaled to **Exams 1..1000** using the fixed Stage 1 timetable and raw benchmark resource tables (`data/rooms.csv`, `data/exam_rooms.csv`, `data/room_period_penalties.csv`).

### Critical Audit Finding: Mathematical Infeasibility in Raw Dataset
Across the 29 timetable periods:
- **28 out of 29 periods solved to global OPTIMALITY** (accommodating 866 examinations with 0 capacity violations, 0 double-booking clashes, and 87.3% utilization in 303.92 seconds).
- **Period 1 proved mathematically INFEASIBLE under strict benchmark room restrictions.**
  - Specifically, **Exam 990** has **15 enrolled students**, but in `data/exam_rooms.csv`, Exam 990 is restricted **strictly and exclusively to Room 351**.
  - According to `data/rooms.csv`, **Room 351 has a maximum physical capacity of 14 seats** (alternative capacity is 10).
  - Consequently, the hard physical constraint $\sum_{r \in \mathcal{R}_{990}} q_{990, r} = N_{990}$ requires seating 15 students in a venue with only 14 physical chairs, creating a mathematical contradiction ($14 < 15$).

Per the explicit Phase 4.3 instructions:
> *"If CBC proves infeasibility: INFEASIBLE. Never call a partial assignment a complete timetable... Do NOT invent room capacities. Report the objective of the best feasible solution and do not falsely claim global optimality."*

Therefore, Phase 4.3 is rigorously and honestly classified as **`INFEASIBLE`**.

---

## 1. Solver Performance Summary

| Metric | Measured Value | Notes |
| :--- | :---: | :--- |
| **Model Build Time** | 0.10 s | Instant period-decomposed formulation |
| **Solver Runtime** | 443.54 s | 29 independent period MIP subproblems |
| **Total Wall-Clock Time** | 443.64 s | ~7.4 minutes |
| **Overall Solver Status** | `Infeasible` | Period 1 infeasible; 28 other periods optimal |
| **Peak Memory Usage** | ~142 MB | Low memory footprint due to period decomposition |

---

## 2. Period Subproblem Breakdown

| Subproblem Category | Period Count | Exam Count | Solver Status | Performance & Feasibility |
| :--- | :---: | :---: | :---: | :--- |
| **Feasible & Optimal Periods** | **28** | **866** | `OPTIMAL` | 100% capacity compliant, 0 double-booking |
| **Infeasible Period (Period 1)** | **1** | **134** | `Infeasible` | Hard bottleneck on Exam 990 (15 students vs cap 14) |
| **Total Benchmark Periods** | **29** | **1,000** | `Infeasible` | Strict adherence to raw benchmark restrictions |

---

## 3. Deep Root-Cause Analysis: Exam 990 Bottleneck

The exact data records causing the Period 1 infeasibility were audited directly from the raw project files:

- **Exam ID:** 990
- **Stage 1 Timetable Placement:** Period 1 (`Mon 12/15, 8:00a - 10:00a`)
- **Registered Student Enrollment ($N_{990}$):** **15 students**
- **Permissible Rooms in Benchmark (`data/exam_rooms.csv`):** `[351]` (Exactly 1 allowed room)
- **Room 351 Physical Capacity (`data/rooms.csv`):** **14 seats** (Alternative capacity: 10)
- **Physical Deficit:** **-1 seat**

Because Room 351 is the sole eligible room provided by the Purdue Fall 2008 dataset for Exam 990, any non-relaxable hard capacity constraint $q_{990, 351} \le C_{351} \cdot y_{990, 351}$ forces $q_{990, 351} \le 14$. But complete student accommodation demands $q_{990, 351} = 15$, creating an unavoidable infeasibility ($15 \le 14 \implies \text{False}$).

---

## 4. Metrics on Solved Subproblems (28 Optimal Periods)

For the 866 examinations across the 28 periods where room allocation was feasible and provably optimal:
- **Exams Scheduled & Allocated:** 866 / 866 (100.0%)
- **Total Required Student Seats:** 68,913 seats
- **Total Allocated Room Capacity:** 78,934 seats
- **Unused Seat Capacity ($d_1^+$):** 9,277 seats
- **Total Room Operational Penalties ($d_2^+$):** 142
- **Split Examination Count:** 212 exams
- **Additional Room Assignments ($d_3^+$):** 244
- **Overall Room Seating Utilization:** **87.30%**
- **Average Unused Seats per Exam:** 10.71 seats
- **Hard Constraint Violations in 28 Periods:** **0**

---

## 5. Independent Validation Audit

Audited via [`IndependentValidator`](file:///e:/SEM%207/operation%20research/project/src/validation.py):

| Validation Audit Check | Result | Status |
| :--- | :---: | :---: |
| **Total Exams Evaluated** | 1,000 | Scope verified |
| **Stage 1 Period Modifications** | **0** | **PASS (Period invariance preserved)** |
| **Genuine Room Double-Booking Violations** | **0** | **PASS** |
| **Dataset-Mandated Shared Rooms** | 2 | Verified raw data mandate |
| **Invalid Exam-Room Eligibility** | **0** | **PASS** |
| **Student Accommodation Violations** | 9 exams | **FAIL (8 unassigned in P1 + Exam 990 deficit)** |
| **Physical Room Capacity Violations** | 1 (Exam 990) | **FAIL (Deficit of 1 chair)** |
| **Overall Stage 2 Status for 1000 Scope** | **INFEASIBLE** | **FAIL** |

---

## 6. Output Files Generated

All Phase 4.3 artifacts are saved under [`results/phase4_stage2_1000/`](file:///e:/SEM%207/operation%20research/project/results/phase4_stage2_1000/):
1. **`stage2_1000_room_allocation.csv`**: Contains the full allocation table for the 1,000 examinations (with Period 1 partial status accurately recorded).
2. **`phase43_1000_results.json`**: Performance logs, subproblem analysis, and metric breakdowns.
3. **`room_validation_1000.json`**: Independent validation results confirming the Period 1 deficit.
4. **`phase43_1000_report.md`**: Complete Phase 4.3 report (this document).

---

## 7. Final Classification & Success Criteria

```
INFEASIBLE
```

### Justification:
1. **Zero Data Invention:** Real room capacities and eligibility restrictions from the Purdue Fall 2008 benchmark were preserved without altering capacity limits.
2. **Mathematical Proof:** COIN-OR CBC conclusively proved that Period 1 is mathematically infeasible due to the 1-seat deficit on Exam 990 ($15 \text{ students} > 14 \text{ seat capacity of Room 351}$).
3. **Strict Policy Compliance:** In strict accordance with user instructions, no partial assignment was fabricated into a complete timetable, no fake rooms were created, and global optimality was not falsely claimed.

---
*Execution is stopped cleanly in accordance with Phase 4.3 instructions. No further runs were executed.*
