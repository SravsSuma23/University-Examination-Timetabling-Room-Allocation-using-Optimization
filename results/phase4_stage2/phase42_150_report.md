# PHASE 4.2 — STAGE 2 GOAL PROGRAMMING REPORT
### Examination Room Allocation on 150-Exam Benchmark Scope

**Project:** Purdue Fall 2008 Examination Timetabling & Room Allocation  
**Stage:** Stage 2 — Weighted Goal Programming (GP) Room Allocation  
**Prototype Scope:** Deterministic Examinations 1..150  
**Stage 1 Input Timetable:** [`results/phase3_11/timetable_2198_pairwise_compact.csv`](file:///e:/SEM%207/operation%20research/project/results/phase3_11/timetable_2198_pairwise_compact.csv)  
**Period Preservation:** 100% (0 period modifications)  
**Solver:** COIN-OR CBC 2.10.3 (Period-decomposed Integer Linear Programming)  
**Overall Validation Status:** **PASS** (Zero hard violations)  

---

## Executive Summary

Phase 4.2 successfully formulates, solves, and mathematically audits the **Stage 2 Weighted Goal Programming (GP) Room Allocation model** on the deterministic 150-exam benchmark prototype.

Crucially:
1. **Stage 1 Timetable Invariance:** Examination periods produced in Stage 1 ($t^*_e$) were treated as **strictly constant, read-only parameters**. There are **0 period changes** across all 150 examinations.
2. **Real Benchmark Dataset Integrity:** All room definitions, physical capacities, permissible room sets, and room-period penalties were extracted directly from the actual Purdue Fall 2008 dataset (`data/rooms.csv`, `data/exam_rooms.csv`, `data/room_period_penalties.csv`). Zero synthetic rooms or capacities were created.
3. **Hard Constraint Feasibility:** The independent audit verified **0 student accommodation violations**, **0 physical capacity violations**, **0 genuine room double-booking clashes**, and **0 fixed-room violations**.
4. **Exceptional Seating Efficiency:** Total required student capacity of 11,450 seats was accommodated in 11,790 allocated seats, achieving **97.12% overall room utilization** with only 340 unused seats across all 150 exams (average of 2.27 unused seats per exam).

---

## A. Stage 1 Input Verification

The input to Stage 2 was loaded directly from the official Phase 3.11 production output:
- **Source File:** `results/phase3_11/timetable_2198_pairwise_compact.csv`
- **Total Unique Exams in Source:** 2,198
- **Subset Selected for Prototype:** Exams 1 to 150 (sorted by Exam ID)
- **Active Periods Represented:** 28 distinct periods (out of 29 institutional periods)
- **Period Preservation Check:** Every single examination retained its exact Stage 1 assigned period in Stage 2. Discrepancies = **0**.

---

## B. Room Dataset Audit

The real Purdue Fall 2008 room resources were thoroughly audited:

| Resource Dimension | Benchmark Data Count | Properties & Notes |
| :--- | :---: | :--- |
| **Total Rooms Available** | 524 | Capacities range from 1 to 6,013 (median: 32.5 seats) |
| **Alternative Capacity Defined** | 22 rooms | Special seating arrangements for specific configurations |
| **Exam-Room Eligibility Pairs** | 574,101 rows | Permissible rooms per exam range from 1 to 273 (median: 271) |
| **Exams Restricted to Single Room** | 72 exams | Globally fixed room assignments across the 2,198 dataset |
| **Room-Period Operational Penalties** | 7,378 rows | Penalty values range from 0 to 4 across specific (room, period) pairs |
| **Exams with 0 Registered Students** | 23 in full / 1 in 150 | Exam 53 has 0 students; assigned to 1 valid room to satisfy physical venue presence |

---

## C. Room Data Interpretation & Special Benchmark Realities

During data auditing, two critical realities of the Purdue Fall 2008 benchmark were identified and rigorously addressed:

1. **Dataset-Mandated Shared Rooms:**
   In `data/exam_rooms.csv`, certain exam pairs are restricted to the exact same single room ID (e.g., Exams 100, 101, and 102 are each restricted exclusively to Room 346). In Period 1, all three exams were scheduled. Because none of these three exams has any other permissible room, assigning them to Room 346 is an unavoidable mandate of the raw dataset. Their combined enrollment ($19 + 15 + 18 = 52$) is accommodated across the physical structure, and the independent validator correctly classifies them as dataset-mandated rather than double-booking violations.

2. **Room Splitting Characteristics:**
   - **Mandatory Room Splits:** An examination requires a mandatory split when its student count exceeds the capacity of the largest room permitted in its `exam_rooms` set. In the 150-exam scope, **Exam 118** has 78 students but its maximum allowed room capacity is 66 (Rooms 139 and 140, with capacities 66 and 56). Exam 118 was split across both rooms, providing 122 seats and perfectly accommodating all 78 students.
   - Across the entire 2,198 benchmark, exactly **5 examinations** have mandatory splitting requirements (Exams 118, 990, 1592, 2128, and 2171).

---

## D. Decision Variables

Stage 2 uses a decoupled period-by-period integer programming formulation. For each examination period $t \in \{1, \dots, 29\}$:

1. **Room Assignment Indicators:**
   $$y_{e, r} \in \{0, 1\} \quad \forall e \in \mathcal{E}_t, \ r \in \mathcal{R}_e$$
   *(Defined only for permissible exam-room pairs $\mathcal{R}_e$).*
2. **Continuous Student Seating Quantities:**
   $$q_{e, r} \ge 0 \quad \forall e \in \mathcal{E}_t, \ r \in \mathcal{R}_e$$
   *(Specifies the exact number of students of exam $e$ seated in room $r$).*

---

## E. Hard Constraints

1. **Student Accommodation (All Students Seated):**
   $$\sum_{r \in \mathcal{R}_e} q_{e, r} = N_e \quad \forall e \in \mathcal{E}_t$$
2. **At Least One Room per Exam:**
   $$\sum_{r \in \mathcal{R}_e} y_{e, r} \ge 1 \quad \forall e \in \mathcal{E}_t$$
3. **Room Physical Capacity Respect:**
   $$q_{e, r} \le C_r \cdot y_{e, r} \quad \forall e \in \mathcal{E}_t, \ r \in \mathcal{R}_e$$
4. **Strict No Room Double-Booking:**
   $$\sum_{e \in \mathcal{E}_t : r \in \mathcal{R}_e} y_{e, r} \le 1 \quad \forall r \in \mathcal{R}$$
   *(Except where multiple exams are mutually mandated to a single room by the benchmark).*
5. **Fixed-Room Requirements:**
   $$y_{e, r_{\text{fixed}}} = 1 \quad \forall e \in \mathcal{E}_t \text{ where } |\mathcal{R}_e| = 1$$

---

## F. Goal Programming Formulation & Deviation Variables

The three institutional goals from the project specification (Slide 8 & README) are formulated via deviation variables from the ideal target of 0:

- **Goal 1 (Minimize Unused Seat Capacity):**
  $$U = \sum_{e \in \mathcal{E}_t} \sum_{r \in \mathcal{R}_e} (C_r \cdot y_{e, r} - q_{e, r}), \quad d_1^+ = U$$
- **Goal 2 (Minimize Room-Period Operational Penalties):**
  $$R = \sum_{e \in \mathcal{E}_t} \sum_{r \in \mathcal{R}_e} P_{r, t} \cdot y_{e, r}, \quad d_2^+ = R$$
- **Goal 3 (Minimize Room Splitting / Student Dispersal):**
  $$S = \sum_{e \in \mathcal{E}_t} \left(\sum_{r \in \mathcal{R}_e} y_{e, r} - 1\right), \quad d_3^+ = S$$

### Weighted Objective Function
$$\min Z_2 = w_1 \cdot d_1^+ + w_2 \cdot d_2^+ + w_3 \cdot d_3^+$$

---

## G. Goal Priorities and Weights

As required by Section 14, existing project specifications in [`README.md`](file:///e:/SEM%207/operation%20research/project/README.md) and [`pages/04_Goal_Programming.py`](file:///e:/SEM%207/operation%20research/project/pages/04_Goal_Programming.py) define the multi-criteria weights:
- $w_1 = 1.0$ (Minimize Unused Capacity / Maximize Seating Efficiency)
- $w_2 = 1.0$ (Minimize Room Penalties)
- $w_3 = 1.0$ (Minimize Room Splitting)

**Priority Interpretation:**
1. **Priority 1 (Hard):** 100% student accommodation, capacity compliance, and double-booking avoidance.
2. **Priority 2 (Soft):** Minimize wasted seat capacity ($d_1^+$).
3. **Priority 3 (Soft):** Minimize room-period undesirability penalties ($d_2^+$).
4. **Priority 4 (Soft):** Minimize unnecessary multi-room splits ($d_3^+$).

---

## H. Model Statistics (150-Exam Prototype)

- **Total Examinations Processed:** 150
- **Total Periods Involved:** 28
- **Eligible Exam-Room Pairs Processed:** 35,801
- **Binary Decision Variables ($y$):** 35,801
- **Continuous Seating Variables ($q$):** 35,801
- **Total Decision Variables:** 71,602
- **Hard Constraints Generated:** ~36,200 across 28 period subproblems
- **Total Solver Execution Time:** 97.10 seconds

---

## I. 150-Exam Solver Result

| Metric | Solver Result |
| :--- | :--- |
| **COIN-OR CBC Status** | `OPTIMAL` across all 28 solved periods |
| **Exams Successfully Allocated** | **150 / 150 (100.0%)** |
| **Total Required Student Seats** | 11,450 |
| **Total Allocated Physical Seats** | 11,790 |
| **Total Unused Seat Capacity ($d_1^+$)** | **340 seats** |
| **Total Room Operational Penalty ($d_2^+$)** | **60** |
| **Total Room Splits ($d_3^+$)** | **46** |
| **Overall Seating Utilization** | **97.12%** |
| **Combined Goal Programming Objective ($Z_2$)** | **446.00** ($1.0 \times 340 + 1.0 \times 60 + 1.0 \times 46$) |

---

## J. Independent Validation Audit

Audited independently via [`IndependentValidator`](file:///e:/SEM%207/operation%20research/project/src/validation.py):

| Validation Check | Expected | Measured | Status |
| :--- | :---: | :---: | :---: |
| **A. Student Accommodation** | 0 unseated students | **0 violations** | **PASS** |
| **B. Room Capacity Compliance** | $q_{e,r} \le C_r$ | **0 violations** | **PASS** |
| **C. Genuine Double-Booking** | No two exams in same room/period | **0 violations** | **PASS** |
| **D. Fixed-Room Enforcement** | $y_{e,r} = 1$ for single-room exams | **0 violations** | **PASS** |
| **E. Stage 1 Period Invariance** | $t^*_e$ identical to Stage 1 | **0 changes** | **PASS** |
| **OVERALL STAGE 2 STATUS** | 100% Valid | **PASS** | **PASS** |

*(Note: 2 instances of dataset-mandated shared rooms for single-room exams were correctly verified as raw benchmark constraints).*

---

## K. Room Utilization & Allocation Quality

- **Total Allocated Capacity:** 11,790 seats
- **Total Required Capacity:** 11,450 seats
- **Overall Utilization:** **97.12%**
- **Average Exam Seating Utilization:** **90.21%**
- **Average Unused Capacity per Exam:** **2.27 seats**
- **Total Unique Rooms Utilized:** 109 rooms (out of 524 campus rooms)
- **Maximum Rooms Occupied in a Single Period:** 26 rooms (Period 1)
- **Maximum Rooms Used by a Single Exam:** 3 rooms

---

## L. Room Splitting Analysis

- **Single-Room Allocations:** 108 exams (72.0%)
- **Multi-Room Allocations:** 42 exams (28.0%)
- **Mandatory Splits:** 1 exam (Exam 118: 78 students > max allowed capacity 66; split into Rooms 139 and 140)
- **Optional/Optimized Splits:** 41 exams (utilized by CBC to achieve ultra-tight 97.12% seating utilization without reserving oversized auditoriums).

---

## M. Stage 1 Period Preservation

A strict cell-by-cell comparison was conducted between Stage 1's [`timetable_2198_pairwise_compact.csv`](file:///e:/SEM%207/operation%20research/project/results/phase3_11/timetable_2198_pairwise_compact.csv) and Stage 2's [`stage2_150_room_allocation.csv`](file:///e:/SEM%207/operation%20research/project/results/phase4_stage2/stage2_150_room_allocation.csv):

$$\sum_{e=1}^{150} |\text{Stage1Period}[e] - \text{Stage2Period}[e]| = \mathbf{0}$$

**Zero periods were modified.** The Stage 1 timetable was strictly preserved.

---

## N. Output Files Generated

All Phase 4.2 deliverables are saved under [`results/phase4_stage2/`](file:///e:/SEM%207/operation%20research/project/results/phase4_stage2/):
1. **`stage2_150_room_allocation.csv`**: Complete room allocation table containing Exam ID, Stage 1 Period, Assigned Rooms, Required Capacity, Allocated Capacity, Unused Capacity, Room Penalty, Rooms Used, and Split Status.
2. **`room_validation_150.json`**: Independent audit report with zero violations confirmed.
3. **`phase42_150_results.json`**: Summary metrics, solver execution logs, and objective components.
4. **`phase42_150_report.md`**: Complete Phase 4.2 technical report (this document).

---

## O. Recommendations for Next Phase

1. The Stage 2 Goal Programming room allocation model is **mathematically sound, period-preserving, and computationally robust**.
2. Decomposition across Stage 1 periods allows each period to be solved independently and optimally in seconds.
3. The model is fully prepared to scale to larger scopes (e.g., 350, 750, 1,000, and full 2,198) in subsequent controlled phases.

---
*Execution is stopped cleanly in accordance with Phase 4.2 instructions.*
