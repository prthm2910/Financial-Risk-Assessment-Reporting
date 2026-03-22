"""
grounded_search_tool.py

🔍 Grounded Search Tool using Google Gemini 2.5 Flash (Web-enabled)

This module defines a LangChain-compatible tool that performs a grounded web search using Google Gemini.
It enriches LLM responses by extracting verified real-world references using resolved URLs.

Dependencies:
- google-genai
- httpx
- python-dotenv
- langchain

"""

import json
import asyncio
import httpx
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types
from langchain.tools import tool  # type: ignore

@tool("grounded_search_tool", return_direct=False)
def grounded_search_tool(user_prompt: str) -> dict:
    """
    Perform a grounded search using Gemini 2.5 Flash with web grounding and return both the
    synthesized LLM response and validated references.

    Args:
        user_prompt (str): The query or topic to search (e.g., "ESG risks of MRF Tyres FY2025").

    Returns:
        dict: {
            "text": str,                          # Synthesized Gemini output
            "grounding_chunks": List[dict]        # Validated {"title": ..., "uri": ...} citations
        }

    Example:
        >>> grounded_search_tool.invoke("MRF Tyres Compliance Risk FY2025 India")
        {
            "text": "MRF Tyres may face ...",
            "grounding_chunks": [
                {"title": "Economic Times", "uri": "https://economictimes.indiatimes.com/..."}
            ]
        }

    Note:
        - Only web sources that resolve with HTTP < 400 are returned.
        - Timeout for each HEAD request is 5 seconds.
        - Uses asyncio to parallelize URL validation.
    """
    
    # Step 1: Setup Gemini Client with Web Grounding
    client = genai.Client()
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])

    # Step 2: Generate grounded content
    raw_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=config,
    )

    # Initialize response container
    response = {
        "text": raw_response.text,
        "grounding_chunks": []
    }

    async def resolve_real_url(session: httpx.AsyncClient, chunk) -> dict | None:
        """
        Resolve and validate a real URL from a web grounding chunk using an HTTP HEAD request.

        Args:
            session (httpx.AsyncClient): Active async HTTP client.
            chunk (types.WebGroundingChunk): Web chunk object from Gemini.

        Returns:
            dict: {"title": ..., "uri": ...} if valid, else None.
        """
        try:
            uri = chunk.web.uri
            title = chunk.web.title
            resp = await session.head(uri, follow_redirects=True, timeout=5.0)
            if resp.status_code < 400:
                return {"title": title, "uri": str(resp.url)}
        except Exception:
            pass
        return None

    async def process_grounding_chunks():
        """
        Extracts and resolves all valid grounding URLs from Gemini's response.
        Updates the `response["grounding_chunks"]` list.
        """
        if raw_response and hasattr(raw_response, "candidates"):
            candidates = raw_response.candidates
            if candidates and len(candidates) > 0:
                candidate = candidates[0]
                if (
                    candidate and
                    hasattr(candidate, "grounding_metadata") and
                    candidate.grounding_metadata and
                    hasattr(candidate.grounding_metadata, "grounding_chunks")
                ):
                    async with httpx.AsyncClient() as session:
                        tasks = []
                        for chunk in candidate.grounding_metadata.grounding_chunks:  # type: ignore
                            if hasattr(chunk, "web") and chunk.web is not None:
                                tasks.append(resolve_real_url(session, chunk))

                        resolved = await asyncio.gather(*tasks)
                        response["grounding_chunks"] = [r for r in resolved if r is not None]

    # Step 3: Run async URL resolver
    asyncio.run(process_grounding_chunks())

    return response


# Example usage for CLI/debug
if __name__ == "__main__":
    user_prompt = input("Enter your prompt: ")
    result = grounded_search_tool.invoke(user_prompt)
    print(json.dumps(result, indent=4))
