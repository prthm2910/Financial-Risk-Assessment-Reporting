import streamlit as st
import d3
from streamlit_searchbox import st_searchbox
from streamlit_chat import message
from prompts_library.prompt import RISK_CATEGORIES, COMPANY_NAMES, STREAMLIT_CSS
from collections import defaultdict
import requests
import datetime
import os
from dotenv import load_dotenv
load_dotenv()

# Custom CSS for the entire app
st.markdown(STREAMLIT_CSS, unsafe_allow_html=True)

# --- Rate Limiting ---
RATE_LIMIT = 2

def get_today():
    return datetime.date.today().isoformat()

def check_rate_limit():
    today = get_today()
    if "api_calls" not in st.session_state:
        st.session_state.api_calls = {today: 0}
    elif today not in st.session_state.api_calls:
        st.session_state.api_calls = {today: 0}
    return st.session_state.api_calls[today] < RATE_LIMIT

def increment_rate():
    today = get_today()
    st.session_state.api_calls[today] += 1

# --- Utility Functions ---
def search_company_names(searchterm: str):
    return [s for s in COMPANY_NAMES if searchterm.lower() in s.lower()]

def render_risk_category_dropdown():
    selected_category = st.session_state.get("selected_risk_category", "ALL")
    st.subheader("Risk Categories")
    selected = st.selectbox(
        "Select a Risk Category",
        options=RISK_CATEGORIES,
        index=RISK_CATEGORIES.index(selected_category),
        key="risk_category"
    )
    st.session_state.selected_risk_category = selected

def display_risks(agent_response):
    selected_category = st.session_state.get("selected_risk_category", "ALL")
    risks = agent_response.get("financial_risks", [])

    if not risks:
        st.warning("No financial risks found.")
        return

    if selected_category == "ALL":
        st.subheader("All Financial Risks")
    else:
        st.subheader(f"{selected_category} Risks")

    shown = 0
    for risk in risks:
        categories = risk.get("risk_category", [])
        if selected_category == "ALL" or selected_category in categories:
            with st.expander(f"{risk['risk_title']}"):
                st.markdown(f"**Description:**\n{risk['description']}")
                st.markdown("---")
                st.markdown(f"- **Severity:** {risk.get('severity', 'N/A')}")
                st.markdown(f"- **Impact:** {risk.get('impact', 'N/A')}")
                if risk.get("mitigation"):
                    st.markdown(f"**Mitigation:**\n{risk['mitigation']}")
                if risk.get("citations"):
                    st.markdown("**References:**")
                    for cite in risk["citations"]:
                        st.markdown(f"- [{cite['title']}]({cite['url']})")
            shown += 1

    if shown == 0:
        st.warning(f"No risks found in category: {selected_category}")


def render_esg_section(agent_response):
    esg_items = agent_response.get("esg_report", [])
    if not esg_items:
        st.warning("No ESG data found.")
        return

    st.title("ESG Metrics Overview")
    esg_data = defaultdict(lambda: {"points": [], "sources": []})
    for item in esg_items:
        category = item.get("esg_category", "Unknown")
        description = item.get("description", "")
        lines = [line.strip() for line in description.split("\n") if line.strip()]
        esg_data[category]["points"].extend(lines)
        esg_data[category]["sources"].extend(item.get("citations", []))

    for category, data in esg_data.items():
        with st.expander(category):
            for point in data["points"]:
                st.markdown(f"{point}")
            if data["sources"]:
                st.markdown("\n**Citations:**")
                for source in data["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']})")

def home_page():
    st.markdown("""
    <div class="header-container">
        <div class="title">InsightBestAI</div>
        <div class="byline">Let AI do the reading, so you can focus on the reasoning.</div>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        col1, col2, col3 = st.columns([1, 6, 1])
        with col2:
            selected_value = st_searchbox(
                search_company_names,
                placeholder="Search for a company...",
                key="ai_searchbox"
            )

    if selected_value:
        st.session_state.search_query = selected_value
        st.session_state.current_page = "results"
        st.rerun()

def results_page():
    query = st.session_state.get('search_query', 'No query found')

    # Check if response already cached
    if "agent_response" not in st.session_state:
        if not check_rate_limit():
            st.error("❌ Rate limit exceeded. Please try again tomorrow.")
            return

        with st.spinner("🔍 Analyzing risks and generating ESG insights... This may take a few minutes. Your Patience is highly appreciated🫡"):
            try:
                response = requests.post(
                    os.getenv('API_ENDPOINT'),   # type: ignore
                    json={"company_name": query}
                )
                response.raise_for_status()
                st.session_state.agent_response = response.json()
                increment_rate()
                st.success("✅ Risk analysis complete!")
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Failed to contact backend:\n{e}")
                return

    agent_response = st.session_state.agent_response

    st.markdown(f"""
    <div class="results-header">
        <h2 style="color: #4f8bf9; font-family: 'Poppins', sans-serif;">
            Results for: \"{query}\"
        </h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="risk-section">
        <h3 style="color: #2d3748; font-family: 'Poppins', sans-serif;">
            Financial Risk Analysis
        </h3>
    </div>
    """, unsafe_allow_html=True)

    render_risk_category_dropdown()
    display_risks(agent_response)
    d3.get_graph(agent_response.get("risk_graph", {}))
    render_esg_section(agent_response)

    if st.button("← Back to Search"):
        st.session_state.current_page = "home"
        for key in ["agent_response", "search_query", "ai_searchbox"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

def main():
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "home"
    if 'selected_risk_category' not in st.session_state:
        st.session_state.selected_risk_category = "ALL"

    if st.session_state.current_page == "home":
        home_page()
    elif st.session_state.current_page == "results":
        results_page()

if __name__ == "__main__":
    main()
