"""
Pain Point Summary
==================
Summarizes pain_points_raw.json into a concise ranked report.

Run: python summarize_pain_points.py pain_points_raw.json
"""

import json
import sys
from collections import Counter, defaultdict

def main():
    with open(sys.argv[1]) as f:
        data = json.load(f)

    print(f"Total pain points extracted: {len(data)}\n")

    # ---------------------------------------------------------------------------
    # 1. Count by workflow
    # ---------------------------------------------------------------------------
    workflow_counts = Counter(p.get("workflow_affected", "unknown") for p in data)
    print("=" * 55)
    print("PAIN POINTS BY WORKFLOW (ranked)")
    print("=" * 55)
    for workflow, count in workflow_counts.most_common():
        pct = count / len(data) * 100
        print(f"  {count:>4} ({pct:4.1f}%)  {workflow}")

    # ---------------------------------------------------------------------------
    # 2. Count by severity
    # ---------------------------------------------------------------------------
    severity_counts = Counter(p.get("severity", "unknown") for p in data)
    print(f"\n{'=' * 55}")
    print("BREAKDOWN BY SEVERITY")
    print("=" * 55)
    for sev in ["high", "medium", "low"]:
        count = severity_counts.get(sev, 0)
        pct = count / len(data) * 100
        print(f"  {count:>4} ({pct:4.1f}%)  {sev}")

    # ---------------------------------------------------------------------------
    # 3. High severity + workaround mentioned (best opportunities)
    # ---------------------------------------------------------------------------
    actionable = [
        p for p in data
        if p.get("severity") == "high" and p.get("workaround_mentioned")
    ]
    print(f"\n{'=' * 55}")
    print(f"HIGH SEVERITY + WORKAROUND MENTIONED ({len(actionable)} items)")
    print("Best app opportunities — pain is real, workaround is painful")
    print("=" * 55)
    # Group by workflow
    by_workflow = defaultdict(list)
    for p in actionable:
        by_workflow[p.get("workflow_affected", "unknown")].append(p)

    for workflow, items in sorted(by_workflow.items(), key=lambda x: -len(x[1])):
        print(f"\n  [{workflow.upper()}] — {len(items)} items")
        for p in items:
            print(f"    Problem   : {p['pain_point']}")
            print(f"    Workaround: {p['workaround_mentioned']}")
            print(f"    Signal    : \"{p['verbatim_signal']}\"")
            print()

    # ---------------------------------------------------------------------------
    # 4. Most common threads (where most pain is concentrated)
    # ---------------------------------------------------------------------------
    thread_counts = Counter(p.get("thread_title", "") for p in data)
    print("=" * 55)
    print("TOP 15 THREADS BY PAIN POINT DENSITY")
    print("=" * 55)
    for thread, count in thread_counts.most_common(15):
        print(f"  {count:>3}  {thread[:65]}")

    # ---------------------------------------------------------------------------
    # 5. Most common verbatim signals (recurring exact language)
    # ---------------------------------------------------------------------------
    print(f"\n{'=' * 55}")
    print("WORKFLOW BREAKDOWN: HIGH SEVERITY ONLY")
    print("=" * 55)
    high_only = [p for p in data if p.get("severity") == "high"]
    high_by_workflow = Counter(p.get("workflow_affected") for p in high_only)
    for workflow, count in high_by_workflow.most_common():
        print(f"  {count:>3}  {workflow}")

if __name__ == "__main__":
    main()