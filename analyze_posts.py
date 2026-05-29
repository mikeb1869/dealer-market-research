"""
DealerRefresh Post Analysis — Quantitative Pass
================================================
Run this on your posts_<timestamp>.json output from the scraper.

Install: pip install pandas matplotlib wordcloud
Run: python analyze_posts.py posts_<timestamp>.json
"""

import json
import sys
import re
from collections import Counter
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from wordcloud import WordCloud

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

# Words to exclude from frequency analysis (common but meaningless)
STOPWORDS = {
    # Original function words
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "it", "i", "we", "you", "they", "be", "are", "was",
    "have", "has", "had", "this", "that", "not", "if", "as", "so", "do",
    "just", "from", "by", "our", "my", "your", "their", "its", "can", "will",
    "would", "could", "should", "about", "up", "out", "get", "got", "been",
    "also", "more", "all", "any", "one", "there", "when", "what", "how",
    "who", "than", "then", "into", "like", "know", "think", "want", "going",
    "make", "need", "some", "no", "im", "dont", "its", "thats", "ive",
    "dont", "didnt", "doesnt", "isnt", "wasnt", "weve", "theyre", "youre",
    # Slipped-through function words
    "them", "here", "these", "only", "most", "which", "over", "now",
    "because", "don", "other", "good", "see", "way", "great", "lot",
    "very", "really", "much", "many", "well", "even", "still", "back",
    "through", "after", "before", "while", "where", "same", "few", "too",
    "those", "such", "each", "between", "being", "since", "both", "off",
    "may", "might", "let", "put", "say", "said", "using", "used", "use",
    "per", "come", "take", "things", "thing", "something", "anything",
    "everything", "nothing", "someone", "anyone", "everyone", "people",
    "person", "always", "never", "often", "ever", "already", "around",
    "without", "within", "again", "though", "however", "actually", "pretty",
    "quite", "able", "keep", "own", "new", "old", "big", "small", "long",
    "little", "right", "left", "next", "last", "first", "second", "third",
    "give", "given", "look", "looking", "feel", "feels", "felt", "find",
    "found", "seem", "seems", "try", "tried", "trying", "ask", "asked",
    "tell", "told", "show", "showed", "run", "running", "set", "sets",
    "sure", "different", "based", "maybe", "probably", "literally",
}

# Keyword categories to track — these are your signal words
# Add or remove based on what you learn as you go
KEYWORD_CATEGORIES = {
    "Inventory & Sourcing":   ["inventory", "auction", "manheim", "acv", "wholesale", "floor plan",
                                "floorplan", "sourcing", "recon", "reconditioning", "carmax",
                                "overpaying", "arbitration", "condition report"],
    "Leads & Follow-up":      ["lead", "leads", "follow up", "followup", "cro", "crm", "response",
                                "contact", "missed call", "voicemail", "text", "sms", "email"],
    "Financing & Lenders":    ["financing", "lender", "lenders", "subprime", "approval", "bank",
                                "credit", "floorplan", "rate", "interest", "bhph", "buy here"],
    "Software & Tools":       ["software", "dms", "frazer", "dealersocket", "dealertrack", "vauto",
                                "cdk", "tool", "platform", "integration", "sync", "spreadsheet",
                                "excel", "manual", "workaround"],
    "Compliance & Paperwork": ["compliance", "dmv", "title", "paperwork", "license", "regulation",
                                "ftc", "red flags", "safeguards", "deal jacket", "contract"],
    "Website & Marketing":    ["website", "seo", "google", "facebook", "ads", "marketing",
                                "listing", "cargurus", "autotrader", "cars.com", "traffic"],
    "Staffing & Operations":  ["staff", "employee", "hire", "salesperson", "manager", "turnover",
                                "training", "overhead", "cost", "margin", "profit"],
    "Fraud & Risk":           ["fraud", "scam", "fake", "identity", "stolen", "chargeback",
                                "dispute", "wire", "deposit"],
}

# Frustration signal words — posts containing these are flagged as high-signal
FRUSTRATION_SIGNALS = [
    "hate", "frustrated", "frustrating", "terrible", "awful", "worst",
    "broken", "useless", "waste", "nightmare", "manually", "by hand",
    "no way to", "wish", "annoying", "ridiculous", "impossible",
    "stuck", "workaround", "spreadsheet", "pain", "problem", "issue",
    "struggle", "difficult", "hard to", "can't figure", "nobody",
    "no one", "ignored", "ripped off", "burned", "screwed",
]

# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------

def load_posts(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        posts = json.load(f)
    df = pd.DataFrame(posts)
    df["content_lower"] = df["content"].str.lower()
    df["word_count"] = df["content"].str.split().str.len()
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    print(f"Loaded {len(df)} posts from {filepath}\n")
    return df

# ---------------------------------------------------------------------------
# ANALYSIS FUNCTIONS
# ---------------------------------------------------------------------------

def basic_stats(df):
    print("=" * 60)
    print("BASIC STATS")
    print("=" * 60)
    print(f"  Total posts          : {len(df)}")
    print(f"  Unique threads       : {df['thread_title'].nunique()}")
    print(f"  Unique authors       : {df['author'].nunique()}")
    print(f"  Avg words per post   : {df['word_count'].mean():.0f}")
    print(f"  Date range           : {df['date'].min()} → {df['date'].max()}")
    print()

    print("Posts per subforum:")
    print(df.groupby("subforum")["content"].count().to_string())
    print()


def top_threads(df, n=15):
    print("=" * 60)
    print(f"TOP {n} THREADS BY REPLY COUNT")
    print("=" * 60)
    top = (df.groupby(["thread_title", "thread_url"])["reply_count"]
             .first()
             .sort_values(ascending=False)
             .head(n))
    for i, ((title, url), count) in enumerate(top.items(), 1):
        print(f"  {i:>2}. [{count} replies] {title[:65]}")
        print(f"        {url}")
    print()


def top_authors(df, n=15):
    print("=" * 60)
    print(f"TOP {n} MOST ACTIVE AUTHORS")
    print("=" * 60)
    counts = df["author"].value_counts().head(n)
    for author, count in counts.items():
        print(f"  {count:>4} posts — {author}")
    print()


def keyword_category_hits(df):
    print("=" * 60)
    print("KEYWORD CATEGORY FREQUENCY")
    print("=" * 60)
    print("(% of posts mentioning at least one keyword in each category)\n")

    results = {}
    for category, keywords in KEYWORD_CATEGORIES.items():
        pattern = "|".join(re.escape(kw) for kw in keywords)
        hits = df["content_lower"].str.contains(pattern, na=False).sum()
        pct = hits / len(df) * 100
        results[category] = (hits, pct)
        print(f"  {hits:>4} posts ({pct:5.1f}%)  —  {category}")

    print()
    return results


def frustration_posts(df, n=20):
    print("=" * 60)
    print(f"TOP {n} HIGH-SIGNAL FRUSTRATION POSTS")
    print("=" * 60)
    print("(posts containing the most frustration signal words)\n")

    pattern = "|".join(re.escape(w) for w in FRUSTRATION_SIGNALS)
    df["frustration_hits"] = df["content_lower"].str.count(pattern)
    top = df[df["frustration_hits"] > 0].nlargest(n, "frustration_hits")

    for _, row in top.iterrows():
        print(f"  [{row['frustration_hits']} signals] {row['thread_title'][:60]}")
        # Print a snippet of the post content
        snippet = row["content"][:200].replace("\n", " ")
        print(f"  \"{snippet}...\"")
        print(f"  {row['thread_url']}")
        print()

    return df


def word_frequency(df, top_n=40):
    print("=" * 60)
    print(f"TOP {top_n} WORDS (excluding stopwords)")
    print("=" * 60)

    all_words = []
    for content in df["content_lower"]:
        words = re.findall(r"\b[a-z]{3,}\b", content)
        all_words.extend(w for w in words if w not in STOPWORDS)

    counter = Counter(all_words)
    for word, count in counter.most_common(top_n):
        bar = "█" * (count // 3)
        print(f"  {count:>5}  {word:<20} {bar}")
    print()
    return counter


def workaround_posts(df):
    print("=" * 60)
    print("POSTS MENTIONING MANUAL WORKAROUNDS")
    print("=" * 60)
    print("(spreadsheet, excel, by hand, manual, workaround)\n")

    pattern = r"spreadsheet|excel|by hand|manually|workaround|track it|keeping track"
    mask = df["content_lower"].str.contains(pattern, na=False)
    hits = df[mask]
    print(f"  Found {len(hits)} posts\n")

    for _, row in hits.iterrows():
        print(f"  Thread : {row['thread_title'][:65]}")
        snippet = row["content"][:250].replace("\n", " ")
        print(f"  Post   : \"{snippet}...\"")
        print(f"  URL    : {row['thread_url']}")
        print()

# ---------------------------------------------------------------------------
# CHARTS
# ---------------------------------------------------------------------------

def chart_category_hits(results):
    # Sort by percentage descending so highest is at top
    sorted_results = sorted(results.items(), key=lambda x: x[1][1], reverse=False)
    categories = [item[0] for item in sorted_results]
    percentages = [item[1][1] for item in sorted_results]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(categories, percentages, color="#2563eb")
    ax.set_xlabel("% of posts mentioning category")
    ax.set_title("Pain Point Category Coverage")
    ax.bar_label(bars, fmt="%.1f%%", padding=4)
    ax.set_xlim(0, max(percentages) * 1.2)
    plt.tight_layout()
    plt.savefig("category_hits.png", dpi=150)
    print("Saved: category_hits.png")


def chart_wordcloud(counter):
    wc = WordCloud(width=1200, height=600, background_color="white",
                   colormap="Blues", max_words=80)
    wc.generate_from_frequencies(counter)
    wc.to_file("wordcloud.png")
    print("Saved: wordcloud.png")


def chart_post_volume_over_time(df):
    dated = df.dropna(subset=["date"]).copy()
    if dated.empty:
        print("No date data available for timeline chart.")
        return

    dated["month"] = dated["date"].dt.to_period("M")
    monthly = dated.groupby("month").size()

    fig, ax = plt.subplots(figsize=(12, 4))
    monthly.plot(ax=ax, color="#2563eb", linewidth=2)
    ax.set_title("Post Volume Over Time")
    ax.set_xlabel("Month")
    ax.set_ylabel("Number of posts")
    plt.tight_layout()
    plt.savefig("post_volume.png", dpi=150)
    print("Saved: post_volume.png")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_posts.py posts_<timestamp>.json")
        sys.exit(1)

    filepath = sys.argv[1]
    df = load_posts(filepath)

    basic_stats(df)
    top_threads(df)
    top_authors(df)
    results = keyword_category_hits(df)
    df = frustration_posts(df)
    word_frequency(df)
    workaround_posts(df)

    print("=" * 60)
    print("GENERATING CHARTS")
    print("=" * 60)
    chart_category_hits(results)
    chart_wordcloud(word_frequency(df))
    chart_post_volume_over_time(df)

    print("\nAll done. Check your terminal output + the 3 PNG files.")


if __name__ == "__main__":
    main()