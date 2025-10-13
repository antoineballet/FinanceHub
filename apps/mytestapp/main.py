import os
import streamlit as st

st.set_page_config(page_title="Secrets Demo", page_icon="🔐", layout="centered")

# Prefer Streamlit Cloud secrets; fall back to environment variable.
secret = st.secrets.get("TEST_SECRET") if "TEST_SECRET" in st.secrets else os.getenv("TEST_SECRET")
source = "st.secrets" if "TEST_SECRET" in st.secrets else ("env var" if secret else "none")

st.markdown(
    f"""
    # Streamlit Community App + GitHub Secrets 🔐
    This is my first Streamlit community app with GitHub secrets,  
    **my test secret is `{secret or "⚠️ not set"}`**.
    """
)
st.caption(f"Loaded from: {source}")
st.info("Reminder: exposing secrets in the UI is only for this demo. Don't try to use it, it's a fake one.")
