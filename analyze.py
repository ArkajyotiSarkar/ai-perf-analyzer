import os
import sys
import json
import pandas as pd
from dotenv import load_dotenv
from groq import Groq


def load_results(filepath):
    df = pd.read_csv(filepath)
    return df


def compute_stats(df):
    total_requests = len(df)
    error_count = (df["success"] == False).sum()
    error_rate = round((error_count / total_requests) * 100, 2)

    stats = {
        "total_requests": total_requests,
        "error_count": int(error_count),
        "error_rate_pct": error_rate,
        "avg_response_ms": round(df["elapsed"].mean(), 2),
        "p50_ms": round(df["elapsed"].quantile(0.50), 2),
        "p90_ms": round(df["elapsed"].quantile(0.90), 2),
        "p99_ms": round(df["elapsed"].quantile(0.99), 2),
        "max_ms": int(df["elapsed"].max()),
        "min_ms": int(df["elapsed"].min()),
    }
    return stats


def find_outliers(df, threshold_multiplier=3):
    """Flag requests significantly slower than the median for their label."""
    outliers = []
    for label, group in df.groupby("label"):
        median = group["elapsed"].median()
        threshold = median * threshold_multiplier
        slow_requests = group[group["elapsed"] > threshold]
        for _, row in slow_requests.iterrows():
            outliers.append({
                "label": label,
                "elapsed": int(row["elapsed"]),
                "group_median": round(median, 2),
                "thread": row["threadName"],
            })
    return outliers


def find_sla_violations(df, sla_ms=1000):
    """Flag any request that breaches a fixed SLA threshold."""
    violations = df[df["elapsed"] > sla_ms]
    return violations[["label", "elapsed", "threadName"]].to_dict("records")


def generate_ai_report(stats, outliers, sla_violations):
    load_dotenv()
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    prompt = f"""You are a senior performance engineer reviewing load test results.

SUMMARY STATS:
{json.dumps(stats, indent=2)}

STATISTICAL OUTLIERS (median-based):
{json.dumps(outliers, indent=2)}

SLA VIOLATIONS:
{json.dumps(sla_violations, indent=2)}

Write two short sections:

1. TECHNICAL ANALYSIS (for engineers): 2-3 sentences on likely root cause, referencing specific endpoints/numbers.

2. EXECUTIVE SUMMARY (for non-technical stakeholders): 2-3 sentences in plain English, no jargon, focused on user/business impact.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def write_markdown_report(stats, outliers, sla_violations, ai_report, output_file="report.md"):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Performance Test Report\n\n")

        f.write("## Summary Stats\n\n")
        f.write("| Metric | Value |\n|---|---|\n")
        for k, v in stats.items():
            f.write(f"| {k} | {v} |\n")

        f.write("\n## SLA Violations\n\n")
        if sla_violations:
            f.write("| Label | Elapsed (ms) | Thread |\n|---|---|---|\n")
            for v in sla_violations:
                f.write(f"| {v['label']} | {v['elapsed']} | {v['threadName']} |\n")
        else:
            f.write("None found.\n")

        f.write("\n## AI-Generated Analysis\n\n")
        f.write(ai_report + "\n")

    print(f"\nReport written to {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze.py <path_to_csv> [sla_ms]")
        print("Example: python analyze.py sample_results.csv 1000")
        sys.exit(1)

    input_file = sys.argv[1]
    sla_threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    df = load_results(input_file)
    stats = compute_stats(df)
    outliers = find_outliers(df)
    sla_violations = find_sla_violations(df, sla_ms=sla_threshold)

    print("=== Summary Stats ===")
    for k, v in stats.items():
        print(f"{k}: {v}")

    print("\n=== Outliers Detected (median-based) ===")
    if outliers:
        for o in outliers:
            print(o)
    else:
        print("None found.")

    print(f"\n=== SLA Violations (>{sla_threshold}ms) ===")
    if sla_violations:
        for v in sla_violations:
            print(v)
    else:
        print("None found.")

    report = generate_ai_report(stats, outliers, sla_violations)
    write_markdown_report(stats, outliers, sla_violations, report)