\# AI-Powered Performance Test Report Analyzer



Parses JMeter-style load test results, computes key performance metrics (percentiles, SLA violations, outliers), and uses an LLM (via Groq's free API) to auto-generate two things from the same data:



1\. A technical root-cause analysis for engineers

2\. A plain-English executive summary for non-technical stakeholders



\## Why



Performance test results are usually only readable by other engineers. This tool closes that gap — turning raw latency/error data into a report that both an SRE and a product manager can act on, without manual write-up time.



\## How it works



1\. Load JMeter CSV results with pandas

2\. Compute p50/p90/p99 latency, error rate, SLA violations, and statistical outliers

3\. Send the structured summary to an LLM (Llama 3.3 70B via Groq) with a prompt that asks for both a technical and executive-level summary

4\. Output a clean Markdown report



\## Usage



\\`\\`\\`bash

pip install -r requirements.txt

\# Add your Groq API key to a .env file: GROQ\_API\_KEY=your\_key\_here

python analyze.py sample\_results.csv 1000

\\`\\`\\`



Second argument (optional) is the SLA threshold in milliseconds — defaults to 1000ms.



\## Sample output



See \[report.md](report.md) for an example generated report.



\## Stack



Python, pandas, Groq API (Llama 3.3 70B, free tier), python-dotenv



\## Roadmap



\- Support k6/Locust output formats in addition to JMeter

\- Historical trend comparison across multiple test runs

\- HTML report export

