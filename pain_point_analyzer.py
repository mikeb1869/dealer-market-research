"""
DealerRefresh Pain Point Analyzer
===================================
Sends batched post content to Claude API and extracts structured pain points.

Install: pip install anthropic
Run: python pain_point_analyzer.py posts_20260512_124647.json
"""

import json
import sys
import time
from collections import defaultdict
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BATCH_SIZE = 25          # posts per API call — don't go much higher than 30
DELAY_BETWEEN_BATCHES = 2  # seconds between API calls

SYSTEM_PROMPT = """You are a product researcher analyzing forum posts written by 
independent used car dealers in the United States. Your job is to extract pain 
points, frustrations, and unmet needs that could be addressed by a focused mobile 
app for small independent dealers.

You must respond ONLY with a valid JSON array. No preamble, no explanation, no 
markdown code fences. Just the raw JSON array.

Each element in the array should have exactly these fields:
{
  "pain_point": "brief description of the problem (1 sentence)",
  "workflow_affected": "one of: inventory_sourcing / lead_followup / financing / compliance / reporting / communication / software_tools / operations",
  "severity": "high / medium / low",
  "verbatim_signal": "the exact short phrase from the post that revealed this pain point",
  "workaround_mentioned": "any DIY fix they describe, or null",
  "thread_title": "the thread title provided"
}

Rules:
- Only extract pain points where a genuine operational problem is expressed
- Skip posts that are purely informational, vendor pitches, or generic discussion
- Skip posts from the perspective of a customer complaining about a dealer
- One post can produce multiple pain point entries if multiple problems are described
- Do not invent or infer pain points not clearly expressed in the text
- Severity guide: high = affects revenue or daily operations, medium = causes friction 
  but has a workaround, low = minor annoyance"""

USER_PROMPT_TEMPLATE = """Extract pain points from the following dealer forum posts.
Each post is formatted as:
THREAD: [thread title]
AUTHOR: [username]  
POST: [content]
---

{posts}"""

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def load_posts(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        posts = json.load(f)
    print(f"Loaded {len(posts)} posts from {filepath}")
    return posts


def format_batch(batch):
    """Format a list of post dicts into a readable string for the prompt."""
    lines = []
    for post in batch:
        lines.append(f"THREAD: {post['thread_title']}")
        lines.append(f"AUTHOR: {post.get('author', 'unknown')}")
        lines.append(f"POST: {post['content']}")
        lines.append("---")
    return "\n".join(lines)


def call_claude(client, batch_text, batch_num, total_batches):
    """Send one batch to Claude and return parsed pain points."""
    print(f"  Calling API for batch {batch_num}/{total_batches}...")
    
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(posts=batch_text)}
        ]
    )
    
    raw = response.content[0].text.strip()
    
    # Strip markdown fences if Claude adds them despite instructions
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
    
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"    [Warning] JSON parse failed on batch {batch_num}: {e}")
        print(f"    Raw response preview: {raw[:200]}")
        return []


def aggregate_results(all_pain_points):
    """
    Group pain points by workflow, sort by severity within each group,
    and count frequency of similar issues.
    """
    by_workflow = defaultdict(list)
    for pp in all_pain_points:
        workflow = pp.get("workflow_affected", "unknown")
        by_workflow[workflow].append(pp)

    severity_order = {"high": 0, "medium": 1, "low": 2}
    for workflow in by_workflow:
        by_workflow[workflow].sort(
            key=lambda x: severity_order.get(x.get("severity", "low"), 2)
        )

    return dict(by_workflow)


def print_summary(aggregated):
    """Print a readable summary to the terminal."""
    severity_order = {"high": 0, "medium": 1, "low": 2}
    
    print("\n" + "=" * 60)
    print("PAIN POINT ANALYSIS SUMMARY")
    print("=" * 60)

    # Count by workflow
    print("\nPain points by workflow category:")
    totals = {k: len(v) for k, v in aggregated.items()}
    for workflow, count in sorted(totals.items(), key=lambda x: -x[1]):
        high = sum(1 for p in aggregated[workflow] if p.get("severity") == "high")
        print(f"  {count:>4} total ({high} high severity)  —  {workflow}")

    # Print high severity items across all workflows
    print("\n" + "=" * 60)
    print("HIGH SEVERITY PAIN POINTS")
    print("=" * 60)
    high_severity = [p for pp in aggregated.values() for p in pp if p.get("severity") == "high"]
    for pp in high_severity:
        print(f"\n  [{pp['workflow_affected']}]")
        print(f"  Problem  : {pp['pain_point']}")
        print(f"  Signal   : \"{pp['verbatim_signal']}\"")
        if pp.get("workaround_mentioned"):
            print(f"  Workaround: {pp['workaround_mentioned']}")
        print(f"  Thread   : {pp['thread_title']}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python pain_point_analyzer.py posts_<timestamp>.json")
        sys.exit(1)

    filepath = sys.argv[1]
    posts = load_posts(filepath)

    # Filter out very short posts — not enough content for analysis
    posts = [p for p in posts if len(p.get("content", "")) > 80]
    print(f"After filtering short posts: {len(posts)} remain")

    client = Anthropic()

    # Split into batches
    batches = [posts[i:i+BATCH_SIZE] for i in range(0, len(posts), BATCH_SIZE)]
    total_batches = len(batches)
    print(f"\nProcessing {total_batches} batches of up to {BATCH_SIZE} posts each...\n")

    all_pain_points = []

    for i, batch in enumerate(batches, 1):
        batch_text = format_batch(batch)
        pain_points = call_claude(client, batch_text, i, total_batches)
        all_pain_points.extend(pain_points)
        print(f"    Extracted {len(pain_points)} pain points (running total: {len(all_pain_points)})")
        
        if i < total_batches:
            time.sleep(DELAY_BETWEEN_BATCHES)

    print(f"\nTotal pain points extracted: {len(all_pain_points)}")

    # Aggregate and save
    aggregated = aggregate_results(all_pain_points)

    # Save full results
    with open("pain_points_raw.json", "w", encoding="utf-8") as f:
        json.dump(all_pain_points, f, indent=2, ensure_ascii=False)

    # Save aggregated by workflow
    with open("pain_points_by_workflow.json", "w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    print_summary(aggregated)

    print("\n" + "=" * 60)
    print("Output files:")
    print("  pain_points_raw.json         — every extracted pain point")
    print("  pain_points_by_workflow.json — grouped and sorted by workflow")
    print("=" * 60)


if __name__ == "__main__":
    main()