import sys
import time
from pathlib import Path
from src.optimization_pipeline import execute_live_run

def progress(stage, pct, extra):
    t_str = time.strftime("%H:%M:%S")
    print(f"[{t_str}] {stage} ({pct*100:.1f}%): {extra}", flush=True)

if __name__ == "__main__":
    print("Starting execute_live_run with max_exams_per_period=150...", flush=True)
    res = execute_live_run(
        scope="all",
        bip_time_limit=600,
        gp_time_limit_per_period=20,
        max_exams_per_period=150,
        progress_callback=progress
    )

    print("\n================ EXECUTION FINISHED ================", flush=True)
    print(f"Run ID: {res.get('run_id')}", flush=True)
    print(f"Stage 1 Status: {res.get('stage1_status')}", flush=True)
    print(f"Stage 2 Status: {res.get('stage2_status')}", flush=True)
    print(f"Overall Verdict: {res.get('overall_verdict')}", flush=True)
