"""
solver_config.py
================
Centralized solver configuration and management module for ExamOpt.
Uses HiGHS Optimizer (via highspy / PuLP HiGHS) as the exclusive optimization solver throughout the application.

Benefits of HiGHS:
- 100% Free & Open-Source (MIT License) with ZERO license keys and ZERO license expirations.
- Completely UNLIMITED model size (handles millions of variables and constraints).
- Recognized as the fastest open-source MILP solver in the world.
- Native C++ Python binding through highspy without Windows subprocess pipe issues.
"""

import time
from typing import Dict, Any, Optional
import pulp

try:
    import highspy
    HIGHS_AVAILABLE = True
    HIGHS_VERSION = highspy.Highs().version()
except ImportError:
    highspy = None
    HIGHS_AVAILABLE = False
    HIGHS_VERSION = "Unavailable"

# Default solver tuning parameters
DEFAULT_BIP_TIME_LIMIT = 900
DEFAULT_GP_TIME_LIMIT = 20
DEFAULT_THREADS = 0
DEFAULT_MIP_GAP = 0.01


def get_solver_info() -> Dict[str, Any]:
    """
    Returns metadata about the installed HiGHS optimizer and PuLP availability.
    """
    pulp_highs_available = False
    if HIGHS_AVAILABLE:
        try:
            pulp_highs_available = pulp.HiGHS().available()
        except Exception:
            pulp_highs_available = False

    return {
        "solver_name": "HiGHS Optimizer",
        "version": HIGHS_VERSION,
        "highspy_installed": HIGHS_AVAILABLE,
        "pulp_highs_available": pulp_highs_available,
        "is_unlimited": True,
        "license": "Open Source (MIT License) — 100% Free & Unlimited",
    }


def verify_solver_status() -> Dict[str, Any]:
    """
    Lightweight health-check verifying that HiGHS optimizes successfully.
    """
    if not HIGHS_AVAILABLE:
        return {
            "is_valid": False,
            "error_message": "highspy is not installed. Install via 'pip install highspy'.",
            "details": "Missing highspy module.",
        }

    try:
        prob = pulp.LpProblem("highs_health_check", pulp.LpMinimize)
        x = pulp.LpVariable("x", 0, 1, cat=pulp.LpBinary)
        prob += x >= 1
        prob += x
        solver = pulp.HiGHS(msg=False, timeLimit=5)
        prob.solve(solver)
        if prob.status != 1 or abs(pulp.value(x) - 1.0) > 1e-4:
            return {
                "is_valid": False,
                "error_message": f"HiGHS solver returned unexpected status {prob.status}",
                "details": "Model solve failed test expectation.",
            }
    except Exception as ex:
        return {
            "is_valid": False,
            "error_message": f"HiGHS health-check encountered error: {ex}",
            "details": str(ex),
        }

    return {
        "is_valid": True,
        "error_message": None,
        "details": f"HiGHS v{HIGHS_VERSION} (MIT License, Unlimited capacity)",
    }


def get_solver(
    time_limit: int = 60,
    mip_gap: float = DEFAULT_MIP_GAP,
    threads: int = DEFAULT_THREADS,
    msg: bool = False,
) -> pulp.LpSolver:
    """
    Central factory for creating a PuLP HiGHS solver instance with unified parameters.
    Ensures HiGHS is the ONLY solver instantiated.
    """
    if not HIGHS_AVAILABLE:
        raise RuntimeError("HiGHS Optimizer is required but 'highspy' is not installed.")

    solver = pulp.HiGHS(
        msg=msg,
        timeLimit=time_limit,
        gapRel=mip_gap,
    )
    if threads > 0:
        solver.threads = threads

    return solver
