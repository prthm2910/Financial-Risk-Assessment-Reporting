# InsightBestAI

## 📌 Overview

**InsightBestAI** is an AI-powered tool that streamlines financial risk analysis for professionals. Instead of manually reading through hundreds of pages of reports, articles, blogs, and PDFs, this platform scans and summarizes all relevant sources on the internet using advanced LLMs.

Whether you're an investor, analyst, or ESG-focused stakeholder, InsightBestAI helps you focus on decisions—not data gathering.

🔗 **Live App**: [Try InsightBestAI on Streamlit](https://financial-risk-assessment-reporting-prthm2910.streamlit.app/)

---

## 🚀 Features

* 🔍 **Financial Risk Analysis (Credit Risk, Operational Risk, Compliance Risk, Strategic Risk)**
* ♻️ **ESG Insights (Environmental, Social, Governance)**
* 🌐 **Force-Directed Network Graph** showing risk interdependencies
* 🧠 Powered by Google's Gemini 2.5 Flash with grounded search

---

## 🧱 Tech Stack

### Backend

* FastAPI
* LangGraph
* LangChain
* Gemini 2.5 Flash (via Gemini API)
* Pydantic

### Frontend

* Streamlit
* streamlit-searchbox

### External Services

* Google Gemini API with grounded web search

---

## ⚙️ Getting Started

### 1. Install Dependencies

Make sure you have Python installed. Then run:

```bash
uv sync  
```

### 2. Start Backend (FastAPI)

```bash
uv run uvicorn agents.main:app --reload
```

### 3. Start Frontend (Streamlit UI)

```bash
uv run streamlit run ui.py
```

---

## 🔧 Usage

### Input

* Type a listed company name into the search bar

### Output

* 🔹 Financial Risks
* 🔹 ESG Metrics & Insights
* 🔹 Force-Directed Graph of risk category dependencies

---

## ⚠️ Known Limitations

* ⏳ Output generation may take time due to Gemini's strict rate limits
* 🧾 Markdown rendering inconsistencies due to  Streamlit's internal markdown parsing force-directed graph explanation box

---

## 🧭 Future Improvements

* ⚡ Improve performance with Gemini Pro (paid tier)
* 🔗 Add support for Gemini URL-context for more grounded and document-specific analysis  
* 🔝 Upgrading to the paid tier also helps overcome rate limit restrictions and results in more accurate, grounded outputs.

---
