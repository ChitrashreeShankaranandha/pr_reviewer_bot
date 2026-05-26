"""
main.py
LangGraph orchestration — wires all 5 agents into an agent-to-agent pipeline.
"""

import os
from typing import Any, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

load_dotenv()

# ── Import all agents ──────────────────────────────────────────
from agents import code_fetcher_agent
from agents import code_parser_agent
from agents import security_review_agent
from agents import style_quality_agent
from agents import summary_agent
from utils.pipeline_state import PipelineState


# ── LangGraph State ────────────────────────────────────────────
# LangGraph requires a TypedDict for its internal state management.
# We bridge between this and our Pydantic PipelineState.

class GraphState(TypedDict):
    raw_input: str
    use_github: bool
    pr_metadata: Optional[Any]
    raw_diff: Optional[str]
    parsed_diff: Optional[Any]
    security_findings: Optional[Any]
    quality_score: Optional[Any]
    review_summary: Optional[Any]
    current_step: str
    skip_style: bool
    errors: list


# ── State Conversion Helpers ───────────────────────────────────

def graph_to_pipeline(state: GraphState) -> PipelineState:
    """Convert LangGraph TypedDict state to our Pydantic PipelineState."""
    return PipelineState(
        raw_input=state["raw_input"],
        use_github=state.get("use_github", False),
        pr_metadata=state.get("pr_metadata"),
        raw_diff=state.get("raw_diff"),
        parsed_diff=state.get("parsed_diff"),
        security_findings=state.get("security_findings"),
        quality_score=state.get("quality_score"),
        review_summary=state.get("review_summary"),
        current_step=state.get("current_step", "fetcher"),
        skip_style=state.get("skip_style", False),
        errors=state.get("errors", [])
    )


def pipeline_to_graph(pipeline: PipelineState) -> GraphState:
    """Convert Pydantic PipelineState back to LangGraph TypedDict."""
    return GraphState(
        raw_input=pipeline.raw_input,
        use_github=pipeline.use_github,
        pr_metadata=pipeline.pr_metadata,
        raw_diff=pipeline.raw_diff,
        parsed_diff=pipeline.parsed_diff,
        security_findings=pipeline.security_findings,
        quality_score=pipeline.quality_score,
        review_summary=pipeline.review_summary,
        current_step=pipeline.current_step,
        skip_style=pipeline.skip_style,
        errors=pipeline.errors
    )


# ── Agent Node Wrappers ────────────────────────────────────────
# Each node converts state, runs the agent, converts back.

def fetcher_node(state: GraphState) -> GraphState:
    print("\n" + "="*50)
    print("AGENT: Code Fetcher")
    print("="*50)
    pipeline = graph_to_pipeline(state)
    result = code_fetcher_agent.run(pipeline)
    return pipeline_to_graph(result)


def parser_node(state: GraphState) -> GraphState:
    print("\n" + "="*50)
    print("AGENT: Code Parser")
    print("="*50)
    pipeline = graph_to_pipeline(state)
    result = code_parser_agent.run(pipeline)
    return pipeline_to_graph(result)


def security_node(state: GraphState) -> GraphState:
    print("\n" + "="*50)
    print("AGENT: Security Review")
    print("="*50)
    pipeline = graph_to_pipeline(state)
    result = security_review_agent.run(pipeline)
    return pipeline_to_graph(result)


def style_node(state: GraphState) -> GraphState:
    print("\n" + "="*50)
    print("AGENT: Style & Quality")
    print("="*50)
    pipeline = graph_to_pipeline(state)
    result = style_quality_agent.run(pipeline)
    return pipeline_to_graph(result)


def summary_node(state: GraphState) -> GraphState:
    print("\n" + "="*50)
    print("AGENT: Summary")
    print("="*50)
    pipeline = graph_to_pipeline(state)
    result = summary_agent.run(pipeline)
    return pipeline_to_graph(result)


# ── Conditional Router ─────────────────────────────────────────

def should_skip_style(state: GraphState) -> str:
    """
    Routing logic after Security Agent.
    If critical/high issues found → skip Style Agent → go to Summary.
    Otherwise → run Style Agent.
    """
    if state.get("skip_style", False):
        print("\n[Router] Critical security found → skipping Style Agent")
        return "skip"
    print("\n[Router] Security passed → running Style Agent")
    return "continue"


# ── Build LangGraph Pipeline ───────────────────────────────────

def build_graph():
    """Construct and compile the LangGraph StateGraph."""
    graph = StateGraph(GraphState)

    # Add all agent nodes
    graph.add_node("fetcher", fetcher_node)
    graph.add_node("parser", parser_node)
    graph.add_node("security", security_node)
    graph.add_node("style", style_node)
    graph.add_node("summary", summary_node)

    # Set entry point
    graph.set_entry_point("fetcher")

    # Linear edges
    graph.add_edge("fetcher", "parser")
    graph.add_edge("parser", "security")

    # Conditional edge after security — the routing logic
    graph.add_conditional_edges(
        "security",
        should_skip_style,
        {
            "skip": "summary",      # critical issues → jump to summary
            "continue": "style"     # passed → run style review
        }
    )

    # Style always goes to summary
    graph.add_edge("style", "summary")

    # Summary is the end
    graph.add_edge("summary", END)

    return graph.compile()


# ── Public API ─────────────────────────────────────────────────

def run_pipeline(raw_input: str, use_github: bool = False) -> GraphState:
    """
    Run the full agent pipeline on a PR URL or pasted diff.

    Args:
        raw_input: GitHub PR URL (if use_github=True) or raw diff text
        use_github: Whether to fetch from GitHub API

    Returns:
        Final GraphState with all agent outputs populated
    """
    app = build_graph()

    initial_state: GraphState = {
        "raw_input": raw_input,
        "use_github": use_github,
        "pr_metadata": None,
        "raw_diff": None,
        "parsed_diff": None,
        "security_findings": None,
        "quality_score": None,
        "review_summary": None,
        "current_step": "fetcher",
        "skip_style": False,
        "errors": []
    }

    print("\n🚀 Starting PR Review Pipeline...")
    result = app.invoke(initial_state)
    print("\n✅ Pipeline Complete!")
    return result


# ── CLI Test ───────────────────────────────────────────────────

if __name__ == "__main__":
    SAMPLE_DIFF = """--- auth.py
+++ auth.py
@@ -1,8 +1,10 @@
+import hashlib
+
 def login(username, password):
-    if password == "admin123":
+    hashed = hashlib.sha256(password.encode()).hexdigest()
+    if hashed == get_stored_hash(username):
         return True
     return False

-def get_user(id):
-    query = f"SELECT * FROM users WHERE id={id}"
-    return db.execute(query)
+def get_user(user_id):
+    query = "SELECT * FROM users WHERE id=?"
+    return db.execute(query, (user_id,))"""

    result = run_pipeline(SAMPLE_DIFF, use_github=False)

    print("\n" + "="*50)
    print("FINAL RESULTS")
    print("="*50)

    if result.get("review_summary"):
        r = result["review_summary"]
        print(f"\nVerdict: {r.verdict.upper()}")
        print(f"\nSummary: {r.summary}")

        if r.security_highlights:
            print("\nSecurity:")
            for h in r.security_highlights:
                print(f"  • {h}")

        if r.quality_highlights:
            print("\nQuality:")
            for h in r.quality_highlights:
                print(f"  • {h}")

        if r.action_items:
            print("\nAction Items:")
            for i, item in enumerate(r.action_items, 1):
                print(f"  {i}. {item}")

    if result.get("errors"):
        print("\nErrors:")
        for e in result["errors"]:
            print(f"  ⚠ {e}")