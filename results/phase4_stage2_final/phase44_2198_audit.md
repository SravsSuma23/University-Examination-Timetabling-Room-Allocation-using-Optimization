# PHASE 4.4.1 — INDEPENDENT AUDIT OF STAGE 2 GOAL PROGRAMMING RESULTS
### Full Purdue Fall 2008 Benchmark (2,198 Examinations)

**Audit Phase:** 4.4.1  
**Target Artifacts Audited:**  
- [`results/phase4_stage2_final/stage2_2198_room_allocation.csv`](file:///e:/SEM%207/operation%20research/project/results/phase4_stage2_final/stage2_2198_room_allocation.csv)  
- [`results/phase4_stage2_final/room_validation_2198.json`](file:///e:/SEM%207/operation%20research/project/results/phase4_stage2_final/room_validation_2198.json)  
- [`results/phase4_stage2_final/phase44_2198_results.json`](file:///e:/SEM%207/operation%20research/project/results/phase4_stage2_final/phase44_2198_results.json)  
- [`results/phase4_stage2_final/phase44_2198_report.md`](file:///e:/SEM%207/operation%20research/project/results/phase4_stage2_final/phase44_2198_report.md)  
- [`results/phase3_11/timetable_2198_pairwise_compact.csv`](file:///e:/SEM%207/operation%20research/project/results/phase3_11/timetable_2198_pairwise_compact.csv) (Strictly Read-Only Baseline)  

**Audit Nature:** Non-destructive data accounting, period-by-period reconciliation, and independent verification. Zero CBC solver runs, zero data alterations.

---

## 1. Complete Period-by-Period Reconciliation Table

Every single period $p \in \{1, \dots, 29\}$ was independently audited against the Stage 1 timetable and Stage 2 output:

| Period | Assigned Exams (Stage 1 Timetable) | Solver Status (CBC Log) | Allocated Exams (Stage 2 CSV) | Unallocated Exams (Stage 2 CSV) | Category Classification |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **P01** | 368 | Infeasible | 359 | 9 | **Infeasible (Bottleneck: Exam 990)** |
| **P02** | 40 | OPTIMAL | 40 | 0 | **Provably Optimal** |
| **P03** | 37 | OPTIMAL | 37 | 0 | **Provably Optimal** |
| **P04** | 34 | OPTIMAL | 34 | 0 | **Provably Optimal** |
| **P05** | 84 | OPTIMAL | 84 | 0 | **Provably Optimal** |
| **P06** | 35 | OPTIMAL | 35 | 0 | **Provably Optimal** |
| **P07** | 27 | OPTIMAL | 27 | 0 | **Provably Optimal** |
| **P08** | 28 | OPTIMAL | 28 | 0 | **Provably Optimal** |
| **P09** | 41 | OPTIMAL | 41 | 0 | **Provably Optimal** |
| **P10** | 248 | FEASIBLE (TIME LIMIT) | 194 | 54 | **Feasible (Time Limit)** |
| **P11** | 162 | FEASIBLE (TIME LIMIT) | 130 | 32 | **Feasible (Time Limit)** |
| **P12** | 146 | Infeasible | 4 | 142 | **Infeasible (Bottleneck: Exam 2171)** |
| **P13** | 109 | FEASIBLE (TIME LIMIT) | 86 | 23 | **Feasible (Time Limit)** |
| **P14** | 98 | OPTIMAL | 98 | 0 | **Provably Optimal** |
| **P15** | 112 | OPTIMAL | 112 | 0 | **Provably Optimal** |
| **P16** | 76 | OPTIMAL | 76 | 0 | **Provably Optimal** |
| **P17** | 67 | OPTIMAL | 67 | 0 | **Provably Optimal** |
| **P18** | 46 | OPTIMAL | 46 | 0 | **Provably Optimal** |
| **P19** | 46 | OPTIMAL | 46 | 0 | **Provably Optimal** |
| **P20** | 63 | OPTIMAL | 63 | 0 | **Provably Optimal** |
| **P21** | 51 | OPTIMAL | 51 | 0 | **Provably Optimal** |
| **P22** | 49 | OPTIMAL | 49 | 0 | **Provably Optimal** |
| **P23** | 35 | OPTIMAL | 35 | 0 | **Provably Optimal** |
| **P24** | 39 | OPTIMAL | 39 | 0 | **Provably Optimal** |
| **P25** | 32 | OPTIMAL | 32 | 0 | **Provably Optimal** |
| **P26** | 38 | OPTIMAL | 38 | 0 | **Provably Optimal** |
| **P27** | 26 | OPTIMAL | 26 | 0 | **Provably Optimal** |
| **P28** | 30 | OPTIMAL | 30 | 0 | **Provably Optimal** |
| **P29** | 31 | OPTIMAL | 31 | 0 | **Provably Optimal** |
| **TOTAL** | **2,198** | — | **1,938** | **260** | **Identity Verified: 1,938 + 260 = 2,198** |

$$\sum_{p=1}^{29} \text{Exams}[p] = 2,198 \quad \text{(100\% Exact Match)}$$

---

## 2. Solver-Status Reconciliation

The raw solver execution logs reveal the following status breakdown across the 29 period subproblems:

| Category | Periods Count | Period IDs | Total Exams in Timetable | Assigned in CSV | Unassigned in CSV |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Provably Optimal** | **24** | 2, 3, 4, 5, 6, 7, 8, 9, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29 | **1,165** | 1,165 (100.0%) | 0 (0.0%) |
| **Feasible (Time Limit)** | **3** | 10, 11, 13 | **519** | 410 (79.0%) | 109 (21.0%) |
| **Infeasible** | **2** | 1, 12 | **514** | 363 (70.6%) | 151 (29.4%) |
| **TOTAL** | **29** | — | **2,198** | **1,938** | **260** |

### Key Resolution on Reported Counts:
1. **Optimal vs. Feasible (Time Limit) Count:**  
   The initial Phase 4.4 report text reported `23 Optimal` and `4 Feasible (Time Limit)`.  
   **Correction:** Period 14 solved to global `OPTIMAL` in 22.56 seconds with objective 3581.0. The actual count is **24 Optimal periods** (1,165 exams) and **3 Feasible (Time Limit) periods** (519 exams).
2. **Infeasible Period Exam Count:**  
   The initial Phase 4.4 report text had an arithmetic typo stating `Period 1 (368 exams) & Period 12 (146 exams)` totaled `504`.  
   **Correction:** $368 + 146 = \mathbf{514}$ exams belong to the two infeasible periods.

---

## 3. Exam-Count Reconciliation

- **Total Unique Examinations:** **2,198**
- **Examinations with Assigned Rooms in Allocation Table:** **1,938**
- **Examinations Marked `UNASSIGNED` in Allocation Table:** **260**
- **Verification Identity:**  
  $$1,938 + 260 = \mathbf{2,198} \quad \checkmark$$

### Breakdown of the 260 Unallocated Exams:
- Period 12: 142 exams (including unallocated bottleneck Exam 2171)
- Period 10: 54 exams
- Period 11: 32 exams
- Period 13: 23 exams
- Period 1: 9 exams (including unallocated bottleneck Exam 990)
- **Total Unallocated:** $142 + 54 + 32 + 23 + 9 = \mathbf{260}$ exams.

---

## 4. Student-Count Reconciliation

The student enrollment counts have been independently audited:

| Item | Description | Student Count | Verification Status |
| :---: | :--- | :---: | :---: |
| **A** | Total Registered Students in Benchmark (All 2,198 Exams) | **130,539** | Exact benchmark sum |
| **B** | Students Belonging to the 1,938 Assigned Exams | **118,755** | Recomputed from enrollment |
| **C** | Students Belonging to the 260 Unassigned Exams | **11,784** | Recomputed from enrollment |
| **D** | Students Physically Seated in Assigned Rooms | **118,755** | Matches required for assigned |
| **E** | Discrepancy (Total vs Seated) | **11,784** | Exact equal to unassigned students |
| **F** | Students in the 24 Provably Optimal Periods (Fully Seated) | **87,840** | 100% accommodated without slack |

### Key Resolution on Student Reporting:
The Phase 4.4 report stated `Required Students Seated = 130,539`.  
**Correction:** 130,539 represents the total university student registrations across all 2,198 examinations. For the 1,938 assigned examinations, exactly **118,755 students** are accommodated. The remaining **11,784 students** belong to the 260 unassigned examinations (including Exams 990 and 2171).

---

## 5. Objective Metrics Reconciliation

### A. Assigned Subset (1,938 Exams in CSV)
Independent recalculation of the metrics recorded in [`stage2_2198_room_allocation.csv`](file:///e:/SEM%207/operation%20research/project/results/phase4_stage2_final/stage2_2198_room_allocation.csv):

- **Allocated Physical Room Capacity:** 333,782 seats
- **Unused Capacity Column Sum ($d_1^+$):** **215,027** seats
- **Room Operational Penalty ($d_2^+$):** **660**
- **Split Examination Count:** **382** examinations
- **Single-Room Examinations:** **1,556** examinations ($382 + 1,556 = 1,938$)
- **Additional Room Assignments Beyond 1st ($d_3^+$):** **490** additional rooms
- **Goal Programming Objective:**
  $$Z_2 = (1.0 \times 215,027) + (1.0 \times 660) + (1.0 \times 490) = \mathbf{216,177.00} \quad \checkmark$$

### B. Provably Optimal Subset (24 Periods, 1,165 Exams)
For the 24 periods that solved to provable mathematical optimality with zero relaxation:
- **Registered Students Accommodated:** 87,840
- **Allocated Room Capacity:** 115,035 seats
- **Unused Room Capacity ($d_1^+$):** 27,195 seats
- **Room Operational Penalty ($d_2^+$):** 167
- **Split Examination Count:** 319 examinations
- **Additional Room Assignments ($d_3^+$):** 400 additional rooms
- **Objective on Optimal Periods:**
  $$Z_{2,\text{optimal}} = 27,195 + 167 + 400 = \mathbf{27,762.00} \quad \checkmark$$

---

## 6. Verification of Bottleneck Exams 990 and 2171

Both examinations were verified directly against [`timetable_2198_pairwise_compact.csv`](file:///e:/SEM%207/operation%20research/project/results/phase3_11/timetable_2198_pairwise_compact.csv), `examopt_data/exam_rooms.csv`, and `examopt_data/rooms.csv`:

### Exam 990
- **Stage 1 Fixed Period:** Period 1 (`Mon 12/15, 8:00a - 10:00a`)
- **Student Enrollment:** 15 students
- **Permissible Rooms:** Exclusively Room 351 (`[351]`)
- **Permissible Room Capacity:** 14 seats
- **Net Deficit:** $-1$ seat ($15 \le 14$ is physically impossible)
- **Infeasibility Status:** Absolute data bottleneck in Period 1 subproblem.

### Exam 2171
- **Stage 1 Fixed Period:** Period 12 (`Wed 12/17, 10:20a - 12:20p`)
- **Student Enrollment:** 77 students
- **Permissible Rooms:** Exclusively Room 312 (`[312]`)
- **Permissible Room Capacity:** 20 seats
- **Net Deficit:** $-57$ seats ($77 \le 20$ is physically impossible)
- **Infeasibility Status:** Absolute data bottleneck in Period 12 subproblem.

Neither case can be resolved without modifying room capacity, violating room eligibility, or relaxing student accommodation.

---

## 7. Independent Validation Checks

1. **Stage 1 Period Modifications:** **0** (100% Period Invariance across all 2,198 exams).
2. **Invalid Room Eligibility Violations:** **0** (Every assigned exam strictly uses rooms present in `exam_rooms.csv`).
3. **Fixed-Room Violations:** **0** (All benchmark single-room requirements satisfied).
4. **Provably Optimal Periods (24 Periods):**
   - Genuine Room Double-Bookings: **0**
   - Benchmark Dataset-Mandated Shared Room Instances: **1**
   - Capacity Violations: **0**
   - Student Accommodation: **100% accommodated**.

---

## 8. Summary of All Discrepancies Found & Corrected

| Discrepancy # | Item | Initial Report Value | Corrected Actual Value | Nature & Rationale |
| :---: | :--- | :---: | :---: | :--- |
| **1** | Infeasible Period Exam Count | 504 exams | **514 exams** | Arithmetic typo: $368 (\text{P1}) + 146 (\text{P12}) = 514$. |
| **2** | Solver Status Classification | 23 Optimal, 4 Time Limit | **24 Optimal, 3 Time Limit** | Period 14 (98 exams) solved to global `OPTIMAL` in 22.56s. |
| **3** | Solved Period Exams Sum | 1,029 optimal, 665 time limit | **1,165 optimal, 519 time limit** | Follows directly from Period 14 status correction. |
| **4** | Students Seated Scope | 130,539 seated | **118,755 seated** | 130,539 is the total student population; exactly 118,755 are accommodated in the 1,938 assigned exams (11,784 unassigned). |
| **5** | Split Terminology Distinction | Verified | **382 split exams / 490 $d_3^+$** | Confirmed distinction: 382 exams split, generating 490 additional room assignments. |

---

## 9. Final Verdict

```
FINAL AUDIT VERDICT:
PASS WITH REPORTING CORRECTIONS
```

### Justification:
1. The Stage 1 timetable input is 100% preserved with **0 period modifications**.
2. Zero solver runs were executed; all calculations were independently re-derived from the saved artifacts and original data files.
3. The underlying room assignments, objective calculations ($Z_2 = 216,177$), and authentic benchmark infeasibilities (Exams 990 & 2171) are mathematically sound and verifiable.
4. All minor arithmetic and reporting classification discrepancies in the previous summary text have been documented, reconciled, and corrected in [`results/phase4_stage2_final/phase44_2198_audit.json`](file:///e:/SEM%207/operation%20research/project/results/phase4_stage2_final/phase44_2198_audit.json).
