"""
agents/code_fetcher_agent.py
Fetches PR diff and metadata from GitHub API, or accepts a pasted diff directly.
Populates: state.pr_metadata, state.raw_diff
"""

import re
import os
from github import Github
from dotenv import load_dotenv
from utils.pipeline_state import PipelineState, PRMetadata

load_dotenv()


def parse_pr_url(url: str) -> tuple[str, int]:
    """
    Extract repo name and PR number from a GitHub PR URL.
    e.g. https://github.com/owner/repo/pull/42 -> ("owner/repo", 42)
    """
    pattern = r"github\.com/([^/]+/[^/]+)/pull/(\d+)"
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"Invalid GitHub PR URL: {url}")
    return match.group(1), int(match.group(2))


def fetch_from_github(pr_url: str) -> tuple[PRMetadata, str]:
    """
    Connect to GitHub API and fetch PR metadata + raw diff.
    Returns (PRMetadata, raw_diff_string)
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not found in .env")

    g = Github(token)
    repo_name, pr_number = parse_pr_url(pr_url)

    print(f"[CodeFetcherAgent] Connecting to GitHub: {repo_name} PR #{pr_number}")

    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    # Build metadata
    metadata = PRMetadata(
        pr_url=pr_url,
        repo_name=repo_name,
        pr_number=pr_number,
        title=pr.title,
        author=pr.user.login,
        base_branch=pr.base.ref,
        head_branch=pr.head.ref,
        files_changed=pr.changed_files
    )

    # Build raw diff from all changed files
    diff_parts = []
    for file in pr.get_files():
        diff_parts.append(f"--- {file.filename}")
        diff_parts.append(f"+++ {file.filename}")
        if file.patch:
            diff_parts.append(file.patch)
        diff_parts.append("")

    raw_diff = "\n".join(diff_parts)

    print(f"[CodeFetcherAgent] Fetched {pr.changed_files} files, {len(raw_diff)} chars of diff")
    return metadata, raw_diff


def fetch_from_paste(raw_input: str) -> tuple[None, str]:
    """
    User pasted a diff directly — skip GitHub API.
    Returns (None, raw_diff_string)
    """
    print(f"[CodeFetcherAgent] Using pasted diff ({len(raw_input)} chars)")
    return None, raw_input


def run(state: PipelineState) -> PipelineState:
    """Main Code Fetcher Agent entrypoint."""
    print("[CodeFetcherAgent] Starting...")

    try:
        if state.use_github:
            metadata, raw_diff = fetch_from_github(state.raw_input)
            state.pr_metadata = metadata
        else:
            _, raw_diff = fetch_from_paste(state.raw_input)

        state.raw_diff = raw_diff
        state.current_step = "parser"
        print("[CodeFetcherAgent] Done.")

    except Exception as e:
        error_msg = f"CodeFetcherAgent error: {str(e)}"
        print(f"[CodeFetcherAgent] ERROR: {e}")
        state.errors.append(error_msg)

    return state