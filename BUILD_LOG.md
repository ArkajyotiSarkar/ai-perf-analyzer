# Build Log: AI-Powered Performance Report Analyzer

A step-by-step record of how this project was built — including the tools setup, the code, and every error hit along the way (and how it was fixed). Written so anyone (including future-me) can understand not just *what* the code does, but *why* each decision was made.

---

## Goal

Take raw performance/load test results (JMeter-style CSV) and produce a report that serves **two audiences at once**:
1. Engineers — technical root-cause analysis
2. Non-technical stakeholders — plain-English business impact summary

All built on **$0 cost** tooling: Python, pandas, and Groq's free LLM API.

---

## Step 1 — Environment Setup

### 1a. Check/install Python

Checked for an existing Python install:
```powershell
python --version
```
Not found, so installed **Python 3.13** from python.org (chose 3.13 over the newer 3.14 for broader library compatibility, and over anything older since 3.13 is the current stable release). During install, checked **"Add python.exe to PATH"** — without this, `python` wouldn't be recognized in the terminal at all.

Also used the installer's **"Disable path length limit"** option — a one-time Windows fix that prevents errors later when dependencies create deeply nested folder paths.

### 1b. Create project folder + virtual environment

```powershell
cd ~
mkdir ai-perf-analyzer
cd ai-perf-analyzer
python -m venv venv
```

**Why a virtual environment?** It keeps this project's Python packages isolated from any other Python project on the machine — avoids version conflicts.

### 1c. Activate the virtual environment

```powershell
.\venv\Scripts\Activate
```

**Error hit:**
```
File ...\venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled on this system.
```

**Cause:** Windows PowerShell blocks running local scripts by default, as a security measure.

**Fix:**
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
This allows locally-created scripts to run for the current user only (doesn't require admin rights, doesn't weaken security system-wide). After this, activation worked — prompt showed `(venv)`.

### 1d. Install core packages

```powershell
pip install pandas jinja2 groq python-dotenv
```

- **pandas** — loads and analyzes the CSV test results
- **groq** — official Python client for Groq's free LLM API
- **python-dotenv** — loads the API key from a `.env` file instead of hardcoding it
- **jinja2** — installed for potential HTML templating (kept for the roadmap; not yet used in v1)

All installed cleanly.

---

## Step 2 — Groq API Key Setup

1. Created a free account at [console.groq.com](https://console.groq.com) — no credit card required.
2. Generated an API key under **API Keys → Create API Key**.
3. Stored it in a `.env` file in the project root:
   ```
   GROQ_API_KEY=gsk_your_key_here
   ```
4. Kept a backup copy of the key in a `.txt` file **outside** the project folder (`Documents/`), specifically so it could never accidentally get committed to Git.

**Why `.env` instead of pasting the key into the code?** Two reasons: (1) it keeps secrets out of source code so they're never accidentally shared/screenshotted, and (2) it lets the same code run for anyone by just swapping their own `.env` file, no code changes needed.

---

## Step 3 — Test the API Connection

Before building the real tool, confirmed the Groq connection worked in isolation with a minimal script (`test_connection.py`):

```python
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": "Say hello and confirm you're working, in one sentence."}]
)

print(response.choices[0].message.content)
```

Ran successfully — got a live AI response back. This confirmed the API key, the network connection, and the SDK were all working before adding any real complexity.

---

## Step 4 — Sample Test Data

Created `sample_results.csv`, formatted to match JMeter's real CSV output columns (`timeStamp`, `elapsed`, `label`, `responseCode`, `success`, `bytes`, `latency`, `threadName`) — so the tool built against this sample would also work against real JMeter output later, unchanged.

Deliberately included:
- Two abnormally slow requests (4521ms, 5102ms) on `/api/orders` — to simulate a real bottleneck
- One failed request (HTTP 500) on `/api/checkout` — to simulate an error spike

This gave the anomaly-detection logic something real to catch.

---

## Step 5 — Core Stats Engine (`analyze.py`)

Built the foundation layer using pandas:

- `compute_stats()` — total requests, error rate, average, p50/p90/p99 latency, min/max
- `find_outliers()` — flags requests abnormally slower than others with the same label
- `find_sla_violations()` — flags any request exceeding a fixed latency threshold (e.g., 1000ms)

### Error hit: outlier detection returned nothing

First version of `find_outliers()` used the **mean** as the baseline for "normal" response time:
```python
avg = group["elapsed"].mean()
threshold = avg * 3
```

Ran it — the two obviously-slow requests (4521ms, 5102ms) were **not** flagged.

**Root cause:** the mean itself was being dragged upward by the very outliers we were trying to detect. For `/api/orders` (`198, 220, 4521, 5102`), the mean is ~2510ms, pushing the 3x threshold to ~7530ms — above even the slowest request. The outliers were hiding themselves by skewing their own baseline.

**Fix:** switched to **median** instead of mean, since median isn't dragged around by extreme values:
```python
median = group["elapsed"].median()
threshold = median * 3
```

This is the statistically correct approach, but with only 10 sample rows (4 per endpoint), the sample size was still too small for the outliers to be reliably caught — a real, expected limitation, not a bug. In production with thousands of requests, this method works well because outliers are a small percentage of a much larger dataset.

**Added a second, complementary method:** `find_sla_violations()` — a fixed absolute threshold (e.g., "flag anything over 1000ms," matching how real teams define latency budgets/SLAs). This caught the slow requests immediately, regardless of sample size.

**Lesson kept in the tool:** using *both* a statistical method (median-based, works well at scale) and a fixed SLA-based method (works reliably at any scale) together — because relying on just one is fragile at small sample sizes.

---

## Step 6 — AI-Generated Report Layer

Added `generate_ai_report()`, which takes the computed stats/outliers/violations and sends them to Groq's `llama-3.3-70b-versatile` model with a structured prompt asking for two distinct outputs from the same data:

1. **Technical analysis** — for engineers, referencing specific numbers/endpoints
2. **Executive summary** — for stakeholders, plain English, framed around user/business impact

This is the core value of the tool: the same underlying data, translated for two different audiences automatically, removing the manual write-up step performance engineers normally do by hand.

First run produced a coherent, correctly-referenced report on the first try — no debugging needed here, since the earlier stats layer was already solid.

---

## Step 7 — Markdown Report Export

Initially the AI report just printed to the terminal — not something you could hand to someone or attach anywhere. Added `write_markdown_report()` to write a clean, formatted `report.md` file with:
- A stats table
- An SLA violations table
- The AI-generated technical + executive analysis

This turns the tool's output into an actual shareable deliverable, not just console text.

---

## Step 8 — CLI Support

Originally the script only worked against a hardcoded `sample_results.csv`. Added `sys.argv` handling so it accepts any file path and an optional custom SLA threshold:

```powershell
python analyze.py <path_to_csv> [sla_ms]
```

Tested with both the default threshold and a custom one (500ms) — both worked correctly. This was the step that turned it from "a script that only works on my sample" into a reusable tool that works on any real JMeter CSV export.

---

## Step 9 — Git & GitHub

### 9a. Install Git

```powershell
git --version
```

**Error hit:** `git` not recognized, even after installing Git via the official installer and opening a new PowerShell window.

**Diagnosis:** confirmed the Git executable *did* exist at `C:\Program Files\Git\bin\git.exe` (PowerShell's own error message said "does exist in the current location") — so this wasn't a broken install, it was a PATH problem: Windows hadn't refreshed its environment variables for the new terminal session.

**Fix:** a full laptop restart (not just closing/reopening PowerShell) forced Windows to reload PATH correctly. After restart, `git --version` worked.

### 9b. Protect the API key with `.gitignore`

Before touching Git commands, created `.gitignore`:
```
venv/
.env
__pycache__/
*.pyc
```

**Why this had to happen before `git add`:** if `.env` (containing the real API key) or `venv/` (thousands of installed package files) got committed and pushed to a public GitHub repo, the key could be scraped and abused by bots that actively scan GitHub for exposed credentials — often within minutes of a push. `.gitignore` tells Git to never track these files in the first place.

### 9c. Initialize repo and commit

```powershell
git init
git add .
git status   # <- checked carefully here before committing
```

**Safety check performed:** before committing, verified `.env` and `venv/` did **not** appear in the staged files list. Only the actual source files did (`.gitignore`, `analyze.py`, `report.md`, `sample_results.csv`, `test_connection.py`). This confirmed `.gitignore` was working correctly before any secrets could be exposed.

```powershell
git config --global user.name "Arkajyoti Sarkar"
git config --global user.email "sarkararkajyoti@gmail.com"
git commit -m "Initial commit: AI-powered performance report analyzer"
```

### 9d. Push to GitHub

Created a public repo on GitHub (`ai-perf-analyzer`), left it empty (no auto-generated README, since local files already existed), then:

```powershell
git remote add origin https://github.com/ArkajyotiSarkar/ai-perf-analyzer.git
git branch -M main
git push -u origin main
```

Authenticated via browser prompt. Pushed successfully — repo now live at:
**https://github.com/ArkajyotiSarkar/ai-perf-analyzer**

---

## Step 10 — README and Requirements

Added two files to make the repo understandable to an outside visitor (recruiter, interviewer, or future-me):

- **`README.md`** — explains what the tool does, why it exists, how it works, usage instructions, tech stack, and roadmap
- **`requirements.txt`** — generated via `pip freeze`, so anyone (including future-me on a new machine) can reinstall the exact same dependencies with one command

```powershell
pip freeze > requirements.txt
git add README.md requirements.txt
git commit -m "Add README and requirements.txt"
git push
```

---

## Final Result

A working, public, portfolio-ready tool that:
- Parses real-format JMeter CSV performance data
- Computes percentile latency, error rate, and flags issues via two complementary detection methods (median-based statistical outliers + fixed SLA thresholds)
- Uses a free LLM API to auto-generate both a technical and an executive-level report from the same data
- Is packaged as a proper CLI tool with documentation, dependency pinning, and secrets kept out of version control

**Total cost: $0.**

## Key lessons from building this

1. **Mean is not robust to outliers** — when the thing you're measuring *is* the outlier, don't use a baseline that the outlier itself can distort. Median (or a fixed absolute threshold) is more reliable.
2. **Small sample sizes break statistical methods** — with only a handful of data points per group, percentile/median-based detection is unreliable. Always pair statistical detection with a simple fixed-threshold fallback (SLA-based), especially early in a system's life when data volume is low.
3. **PATH issues on Windows often need a full restart**, not just a new terminal window — worth trying first before assuming a broken install.
4. **`.gitignore` must exist and be verified with `git status` *before* the first commit**, not after — once a secret is committed, deleting the file later doesn't remove it from Git history; the key would need to be revoked and regenerated.

## Roadmap (not yet built)

- Support k6/Locust output formats in addition to JMeter
- Historical trend comparison across multiple test runs
- HTML report export
