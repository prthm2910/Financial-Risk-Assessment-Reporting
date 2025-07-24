"""
ESG Risk Agent

This module analyzes ESG (Environmental, Social, Governance) risks for a given company
using Google's Gemini 2.5 Flash model, a ReAct agent, and a grounded web search tool.

Parallel execution is supported for different ESG categories with rate-limit retries
and citation-rich structured output.
"""


import time
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Literal

from tools.financial_year import get_current_financial_year
from tools.google_search import grounded_search_tool
from prompts_library.prompt import ESG_REPORTING_PROMPT, ESG_CATEGORIES

from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
from langgraph.prebuilt import create_react_agent  # type: ignore
from pydantic import BaseModel
import backoff  # type: ignore
from google.api_core.exceptions import ResourceExhausted


# ---- Logging Setup ----
logging.basicConfig(level=logging.INFO)


# ---- Initialize Gemini LLM ----
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")


# ---- Output Schemas ----
class Citation(BaseModel):
    """
    Represents a source citation used in the ESG report.
    """
    title: str
    url: str


class ESGReport(BaseModel):
    """
    Structured ESG insight for a specific category.
    """
    esg_category: Literal["Environment", "Social", "Governance"]
    description: str
    citations: List[Citation]


# ---- ReAct Agent Setup ----
agent = create_react_agent(
    model=llm,
    tools=[grounded_search_tool],
    response_format=ESGReport
)


# ---- Retry Logic ----
def extract_retry_seconds_from_error(e: Exception) -> int:
    """
    Parses the retry delay (in seconds) from a ResourceExhausted exception.

    Args:
        e (Exception): The exception raised by Gemini API.

    Returns:
        int: Seconds to wait before retrying.
    """
    match = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)", str(e))
    if match:
        return int(match.group(1))
    return 15  # default fallback delay


@backoff.on_exception(
    backoff.expo,
    ResourceExhausted,
    max_tries=6,
    jitter=backoff.full_jitter,
)
def process_category_with_retry(category: str, company_name: str) -> dict:
    """
    Invokes the Gemini agent for a single ESG category with retry logic and dynamic backoff.
    """
    prompt = ESG_REPORTING_PROMPT.format(
        esg_category=category,
        company_name=company_name,
        financial_year=get_current_financial_year()
    )

    start = time.time()
    try:
        response = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        end = time.time()
        return {
            "category": category,
            "output": response["structured_response"].model_dump(),
            "time": end - start
        }
    except ResourceExhausted as e:
        # Attempt to extract Retry-After if provided
        retry_secs = extract_retry_seconds_from_error(e)
        logging.warning(f"⏳ Rate limit hit for {category}. Retrying after {retry_secs}s...")
        time.sleep(retry_secs)
        raise e  # Needed for backoff to work properly
    except Exception as e:
        raise e



def process_category(category: str, company_name: str) -> dict:
    """
    Wrapper around category processing to catch and report errors.

    Args:
        category (str): ESG category.
        company_name (str): Company to analyze.

    Returns:
        dict: Either a success dict with output, or error message.
    """
    try:
        return process_category_with_retry(category, company_name)
    except Exception as e:
        return {"category": category, "error": str(e)}


# ---- Main Agent Function ----
def esg_risk_agent(company_name: str) -> List[dict]:
    """
    Processes all ESG categories for a given company using parallel threads.

    Args:
        company_name (str): Company to assess.

    Returns:
        List[dict]: List of ESGReport dicts (if successful) or error entries.
    """
    results, structured_response = [], []

    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = [
            executor.submit(process_category, cat, company_name)
            for cat in ESG_CATEGORIES
        ]

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            if "error" in result:
                print(f"\n❌ {result['category']} failed: {result['error']}")
            else:
                print(f"\n✅ {result['category']} took {result['time']:.2f} seconds")
                structured_response.append(result["output"])

    return structured_response


# ---- CLI Entrypoint ----
if __name__ == "__main__":
    import json
    company = input("Enter company name : ")
    print(f"🔍 Running ESG risk assessment for: {company}")
    agent_response = esg_risk_agent(company)
    print("\n📊 Final ESG Report:\n")
    print(json.dumps(agent_response, indent=4))
