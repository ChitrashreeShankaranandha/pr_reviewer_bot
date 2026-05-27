"""
agents/code_parser_agent.py
Parses raw diff text into structured FileDiff objects.
Uses local SLM (gemma3:4b via Ollama) for intelligent analysis.
Falls back to rule-based parsing if Ollama is unavailable.
Populates: state.parsed_diff
"""

import re
import json
import httpx
from utils.pipeline_state import PipelineState, FileDiff, ParsedDiff


# ── Configuration ──────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"
OLLAMA_TIMEOUT = 30  # seconds


# ── Language Detection ─────────────────────────────────────────

def detect_language(filename: str) -> str:
    """Map file extension to programming language name."""
    extension_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rb": "ruby",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".rs": "rust",
        ".sql": "sql",
        ".sh": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".md": "markdown",
    }
    for ext, lang in extension_map.items():
        if filename.endswith(ext):
            return lang
    return "unknown"


# ── Rule-based Parser (fallback) ───────────────────────────────

def parse_diff_rules(raw_diff: str) -> list[FileDiff]:
    """
    Parse raw diff text into FileDiff objects using rule-based parsing.
    Used as fallback when Ollama is unavailable.
    """
    files = []
    current_filename = None
    current_patch_lines = []
    current_additions = 0
    current_deletions = 0

    lines = raw_diff.splitlines()

    for line in lines:
        if line.startswith("+++ "):
            if current_filename:
                files.append(FileDiff(
                    filename=current_filename,
                    language=detect_language(current_filename),
                    additions=current_additions,
                    deletions=current_deletions,
                    patch="\n".join(current_patch_lines)
                ))
            raw_name = line[4:].strip()
            current_filename = raw_name.lstrip("b/").lstrip("/")
            current_patch_lines = []
            current_additions = 0
            current_deletions = 0

        elif line.startswith("--- "):
            continue

        elif current_filename:
            current_patch_lines.append(line)
            if line.startswith("+") and not line.startswith("+++"):
                current_additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_deletions += 1

    if current_filename:
        files.append(FileDiff(
            filename=current_filename,
            language=detect_language(current_filename),
            additions=current_additions,
            deletions=current_deletions,
            patch="\n".join(current_patch_lines)
        ))

    return files


# ── SLM Parser via Ollama ──────────────────────────────────────

def parse_diff_with_slm(raw_diff: str) -> list[FileDiff] | None:
    """
    Use local SLM (gemma3:4b via Ollama) to intelligently parse the diff.
    Returns None if Ollama is unavailable — triggers fallback.
    """
    prompt = f"""Analyze this code diff and return a JSON array of changed files.

For each file return:
- filename: the file path
- language: programming language
- additions: number of lines added (starting with +)
- deletions: number of lines removed (starting with -)
- summary: one sentence describing what changed

Return ONLY a valid JSON array, no markdown, no explanation:
[{{"filename": "auth.py", "language": "python", "additions": 3, "deletions": 1, "summary": "Replaced hardcoded password with hash comparison"}}]

Diff to analyze:
{raw_diff[:2000]}"""

    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0}
            },
            timeout=OLLAMA_TIMEOUT
        )

        if response.status_code != 200:
            return None

        result = response.json()
        raw_text = result.get("response", "").strip()

        # Strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        # Parse JSON response
        data = json.loads(raw_text)

        # Get the full patch from rule-based parser for each file
        rule_files = {f.filename: f for f in parse_diff_rules(raw_diff)}

        files = []
        for item in data:
            filename = item.get("filename", "unknown")
            rule_file = rule_files.get(filename)

            files.append(FileDiff(
                filename=filename,
                language=item.get("language", detect_language(filename)),
                additions=item.get("additions", rule_file.additions if rule_file else 0),
                deletions=item.get("deletions", rule_file.deletions if rule_file else 0),
                patch=rule_file.patch if rule_file else ""
            ))

        return files if files else None

    except Exception as e:
        print(f"[CodeParserAgent] Ollama unavailable: {e}")
        return None


# ── Summary ────────────────────────────────────────────────────

def summarize_diff(files: list[FileDiff]) -> str:
    """Create a human-readable one-line summary of the diff."""
    if not files:
        return "No files changed."
    total_additions = sum(f.additions for f in files)
    total_deletions = sum(f.deletions for f in files)
    filenames = ", ".join(f.filename for f in files)
    count = len(files)
    return (
        f"{count} file{'s' if count != 1 else ''} changed: "
        f"{filenames} "
        f"(+{total_additions} additions, -{total_deletions} deletions)"
    )


# ── Agent Entrypoint ───────────────────────────────────────────

def run(state: PipelineState) -> PipelineState:
    """Main Code Parser Agent entrypoint."""
    print("[CodeParserAgent] Starting...")

    if not state.raw_diff:
        error_msg = "CodeParserAgent: No raw diff available in state."
        print(f"[CodeParserAgent] ERROR: {error_msg}")
        state.errors.append(error_msg)
        return state

    try:
        # Try SLM first
        print("[CodeParserAgent] Attempting SLM parse via Ollama (gemma3:4b)...")
        files = parse_diff_with_slm(state.raw_diff)

        if files:
            print(f"[CodeParserAgent] SLM parse successful — {len(files)} files")
        else:
            # Fallback to rule-based parsing
            print("[CodeParserAgent] Falling back to rule-based parsing...")
            files = parse_diff_rules(state.raw_diff)
            print(f"[CodeParserAgent] Rule-based parse — {len(files)} files")

        if not files:
            state.errors.append("CodeParserAgent: No files found in diff.")
            return state

        total_additions = sum(f.additions for f in files)
        total_deletions = sum(f.deletions for f in files)
        summary = summarize_diff(files)

        state.parsed_diff = ParsedDiff(
            files=files,
            total_additions=total_additions,
            total_deletions=total_deletions,
            summary=summary
        )

        state.current_step = "security"
        print(f"[CodeParserAgent] Done. {summary}")

    except Exception as e:
        error_msg = f"CodeParserAgent error: {str(e)}"
        print(f"[CodeParserAgent] ERROR: {e}")
        state.errors.append(error_msg)

    return state