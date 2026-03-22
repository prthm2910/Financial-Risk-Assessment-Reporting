"""
This module implements the financial risk assessment agent using LangGraph and Gemini (Google Generative AI).
The agent analyzes financial risks for a given company across predefined categories, returning structured outputs
with severity, impact, mitigation strategies, and supporting citations.

Key Features:
    - Multi-threaded execution using ThreadPoolExecutor
    - Retry mechanism with exponential fallback for Gemini errors
    - Strict output validation using Pydantic
    - Modular design with clean schema definitions
"""


import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Literal, Optional

from tools.financial_year import get_current_financial_year
from tools.google_search import grounded_search_tool
from prompts_library.prompt import FINANCIAL_RISK_ASSESSMENT_PROMPT, RISK_CATEGORIES

from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
from langgraph.prebuilt import create_react_agent  # type: ignore
from pydantic import BaseModel, Field  # type: ignore

# Initialize Gemini language model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash"
)

# =========================
# ✅ Pydantic Output Schema
# =========================

class Citation(BaseModel):
    """
    Represents a citation reference for a financial risk analysis.

    Attributes:
        title (str): Title of the cited document.
        url (str): Web URL to the cited source.
    """
    title: str = Field(..., description="The title of the citation.")
    url: str = Field(..., description="The URL of the citation.")


class FinancialRiskAssessment(BaseModel):
    """
    Structured output schema for each risk category returned by the agent.

    Attributes:
        risk_title (str): Name or label of the identified risk.
        description (str): Plain-text explanation of the risk.
        risk_category (List[str]): One or more categories this risk falls into.
        severity (Literal): Severity level as High, Medium, or Low.
        mitigation (str): Suggested mitigation steps in plain text.
        impact (str): Description of how the risk may impact the company.
        citations (List[Citation]): Supporting sources or references.
    """
    risk_title: str
    description: str
    risk_category: List[str]
    severity: Literal["High", "Medium", "Low"]
    mitigation: str
    impact: str
    citations: List[Citation]


# =========================
# ✅ LangGraph ReAct Agent
# =========================

# Agent that uses Google Gemini + grounded search to output structured risk analysis
agent = create_react_agent(
    model=llm,
    tools=[grounded_search_tool],
    response_format=FinancialRiskAssessment
)

# =========================
# ✅ Retry Handler
# =========================

def extract_retry_seconds_from_error(e: Exception) -> Optional[int]:
    """
    Extracts the retry delay from a Gemini API error message, if present.

    Args:
        e (Exception): The exception raised by the Gemini call.

    Returns:
        Optional[int]: The number of seconds to wait before retrying.
    """
    match = re.search(r"retry_delay\\s*{\\s*seconds: \\s*(\\d+)", str(e))
    if match:
        return int(match.group(1))
    return None

# =========================
# ✅ Worker Function
# =========================

def process_category(category: str, company_name: str) -> dict:
    """
    Processes a single risk category by invoking the agent with a tailored prompt.

    Includes a retry mechanism to handle API rate limits and other transient failures.

    Args:
        category (str): The financial risk category to analyze.
        company_name (str): The target company name.

    Returns:
        dict: Output structure including category, parsed output, and response time.
    """
    prompt = FINANCIAL_RISK_ASSESSMENT_PROMPT.format(
        risk_categories=RISK_CATEGORIES,
        risk_category=category,
        company_name=company_name,
        financial_year=get_current_financial_year()
    )

    retry_count = 0
    while True:
        try:
            time.sleep(7)  # Prevent rapid API spamming
            start = time.time()
            response = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
            end = time.time()
            return {
                "category": category,
                "output": response["structured_response"].model_dump(),
                "time": end - start
            }
        except Exception as e:
            retry_delay = extract_retry_seconds_from_error(e) or 20
            retry_count += 1
            print(f"\n🔁 Retrying {category} in {retry_delay} seconds (Attempt {retry_count})...")
            time.sleep(retry_delay)

# =========================
# ✅ Main Agent Executor
# =========================

def fin_risk_agent(company_name: str) -> List[dict]:
    """
    Main entry point to run financial risk assessment across all defined categories.

    Executes each category in parallel using threads and aggregates structured responses.

    Args:
        company_name (str): The name of the company for which to assess risks.

    Returns:
        List[dict]: List of structured financial risk assessments per category.
    """
    results, response = [], []
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = [executor.submit(process_category, cat, company_name) for cat in RISK_CATEGORIES]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if "error" in result:
                print(f"\n❌ {result['category']} failed: {result['error']}")
            else:
                print(f"\n✅ {result['category']} took {result['time']:.2f} seconds")
                response.append(result["output"])
                print("\n\n\n\n")
    return response


if __name__ == "__main__":
    import json
    # Example usage for manual testing
    print(json.dumps(fin_risk_agent("MRF Tyres"), indent=4))
