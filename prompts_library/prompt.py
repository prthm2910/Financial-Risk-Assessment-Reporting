RISK_CATEGORIES = [
    "ALL",
    "Operational Risk",
    "Credit Risk",
    "Compliance Risk",
    "Strategic Risk"
]

COMPANY_NAMES = [
    "Reliance Industries Limited",
    "Tata Consultancy Services Limited",
    "HDFC Bank Limited",
    "ICICI Bank Limited",
    "Bharti Airtel Limited",
    "Infosys Limited",
    "Larsen & Toubro Limited",
    "Hindustan Unilever Limited",
    "Axis Bank Limited",
    "State Bank of India",
    "ITC Limited",
    "Bajaj Finance Limited",
    "Kotak Mahindra Bank Limited",
    "Maruti Suzuki India Limited",
    "Adani Enterprises Limited",
    "Sun Pharmaceutical Industries Limited",
    "Mahindra & Mahindra Limited",
    "UltraTech Cement Limited",
    "Tata Motors Limited",
    "Titan Company Limited",
    "Asian Paints Limited",
    "Nestle India Limited",
    "Power Grid Corporation of India Limited",
    "Adani Ports and Special Economic Zone Limited",
    "NTPC Limited",
    "Oil & Natural Gas Corporation Limited",
    "Tata Steel Limited",
    "JSW Steel Limited",
    "Bajaj Finserv Limited",
    "Dr. Reddy's Laboratories Limited",
    "Cipla Limited",
    "Grasim Industries Limited",
    "Eicher Motors Limited",
    "Hindalco Industries Limited",
    "Britannia Industries Limited",
    "Hero MotoCorp Limited",
    "IndusInd Bank Limited",
    "SBI Life Insurance Company Limited",
    "Life Insurance Corporation of India (LIC)",
    "Tech Mahindra Limited",
    "HDFC Life Insurance Company Limited",
    "Tata Consumer Products Limited",
    "Wipro Limited",
    "Coal India Limited",
    "DLF Limited",
    "Apollo Hospitals Enterprise Limited",
    "Shriram Finance Limited",
    "Adani Green Energy Limited",
    "Pidilite Industries Limited",
    "Bharat Petroleum Corporation Limited",
    "Bharat Electronics Limited",
    "UPL Limited",
    "Godrej Consumer Products Limited",
    "SBI Cards and Payment Services Limited",
    "ICICI Prudential Life Insurance Company Limited",
    "Siemens Limited",
    "LTIMindtree Limited" 
]

 
FINANCIAL_RISK_ASSESSMENT_PROMPT = """
You are a structured data assistant specializing in financial risk analysis for Indian listed companies.

Use the `grounded_search_tool` to gather factual, verifiable insights related to **'{risk_category}'** for the company **'{company_name}'**, based on the **latest available data for Financial Year {financial_year}**.

⚠️ Important Instructions:
- You must use the `grounded_search_tool` for all information gathering.
- Do **NOT** hallucinate. Only include facts that are backed by **verifiable citations**.
- Focus only on **Indian listed companies**.
- Only use **reputable sources** (e.g., Economic Times, Reuters India, Hindustan Times, Business Standard, ClearTax, Company Specific Websites, SEBI, RBI, MCA, NFRA etc) for information gathering.
- Prioritize source hierarchy in this order:
  1. **Official government-authorized filings** (e.g., SEBI, RBI, MCA, NFRA)
  2. **Company disclosures** (e.g., Annual Reports, BRSR, Financial Statements, Press Releases)
  3. **Reputable Indian business news** (e.g., Economic Times, Reuters India, Hindustan Times, Business Standard, ClearTax)

🧭 Objective:
Your task is to synthesize findings into a structured JSON format that adheres to the Pydantic model provided.

📌 Predefined Risk Categories:

RISK_CATEGORIES = {risk_categories}

Keep in mind:
- `risk_category` may include **multiple relevant categories** from the list.
- All fields must be **fact-based and citation-supported**.
- Return **strict JSON only**. No markdown, no explanation, no extra text.

### OUTPUT SCHEMA (Strict JSON):
{{
  "risk_title": "Concise Risk Title",
  "description": "Clear Elaborated explanation of the risk  with source-based insights on its nature, cause, manifestation, and relevance.",
  "risk_category": ["One or more exact entries from RISK_CATEGORIES"],
  "severity": "High | Medium | Low",
  "mitigation": "Clear Elaborated mitigation strategies  including actions taken, controls implemented, and Indian industry best practices.",
  "impact": "Clear Elaborated assessment  of the risk’s effect on the company (financially, operationally, reputationally) in the Indian context.",
  "citations": [
    {{"title": "Source title from search result", "url": "https://verifiable.indian.source"}}
  ]
}}
"""

ESG_CATEGORIES = [
    "Environmental",
    "Social",
    "Governance"
]


ESG_REPORTING_PROMPT = """
You are a structured data assistant specializing in ESG (Environmental, Social, Governance) reporting for **Indian listed companies**.

Your task is to extract factual, verifiable ESG-related disclosures based on the provided ESG category, company name, and financial year.

🔍 You must use the `grounded_search_tool` to gather the most recent, trustworthy data. No hallucination is allowed. Use only **verifiable citations**.

🛑 Do NOT include any explanation or markdown formatting around the output. Return ONLY a **strict JSON object** that conforms to the schema below.

✅ Allowed Sources (in order of preference):
1. Government and regulator portals (e.g., SEBI, MCA, RBI, MoEFCC)
2. Company disclosures (e.g., Annual Reports, BRSR, Sustainability Reports, Press Releases)
3. Reputable Indian business news (e.g., Economic Times, Reuters India, Hindustan Times, Business Standard, ClearTax)

---

🧭 Inputs:
- `esg_category`: **{esg_category}**
- `company_name`: **{company_name}**
- `financial_year`: **{financial_year}**

---

### ✅ OUTPUT FORMAT (Strict JSON Only):
{{
  "esg_category": "{esg_category}",
  "description": "- Point 1 in markdown style\\n- Point 2...\\n- Point 3...",
  "citations": [
    {{
      "title": "Source title from search result",
      "url": "https://verifiable.indian.source"
    }}
  ]
}}

---

### 📌 EXAMPLE:
Input:
- `esg_category`: "Environmental"
- `company_name`: "Infosys"
- `financial_year`: "FY24"

Output:
{{
  "esg_category": "Environmental",
  "description": "- Reduced carbon emissions by 20% in 2024.\\n- Implemented a company-wide waste recycling program.\\n- Transitioned 50% of energy usage to renewables.",
  "citations": [
    {{
      "title": "Environmental Policy",
      "url": "https://www.infosys.com/sustainability/environment-policy"
    }},
    {{
      "title": "Sustainability Blog",
      "url": "https://www.infosys.com/newsroom/sustainability-updates"
    }}
  ]
}}

---

🎯 Goal:
Return only well-grounded ESG insights backed by citations and formatted exactly as per the output schema above.
"""


RISK_PARSER_PROMPT = """


# AI Agent Prompt: Risk Assessment JSON to Pydantic-Compatible Output

You are a data transformation and reasoning engine. Your task is to parse the given list of JSON objects representing detailed risk assessments. Your goal is to transform this input into a Pydantic-compatible output that includes two lists:

1. **`nodes`** – A list of cleaned and structured risk nodes.  
2. **`links`** – A list of logical connections between risks in `{{"source": id, "target": id}}` format.

---

## ✅ You must follow these precise instructions:

### `nodes` list:

For each input risk object:

- Generate a unique, consecutive `id` (starting from 1).
- Use the original `risk_title` as the `name`, but ensure it is short enough (ideally under 100 characters) to display clearly in a visualization network graph. You may summarize or trim the title while preserving its meaning.
- Generate a `description` in **plain text** format using `\n` for newlines only:
  - Include two ` Logical Connection to:` sections that summarize the risk's relationship to *other risk types*, **inferred** intelligently from the context of the `description`, `impact`, and `mitigation` only. Don't blindly copy `description`, `impact`, and `mitigation` verbatim.

### `links` list:

- Create logical relationships between nodes by matching connections in their logical connection sections.
- If node A mentions node B’s category or risk context in its “Logical Connection to” section, create a link: `{{"source": A.id, "target": B.id}}`.
- Include reciprocal links only if both nodes reference each other logically.
- Avoid redundant links.

---

## ⚠️ Strict Rules:

- Do NOT include the `citations` key in the output.
- All plain text must use `\n` for newlines.
- Do NOT hallucinate fields or add extra metadata.

---

## 🎯 Final Output Schema:

```json
{{
  "nodes": [ {{ "id": int, "name": str, "description": str }} ],
  "links": [ {{ "source": int, "target": int }} ]
}}
```

---

## 📥 Input Placeholder:

INPUT JSON = {risk_assessment_input}

---
```

"""


STREAMLIT_CSS = """
<style>
    [data-testid="stSidebar"] {
        display: none !important;
    }
    
    .stApp {
        margin-left: 0 !important;
    }
    
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
    
    .header-container {
        background: linear-gradient(135deg, #6e8efb, #a777e3);
        padding: 2.5rem 1rem;
        border-radius: 0 0 20px 20px;
        margin-bottom: 2.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.12);
    }
    
    .title {
        font-family: 'Poppins', sans-serif;
        font-size: 3.2rem !important;
        font-weight: 700 !important;
        color: white !important;
        text-align: center;
        margin-bottom: 0.4rem !important;
        letter-spacing: 0.5px;
        text-shadow: 1px 1px 4px rgba(0,0,0,0.2);
    }
    
    .byline {
        font-family: 'Poppins', sans-serif;
        font-size: 1.2rem !important;
        font-weight: 300 !important;
        text-align: center;
        color: rgba(255,255,255,0.9) !important;
        margin-bottom: 1.5rem !important;
        letter-spacing: 0.3px;
    }
    
    [data-testid="stSearchbox"] {
        max-width: 700px;
        margin: 0 auto;
    }
    
    [data-testid="stSearchbox"] input {
        padding: 14px 20px !important;
        border-radius: 50px !important;
        border: none !important;
        box-shadow: 0 2px 12px rgba(0,0,0,0.1) !important;
        font-size: 1rem !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    [data-testid="stSearchbox"] input::placeholder {
        color: #888 !important;
        font-style: italic !important;
        opacity: 1 !important;
    }
    
    [data-testid="stSearchbox"] ul {
        border-radius: 12px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
        border: none !important;
        font-family: 'Poppins', sans-serif !important;
    }
    
    .results-header {
        margin-bottom: 2rem;
        border-bottom: 2px solid #2d3748;
        padding-bottom: 1rem;
    }
    
    .risk-expander {
        margin-bottom: 1rem;
        border-radius: 12px !important;
        border: 1px solid #e0e0e0 !important;
    }
    
    .risk-expander .streamlit-expanderHeader {
        font-family: 'Poppins', sans-serif !important;
        font-weight: 600 !important;
        color: #4f4f4f !important;
        background-color: #f8f9fa;
        padding: 0.75rem 1rem;
    }
    
    .risk-expander .streamlit-expanderContent {
        font-family: 'Poppins', sans-serif !important;
        padding: 1rem !important;
        background-color: #ffffff;
        border-radius: 0 0 12px 12px;
    }
    
    .risk-section {
        margin-top: 2.5rem;
        padding: 1.5rem;
        background-color: #f8f9fa;
        border-radius: 12px;
    }
    
    .risk-metadata {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin: 1rem 0;
        width: 100%;
    }

    .risk-box {
        background-color: #1e1e1e;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        width: 100%;
        box-shadow: 0 0 4px rgba(255, 255, 255, 0.05);
    }

    .risk-label {
        color: #bbbbbb;
        font-size: 1.25rem;
        margin-bottom: 0.4rem;
    }

    .risk-value {
        color: white;
        font-size: 1 rem;
        font-weight: 600;
        white-space: pre-wrap;
    }
    
    .risk-mitigation {
        background-color: #0e1117;
        padding: 0.8rem;
        border-radius: 8px;
        border-left: 4px solid #6e8efb;
        margin: 0.5rem 0;
    }
</style>
"""










