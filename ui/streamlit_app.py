"""
ui/streamlit_app.py
Streamlit UI for the AI PR Reviewer Bot.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from dotenv import load_dotenv
load_dotenv()  # Works locally — on HF, secrets are injected automatically

# Validate required secrets are available
import os
if not os.getenv("OPENAI_API_KEY"):
    import streamlit as st
    st.error("⚠️ OPENAI_API_KEY not configured. Add it to HF Secrets in Space Settings.")
    st.stop()

from main import run_pipeline

# ── Page Config ────────────────────────────────────────────────
st.set_page_config(
    page_title="AI PR Reviewer Bot",
    page_icon="🤖",
    layout="wide"
)

# ── Styling ────────────────────────────────────────────────────
st.markdown("""
<style>
.verdict-approved {
    background: #d4edda; color: #155724;
    padding: 16px; border-radius: 8px;
    font-size: 1.4rem; font-weight: bold;
    text-align: center;
}
.verdict-needs_changes {
    background: #fff3cd; color: #856404;
    padding: 16px; border-radius: 8px;
    font-size: 1.4rem; font-weight: bold;
    text-align: center;
}
.verdict-rejected {
    background: #f8d7da; color: #721c24;
    padding: 16px; border-radius: 8px;
    font-size: 1.4rem; font-weight: bold;
    text-align: center;
}
.finding-critical { border-left: 4px solid #dc3545; padding: 8px 12px; margin: 6px 0; background: #fff5f5; border-radius: 4px; }
.finding-high     { border-left: 4px solid #fd7e14; padding: 8px 12px; margin: 6px 0; background: #fff8f0; border-radius: 4px; }
.finding-medium   { border-left: 4px solid #ffc107; padding: 8px 12px; margin: 6px 0; background: #fffdf0; border-radius: 4px; }
.finding-low      { border-left: 4px solid #28a745; padding: 8px 12px; margin: 6px 0; background: #f0fff4; border-radius: 4px; }
.agent-step { background: #f0f4ff; border-radius: 6px; padding: 8px 14px; margin: 4px 0; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────
st.title("🤖 AI PR Reviewer Bot")
st.caption("Multi-agent code review powered by LangGraph · Security · Quality · Summary")

# ── Sample Diffs ───────────────────────────────────────────────
SAMPLE_VULNERABLE = """--- auth.py
+++ auth.py
@@ -1,8 +1,6 @@
 def login(username, password):
-    hashed = hashlib.sha256(password.encode()).hexdigest()
-    if hashed == get_stored_hash(username):
-        return True
+    if password == "admin123":
+        return True
     return False

 def get_user(user_id):
-    query = "SELECT * FROM users WHERE id=?"
-    return db.execute(query, (user_id,))
+    query = f"SELECT * FROM users WHERE id={user_id}"
+    return db.execute(query)"""

SAMPLE_CLEAN = """--- utils.py
+++ utils.py
@@ -1,6 +1,10 @@
+import hashlib
+from typing import Optional
+
 def format_username(name: str) -> str:
-    return name.strip()
+    return name.strip().lower()

+def hash_value(value: str) -> str:
+    return hashlib.sha256(value.encode()).hexdigest()
+
 def is_valid_email(email: str) -> bool:
     return "@" in email and "." in email"""

# ── Input Section ──────────────────────────────────────────────
st.subheader("1. Input")

input_mode = st.radio(
    "Input mode:",
    ["Paste Diff", "GitHub PR URL"],
    horizontal=True
)

raw_input = ""

if input_mode == "Paste Diff":
    # Sample buttons
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("Load Vulnerable Sample"):
            st.session_state["sample"] = SAMPLE_VULNERABLE
    with col2:
        if st.button("Load Clean Sample"):
            st.session_state["sample"] = SAMPLE_CLEAN

    default_text = st.session_state.get("sample", "")
    raw_input = st.text_area(
        "Paste your diff here:",
        value=default_text,
        height=200,
        placeholder="--- filename.py\n+++ filename.py\n@@ ... @@\n+added line\n-removed line"
    )

else:
    raw_input = st.text_input(
        "GitHub PR URL:",
        placeholder="https://github.com/owner/repo/pull/42"
    )
    st.caption("Requires GITHUB_TOKEN in your .env file")

st.divider()

# ── Run Button ─────────────────────────────────────────────────
use_github = input_mode == "GitHub PR URL"

run_clicked = st.button(
    "▶ Run PR Review",
    type="primary",
    disabled=not raw_input.strip()
)

if run_clicked and raw_input.strip():
    # Show agent progress
    st.subheader("Pipeline Running...")

    progress_bar = st.progress(0)
    status = st.empty()

    with st.spinner("Running agent pipeline..."):
        status.markdown('<div class="agent-step">🔍 Code Fetcher Agent — fetching diff...</div>', unsafe_allow_html=True)
        progress_bar.progress(10)

        try:
            # Intercept agent logs to update progress
            status.markdown('<div class="agent-step">🔍 Code Fetcher → 📝 Parser → 🔒 Security → 🎨 Style → 📋 Summary</div>', unsafe_allow_html=True)
            progress_bar.progress(20)

            result = run_pipeline(raw_input, use_github=use_github)

            progress_bar.progress(100)
            status.markdown('<div class="agent-step">✅ All agents complete!</div>', unsafe_allow_html=True)

            st.session_state["result"] = result
            st.session_state["has_result"] = True

        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

# ── Results ─────────────────────────────────────────────────────
if st.session_state.get("has_result") and st.session_state.get("result"):
    result = st.session_state["result"]

    st.divider()

    # ── Verdict Banner ─────────────────────────────────────────
    if result.get("review_summary"):
        r = result["review_summary"]
        verdict = r.verdict

        verdict_icons = {
            "approved": "✅ APPROVED",
            "needs_changes": "⚠️ NEEDS CHANGES",
            "rejected": "❌ REJECTED"
        }
        st.markdown(
            f'<div class="verdict-{verdict}">{verdict_icons.get(verdict, verdict.upper())}</div>',
            unsafe_allow_html=True
        )
        st.markdown("")

    # ── Three columns layout ───────────────────────────────────
    col_left, col_right = st.columns([1, 1])

    # ── Left: Security Findings ────────────────────────────────
    with col_left:
        st.subheader("🔒 Security Findings")

        if result.get("security_findings"):
            sf = result["security_findings"]

            risk_colors = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
                "none": "✅"
            }
            st.markdown(f"**Overall Risk:** {risk_colors.get(sf.overall_risk, '⚪')} `{sf.overall_risk.upper()}`")

            if sf.findings:
                for finding in sf.findings:
                    st.markdown(
                        f'<div class="finding-{finding.severity}">'
                        f'<strong>[{finding.severity.upper()}] {finding.category}</strong><br>'
                        f'📄 <code>{finding.filename}</code><br>'
                        f'{finding.description}<br>'
                        f'<em>💡 {finding.recommendation}</em>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.success("No security issues found!")
        else:
            st.info("Security analysis not available.")

    # ── Right: Quality Scores ──────────────────────────────────
    with col_right:
        st.subheader("🎨 Quality Scores")

        if result.get("quality_score"):
            q = result["quality_score"]

            # Overall score prominent
            st.metric("Overall Score", f"{q.overall_score}/10")

            # Four dimension scores
            c1, c2 = st.columns(2)
            c1.metric("Readability", f"{q.readability_score}/10")
            c2.metric("Naming", f"{q.naming_score}/10")
            c3, c4 = st.columns(2)
            c3.metric("Complexity", f"{q.complexity_score}/10")
            c4.metric("Best Practices", f"{q.best_practices_score}/10")

            if q.strengths:
                st.markdown("**💪 Strengths**")
                for s in q.strengths:
                    st.markdown(f"- {s}")

            if q.improvements:
                st.markdown("**📈 Improvements**")
                for i in q.improvements:
                    st.markdown(f"- {i}")

        elif result.get("skip_style"):
            st.warning("Style review skipped — critical security issues must be fixed first.")
        else:
            st.info("Quality analysis not available.")

    st.divider()

    # ── Summary ────────────────────────────────────────────────
    st.subheader("📋 Summary")

    if result.get("review_summary"):
        r = result["review_summary"]
        st.write(r.summary)

        col1, col2 = st.columns(2)

        with col1:
            if r.security_highlights:
                st.markdown("**🔒 Security Highlights**")
                for h in r.security_highlights:
                    st.markdown(f"- {h}")

            if r.quality_highlights:
                st.markdown("**🎨 Quality Highlights**")
                for h in r.quality_highlights:
                    st.markdown(f"- {h}")

        with col2:
            if r.action_items:
                st.markdown("**✅ Action Items**")
                for i, item in enumerate(r.action_items, 1):
                    st.markdown(f"{i}. {item}")

    # ── Pipeline Info ──────────────────────────────────────────
    with st.expander("🔍 Pipeline Details"):
        if result.get("parsed_diff"):
            pd = result["parsed_diff"]
            st.markdown(f"**Files reviewed:** {len(pd.files)}")
            st.markdown(f"**Changes:** +{pd.total_additions} additions, -{pd.total_deletions} deletions")
            for f in pd.files:
                st.markdown(f"- `{f.filename}` ({f.language}): +{f.additions} / -{f.deletions}")

        if result.get("errors"):
            st.markdown("**⚠️ Pipeline Warnings:**")
            for e in result["errors"]:
                st.warning(e)

    # ── Agent Flow Diagram ─────────────────────────────────────
    with st.expander("🗺️ Agent Flow"):
        skip = result.get("skip_style", False)
        st.markdown(f"""
                    Input
                    ↓
                    ✅ Code Fetcher Agent
                    ↓
                    ✅ Code Parser Agent
                    ↓
                    ✅ Security Review Agent {"→ ⚠️ Critical found!" if skip else "→ ✅ Passed"}
                    ↓ {"(Style skipped)" if skip else ""}
                    {"⏭️ Style Agent SKIPPED" if skip else "✅ Style & Quality Agent"}
                    ↓
                    ✅ Summary Agent
                    ↓
                    🏁 Complete — Verdict: {result.get("review_summary").verdict.upper() if result.get("review_summary") else "N/A"}
                    """)