"""Module: knowledge_graph

Generates a risk dependency graph from financial risk descriptions using
Google Gemini's structured output capabilities via LangChain.

This module is used to transform natural language risk descriptions into a
structured graph (nodes and edges) for visualization and semantic understanding.

Dependencies:
- Google Generative AI SDK (Gemini 2.5)
- LangChain
- Pydantic
- Backoff for retry handling
"""

from dotenv import load_dotenv
load_dotenv()

import time
import asyncio
import re
import logging
import backoff  # type: ignore
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
from pydantic import BaseModel, Field
from prompts_library.prompt import RISK_PARSER_PROMPT
from google.api_core.exceptions import ResourceExhausted

# Set up logging
logging.basicConfig(level=logging.INFO)


class RiskAssessmentNode(BaseModel):
    """
    Represents a single node in the risk knowledge graph.

    Attributes:
        id (int): Unique identifier for the node.
        name (str): Title of the risk factor.
        description (str): Description of the node and its dependencies.
    """
    id: int = Field(..., description="Unique identifier for the risk node")
    name: str = Field(..., description="Short name/title of the risk")
    description: str = Field(..., description="Explanation of logical connections")


class RiskLink(BaseModel):
    """
    Represents a directed relationship (edge) between two risk nodes.

    Attributes:
        source (int): ID of the source node.
        target (int): ID of the target node.
    """
    source: int = Field(..., description="ID of the source node in the relationship")
    target: int = Field(..., description="ID of the target node in the relationship")


class RiskOutput(BaseModel):
    """
    The structured output returned by the Gemini model.

    Attributes:
        nodes (List[RiskAssessmentNode]): All nodes in the graph.
        links (List[RiskLink]): Directed edges connecting the nodes.
    """
    nodes: List[RiskAssessmentNode]
    links: List[RiskLink]


def extract_retry_seconds_from_error(e: Exception) -> int:
    """
    Extracts retry delay (in seconds) from a Gemini rate limit error message.

    Args:
        e (Exception): The raised exception.

    Returns:
        int: Number of seconds to wait before retrying. Defaults to 15 if unspecified.
    """
    match = re.search(r"retry_delay\\s*{\\s*seconds:\\s*(\\d+)", str(e))
    if match:
        return int(match.group(1))
    return 15


@backoff.on_exception(
    backoff.expo,
    ResourceExhausted,
    max_tries=6,
    jitter=backoff.full_jitter,
)
async def invoke_llm(prompt: str, llm: ChatGoogleGenerativeAI) -> RiskOutput:
    """
    Calls the Gemini model with structured output parsing.

    Automatically retries on rate limit errors using exponential backoff.

    Args:
        prompt (str): The formatted prompt string for Gemini.
        llm (ChatGoogleGenerativeAI): LangChain-wrapped Gemini model.

    Returns:
        RiskOutput: Parsed graph structure with nodes and edges.

    Raises:
        ResourceExhausted: If Gemini continues to return quota errors after retries.
    """
    structured_agent = llm.with_structured_output(RiskOutput)
    try:
        return await asyncio.to_thread(structured_agent.invoke, prompt)
    except ResourceExhausted as e:
        retry_secs = extract_retry_seconds_from_error(e)
        logging.warning(f"⏳ Rate limit hit. Retrying after {retry_secs}s...")
        await asyncio.sleep(retry_secs)
        raise e


async def create_knowledge_graph_async(risk_assessment: List[dict]) -> RiskOutput:
    """
    Generates a risk knowledge graph from a list of risk descriptions.

    This function invokes Gemini's structured output parsing to convert
    unstructured risk descriptions into graph-compatible format.

    Args:
        risk_assessment (List[dict]): A list of risk objects, each with keys
            like 'title' and 'description'.

    Returns:
        RiskOutput: A graph of nodes and links representing dependencies between risks.

    Example:
        >>> risk_data = [
        >>>     {"title": "Operational Risk", "description": "..."},
        >>>     {"title": "Market Risk", "description": "..."}
        >>> ]
        >>> graph = await create_knowledge_graph_async(risk_data)
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    prompt = RISK_PARSER_PROMPT.format(risk_assessment_input=str(risk_assessment))

    start = time.time()
    response = await invoke_llm(prompt, llm)
    end = time.time()
    print(f"✅ Knowledge graph generated in {end - start:.2f} seconds")

    return response
