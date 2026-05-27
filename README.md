---
title: AI PR Reviewer Bot
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.45.1
app_file: app.py
pinned: true
---

# 🤖 AI PR Reviewer Bot

A multi-agent AI system that automatically reviews pull requests for security vulnerabilities and code quality using LangGraph agent-to-agent orchestration.

## 🏗️ Architecture

Six specialized agents communicate via structured Pydantic state handoffs — each agent does exactly one job and passes its output to the next.

```
Input (PR URL or pasted diff)
↓
Code Fetcher Agent       →  Fetches PR diff via GitHub API or paste
↓
Code Parser Agent        →  Parses diff into structured FileDiff objects
↓
LLM Security Guard       →  OWASP LLM Top 10 — detects prompt injection,
↓                           output manipulation, data exfiltration
┌──────────────────────────────────────┐
│ Malicious diff detected?             │
│ YES → block → jump to Summary        │
│ NO  → proceed to Security Review     │
└──────────────────────────────────────┘
↓
Security Review Agent    →  OWASP Top 10 vulnerability analysis
↓
┌──────────────────────────────────────┐
│ Critical issue found?                │
│ YES → skip to Summary                │
│ NO  → continue to Style Agent        │
└──────────────────────────────────────┘
↓
Style & Quality Agent    →  Scores readability, naming, complexity
↓
Summary Agent            →  Final verdict + action items
↓
VERDICT: ✅ APPROVED / ⚠️ NEEDS CHANGES / ❌ REJECTED
```

## 🤖 Agents

| Agent | Responsibility | Output |
|---|---|---|
| **Code Fetcher** | Connects to GitHub API or accepts pasted diff | `raw_diff` |
| **Code Parser** | Parses diff into structured FileDiff objects with language detection | `parsed_diff` |
| **LLM Security Guard** | OWASP LLM Top 10 — detects prompt injection, output manipulation, data exfiltration, excessive agency, oversized input | `llm_security_report` |
| **Security Review** | OWASP Top 10 vulnerability analysis with severity tagging | `security_findings` |
| **Style & Quality** | Scores readability, naming, complexity, best practices (0–10) | `quality_score` |
| **Summary** | Aggregates all findings into final verdict and action items | `review_summary` |

## 🛡️ Security Coverage

| Layer | Standard | Coverage |
|---|---|---|
| Code Security | OWASP Top 10 | SQL Injection, Broken Auth, Sensitive Data, XSS, Misconfiguration |
| LLM Security | OWASP LLM Top 10 | LLM01 Prompt Injection, LLM02 Output Manipulation, LLM04 Model DoS, LLM06 Data Exfiltration, LLM08 Excessive Agency |

## 🎨 Design Principles

| Principle | Implementation |
|---|---|
| **SLM** | Code Parser Agent uses gemma3:4b (4B parameter model) via Ollama for local inference |
| **vLLM Ready** | Parser interface compatible with vLLM server — swap Ollama endpoint for vLLM in config |
| **Task-based LLM** | Each agent has exactly one responsibility — no monolithic prompts |
| **Coding Agent** | Full system reads, understands, and critiques code autonomously |
| **Agent-to-Agent** | LangGraph passes structured Pydantic state between all 6 agents |

## ⚙️ Tech Stack

| Component | Technology |
|---|---|
| Agent Orchestration | LangGraph |
| Language Models | GPT-4o-mini (OpenAI) |
| Small Language Model | gemma3:4b via Ollama (local inference) |
| State Management | Pydantic v2 |
| GitHub Integration | PyGithub |
| UI | Streamlit |
| Deployment | Hugging Face Spaces |

## Setup

### 1. Clone and install
```bash
git clone https://github.com/ChitrashreeShankaranandha/pr_reviewer_bot.git
cd pr_reviewer_bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Add your keys to .env:
# OPENAI_API_KEY=your_key_here
# GITHUB_TOKEN=your_token_here
```

### 3. Run the UI
```bash
streamlit run ui/streamlit_app.py
```

### 4. Run CLI
```bash
python main.py
```

### 5. Run tests
```bash
pytest tests/ -v
# Expected: 115 passed
```

## 🧪 Sample Diffs

Three sample diffs are included in `data/sample_diffs/`:

| File | Expected Verdict | Tests |
|---|---|---|
| `vulnerable_auth.py.diff` | ❌ REJECTED | SQL injection + hardcoded password |
| `command_injection.py.diff` | ❌ REJECTED | Command injection via shell=True |
| `clean_utils.py.diff` | ✅ APPROVED | Clean code, no issues |

## 📝 Agent Prompts

Each agent uses a specialized system prompt:

- **LLM Security Guard**: OWASP LLM Top 10 pattern matching + LLM-as-judge secondary check
- **Security Agent**: OWASP Top 10 checklist — returns structured JSON findings with severity, category, and recommendation per issue
- **Style Agent**: Senior engineer rubric — scores readability, naming, complexity, best practices 0-10
- **Summary Agent**: Engineering lead synthesizer — aggregates all findings into verdict + action items

## 📁 Project Structure

```
pr_reviewer_bot/
├── agents/
│   ├── code_fetcher_agent.py
│   ├── code_parser_agent.py
│   ├── llm_security_guard.py
│   ├── security_review_agent.py
│   ├── style_quality_agent.py
│   └── summary_agent.py
├── ui/
│   └── streamlit_app.py
├── utils/
│   └── pipeline_state.py
├── tests/
├── config/
│   └── settings.yaml
├── data/
│   └── sample_diffs/
├── main.py
└── requirements.txt
```
