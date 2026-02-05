import streamlit as st
import requests
import pandas as pd

API_URL = "http://api:8000"

st.set_page_config(page_title="SRME — Research Intelligence", layout="wide")

st.title("🧠 SRME")
st.subheader("Semantic Research Matchmaking Engine")

tab1, tab2 = st.tabs(["🔍 Search Researchers", "📥 Ingest University"])

with tab2:
    st.header("Admin: System Ingestion")
    st.info("Ingest university faculty to build the semantic index. This process runs in the background.")
    uni_name = st.text_input("University Name", "MIT")
    dept_url = st.text_input("Faculty Directory URL", placeholder="https://physics.mit.edu/faculty/")
    if st.button("Trigger Discovery"):
        if uni_name and dept_url:
            try:
                r = requests.post(f"{API_URL}/ingest", json={
                    "university": uni_name,
                    "dept_url": dept_url
                })
                st.success(f"Job Queued: {r.json().get('task_id')}")
            except Exception as e:
                st.error(f"Error connecting to API: {e}")
        else:
            st.error("Please provide both university name and URL.")

with tab1:
    st.header("Find Your Next Collaborator")
    profile_text = st.text_area(
        "Describe your research interests:",
        placeholder="e.g., Quantum foundations, emergence of spacetime, AI for scientific discovery...",
        height=150
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        limit = st.slider("Max Papers to Search", 10, 200, 50)
        min_score = st.slider("Min Similarity Threshold", 0.0, 1.0, 0.4)

    if st.button("Match Engine: Search"):
        if profile_text:
            with st.spinner("Analyzing research landscape..."):
                try:
                    response = requests.post(f"{API_URL}/match", json={
                        "profile_text": profile_text,
                        "limit": limit,
                        "min_score": min_score
                    })
                    data = response.json()
                    
                    if not data:
                        st.warning("No matches found above threshold. Try ingesting more data!")
                    else:
                        st.success(f"Found {len(data)} potential collaborators.")
                        
                        for prof in data:
                            with st.expander(f"👤 {prof['professor']} ({prof['university']}) — Match Score: {prof['max_score']}"):
                                st.markdown("### Top Matching Papers")
                                for p in prof['papers']:
                                    st.markdown(f"- **{p['title']}** ({p['year']})")
                                    st.caption(f"Score: {round(p['score'], 4)}")
                                
                                st.info("Match Explanation: Generating via LLM reasoning engine...")
                except Exception as e:
                    st.error(f"Error connecting to API: {e}")
        else:
            st.warning("Please enter your research profile.")

st.markdown("---")
st.caption("SRME — Research Intelligence & Collaboration Discovery. Production Build.")
