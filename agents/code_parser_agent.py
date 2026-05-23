"""
agents/code_parser_agent.py
Parses raw diff text into structured FileDiff objects.
Populates: state.parsed_diff
"""

from utils.pipeline_state import PipelineState, FileDiff, ParsedDiff


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


# ── Diff Parser ────────────────────────────────────────────────

def parse_diff(raw_diff: str) -> list[FileDiff]:
    """
    Parse raw diff text into a list of FileDiff objects.

    Raw diff format:
        --- filename.py
        +++ filename.py
        @@ ... @@
        -removed line
        +added line
         context line
    """
    files = []
    current_filename = None
    current_patch_lines = []
    current_additions = 0
    current_deletions = 0

    lines = raw_diff.splitlines()

    for line in lines:
        # New file starts
        if line.startswith("+++ "):
            # Save previous file if exists
            if current_filename:
                files.append(FileDiff(
                    filename=current_filename,
                    language=detect_language(current_filename),
                    additions=current_additions,
                    deletions=current_deletions,
                    patch="\n".join(current_patch_lines)
                ))
            # Start new file - clean up the filename
            raw_name = line[4:].strip()
            current_filename = raw_name.lstrip("b/").lstrip("/")
            current_patch_lines = []
            current_additions = 0
            current_deletions = 0

        elif line.startswith("--- "):
            # This is the "before" marker - skip, we use +++ for filename
            continue

        elif current_filename:
            current_patch_lines.append(line)
            if line.startswith("+") and not line.startswith("+++"):
                current_additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                current_deletions += 1

    # Don't forget the last file
    if current_filename:
        files.append(FileDiff(
            filename=current_filename,
            language=detect_language(current_filename),
            additions=current_additions,
            deletions=current_deletions,
            patch="\n".join(current_patch_lines)
        ))

    return files


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
        files = parse_diff(state.raw_diff)

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
        print(f"[CodeParserAgent] Parsed {len(files)} files. {summary}")

    except Exception as e:
        error_msg = f"CodeParserAgent error: {str(e)}"
        print(f"[CodeParserAgent] ERROR: {e}")
        state.errors.append(error_msg)

    return state