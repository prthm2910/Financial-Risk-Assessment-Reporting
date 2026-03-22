"""
LangGraph-Based Financial Risk Assessment Workflow

This module defines a multi-stage LangGraph pipeline that orchestrates:
- Financial risk assessment
- ESG (Environmental, Social, Governance) analysis
- Risk knowledge graph generation

Each node includes rate-limiting resilience for Gemini API.

"""

from langgraph.graph import StateGraph, END  # type: ignore
from typing import TypedDict, List, Annotated, Optional
from agents.risk_reporter import fin_risk_agent
from agents.esg_reporting import esg_risk_agent
from agents.knowledge_graph import create_knowledge_graph_async
import asyncio
import json
import logging
import time
import re
from google.api_core.exceptions import ResourceExhausted

# ---- Logging Setup ----
logging.basicConfig(level=logging.INFO)


# ---- Retry Delay Extractor ----
def extract_retry_seconds_from_error(e: Exception) -> Optional[int]:
    """
    Extracts the retry delay in seconds from a Gemini API ResourceExhausted error.

    Args:
        e (Exception): The caught ResourceExhausted exception.

    Returns:
        Optional[int]: The parsed number of seconds to wait before retrying.
    """
    try:
        match = re.search(r"retry_delay\s*{\s*seconds:\s*(\d+)", str(e))
        if match:
            return int(match.group(1))
    except Exception as parse_err:
        logging.warning(f"⚠️ Failed to parse retry delay: {parse_err}")
    return None


# ---- Retry Wrappers ----
def retry_with_delay(func, *args, max_retries=6, **kwargs):
    """
    Synchronously retries a function on ResourceExhausted errors, respecting retry delay headers.

    Args:
        func: The function to call.
        max_retries (int): Maximum number of retries before failing.

    Returns:
        Any: Result of the called function.
    """
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except ResourceExhausted as e:
            if attempt >= max_retries - 1:
                logging.error(f"❌ Max retries hit. Final failure: {e}")
                raise
            retry_seconds = extract_retry_seconds_from_error(e)
            wait_time = retry_seconds or (2 ** attempt) + (attempt * 0.5)
            logging.warning(f"⏳ Rate limit hit. Retrying in {wait_time:.1f} seconds (attempt {attempt+1})...")
            time.sleep(wait_time)


async def async_retry_with_delay(func, *args, max_retries=6, **kwargs):
    """
    Asynchronously retries a coroutine on ResourceExhausted errors, respecting retry delay headers.

    Args:
        func: The async function to call.
        max_retries (int): Maximum number of retries before failing.

    Returns:
        Any: Result of the awaited function.
    """
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except ResourceExhausted as e:
            if attempt >= max_retries - 1:
                logging.error(f"❌ Max retries hit. Final failure: {e}")
                raise
            retry_seconds = extract_retry_seconds_from_error(e)
            wait_time = retry_seconds or (2 ** attempt) + (attempt * 0.5)
            logging.warning(f"⏳ Rate limit hit. Retrying in {wait_time:.1f} seconds (attempt {attempt+1})...")
            await asyncio.sleep(wait_time)


# ---- LangGraph State Definition ----
class GraphState(TypedDict):
    """
    Represents the intermediate and final state of the LangGraph workflow.
    """
    company_name: Annotated[str, "Name of the company"]
    financial_risks: List[dict]
    esg_report: List[dict]
    risk_graph: dict


# ---- Workflow Nodes ----
def start_node(state: GraphState) -> dict:
    """
    Initial node: validates input and starts the graph.

    Args:
        state (GraphState): Initial state.

    Returns:
        dict: Empty output to continue graph.
    """
    company = state.get("company_name")
    if not company or not isinstance(company, str):
        raise ValueError("Missing or invalid 'company_name' in input.")
    logging.info(f"🚀 Starting graph for: {company}")
    return {}


def run_risk_reporter(state: GraphState) -> dict:
    """
    Executes the financial risk agent with retry logic.

    Args:
        state (GraphState): Current workflow state.

    Returns:
        dict: Output containing financial_risks.
    """
    logging.info("🔍 Running risk reporter (with rate limit protection)...")
    try:
        risks = retry_with_delay(fin_risk_agent, state["company_name"])
        logging.info(f"✅ Risk reporter completed with {len(risks)} items.") # type: ignore
    except Exception as e:
        logging.error(f"❌ Fatal error in risk reporter: {e}")
        raise
    return {"financial_risks": risks}


def run_esg_reporting(state: GraphState) -> dict:
    """
    Executes the ESG reporting agent with retry logic.

    Args:
        state (GraphState): Current workflow state.

    Returns:
        dict: Output containing esg_report.
    """
    logging.info("🌱 Running ESG reporter (with rate limit protection)...")
    try:
        esg_data = retry_with_delay(esg_risk_agent, state["company_name"])
        logging.info(f"✅ ESG reporting completed with {len(esg_data)} items.") # type: ignore
    except Exception as e:
        logging.error(f"❌ Fatal error in ESG reporter: {e}")
        raise
    return {"esg_report": esg_data}


async def run_knowledge_graph(state: GraphState) -> dict:
    """
    Asynchronously generates a knowledge graph from financial risk data.

    Args:
        state (GraphState): Current workflow state.

    Returns:
        dict: Output containing risk_graph.
    """
    logging.info("📊 Generating Knowledge Graph from risks (with rate limit protection)...")
    try:
        kg_data = await async_retry_with_delay(create_knowledge_graph_async, state["financial_risks"])
        logging.info("✅ Knowledge Graph generation complete.")
    except Exception as e:
        logging.error(f"❌ Fatal error in Knowledge Graph: {e}")
        raise
    return {"risk_graph": kg_data}


# ---- LangGraph Compiler ----
def compile_graph():
    """
    Compiles the LangGraph pipeline with all nodes and edges.

    Returns:
        StateGraph: A compiled LangGraph object ready for execution.
    """
    builder = StateGraph(GraphState)

    builder.add_node("start", start_node)
    builder.add_node("run_risk_reporter", run_risk_reporter)
    builder.add_node("run_esg_reporting", run_esg_reporting)
    builder.add_node("run_knowledge_graph", run_knowledge_graph)

    builder.set_entry_point("start")

    builder.add_edge("start", "run_risk_reporter")
    builder.add_edge("start", "run_esg_reporting")
    builder.add_edge("run_risk_reporter", "run_knowledge_graph")
    builder.add_edge("run_knowledge_graph", END)
    builder.add_edge("run_esg_reporting", END)

    return builder.compile()


# ---- Workflow Runner ----
async def run_agent(company_name: str):
    """
    Executes the complete workflow for a given company name.

    Args:
        company_name (str): Target company name.

    Returns:
        GraphState: Final state after execution.
    """
    graph = compile_graph()

    input_state: GraphState = {
        "company_name": company_name,
        "financial_risks": [],
        "esg_report": [],
        "risk_graph": {}
    }

    final_state = await graph.ainvoke(input_state)
    return final_state


# ---- CLI Entry Point ----
if __name__ == "__main__":
    async def main():
        """
        CLI utility for running the graph interactively via terminal.
        """
        company_name = input("Enter company name: ")
        print(f"\n🚀 Running Graph for: {company_name}\n")

        final_state = await run_agent(company_name)

        print("\n🎯 Final Output State:\n")
        print(json.dumps(final_state, indent=2, ensure_ascii=False))

    asyncio.run(main())
