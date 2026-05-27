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

Five specialized agents communicate via structured Pydantic state handoffs — each agent does exactly one job and passes its output to the next.

```
Input (PR URL or pasted diff)
         ↓
  Code Fetcher Agent       →  Fetches PR diff via GitHub API or paste
         ↓
  Code Parser Agent        →  Parses diff into structured FileDiff objects
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
| **Security Review** | OWASP Top 10 vulnerability analysis with severity tagging | `security_findings` |
| **Style & Quality** | Scores readability, naming, complexity, best practices (0–10) | `quality_score` |
| **Summary** | Aggregates all findings into final verdict and action items | `review_summary` |

## Design Principles

| Principle | Implementation |
|---|---|
| **vLLM Ready** | Code Parser Agent designed for SLM via vLLM inference server |
| **SLM Optimized** | CodeLlama-7B / Mistral-7B for fast, cheap code parsing |
| **Task-based LLM** | Each agent has exactly one responsibility |
| **Coding Agent** | Full system reads, understands, and critiques code |
| **Agent-to-Agent** | LangGraph passes structured Pydantic state between agents |

## Tech Stack

- **Orchestration**: LangGraph
- **LLMs**: GPT-4o-mini (OpenAI)
- **Validation**: Pydantic v2
- **GitHub Integration**: PyGithub
- **UI**: Streamlit
- **Deployment**: Hugging Face Spaces

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
# Expected: 84 passed
```

## Sample Diffs

Three sample diffs are included in `data/sample_diffs/`:

| File | Expected Verdict | Tests |
|---|---|---|
| `vulnerable_auth.py.diff` | ❌ REJECTED | SQL injection + hardcoded password |
| `command_injection.py.diff` | ❌ REJECTED | Command injection via shell=True |
| `clean_utils.py.diff` | ✅ APPROVED | Clean code, no issues |

## Agent Prompts

Each agent uses a specialized system prompt:

- **Security Agent**: OWASP Top 10 checklist prompt — returns structured JSON findings with severity, category, and recommendation per issue
- **Style Agent**: Senior engineer rubric — scores readability, naming, complexity, best practices 0-10
- **Summary Agent**: Engineering lead synthesizer — aggregates all findings into verdict + action items

## 📁 Project Structure

```
pr_reviewer_bot/
├── agents/
│   ├── code_fetcher_agent.py      
│   ├── code_parser_agent.py       
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
