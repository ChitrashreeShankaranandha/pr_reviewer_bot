# app.py — Hugging Face Spaces entry point
# Redirects to the actual Streamlit app in ui/

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Run the streamlit app
exec(open("ui/streamlit_app.py").read())