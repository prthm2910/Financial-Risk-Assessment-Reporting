import json
import os
import sys
import logging
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import litellm

# 1. Setup & Environment
load_dotenv()
# Note: Rate limiting is now handled AUTOMATICALLY by the PageIndex library patch.
litellm.api_base = "https://integrate.api.nvidia.com/v1"
litellm.api_key = os.getenv("NVIDIA_API_KEY")

# MODEL SELECTION
# MODEL = "openai/moonshotai/kimi-k2-instruct"
#MODEL = "nvidia_nim/qwen/qwen2.5-7b-instruct"
MODEL = "openai/qwen/qwen3-coder-480b-a35b-instruct"
# Custom logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger("Forensic-RAG-Pro")

# Add PageIndex to path
sys.path.append(os.path.join(os.getcwd(), 'PageIndex'))
from PageIndex.utils import llm_completion 

class PageIndexChatEngine:
    def __init__(self, tree_path: str):
        logger.info(f"LOADING ENRICHED JSON TREE: {tree_path}")
        if not os.path.exists(tree_path):
            raise FileNotFoundError(f"Tree file not found: {tree_path}")

        with open(tree_path, 'r', encoding='utf-8') as f:
            self.tree_data = json.load(f)
        self.doc_name = self.tree_data.get("doc_name", "Forensic Report")
        self.structure_overview = self._get_structure_overview(self.tree_data.get("structure", []))
        logger.info(f"TREE LOADED SUCCESSFULLY. Doc: {self.doc_name}")

    def _get_structure_overview(self, structure: List[Dict[str, Any]], depth=0) -> str:
        lines = []
        for item in structure:
            indent = "  " * depth
            summary = (item.get("summary") or item.get("prefix_summary") or "")[:120].replace("\n", " ")
            lines.append(f"{indent}[ID: {item['node_id']}] {item['title']} | Content Preview: {summary}...")
            if "nodes" in item and item["nodes"]:
                lines.append(self._get_structure_overview(item["nodes"], depth + 1))
        return "\n".join(lines)

    def _get_node_by_id(self, structure: List[Dict[str, Any]], target_id: str) -> Optional[Dict[str, Any]]:
        for item in structure:
            if item.get("node_id") == target_id:
                return item
            if "nodes" in item and item["nodes"]:
                found = self._get_node_by_id(item["nodes"], target_id)
                if found: return found
        return None

    def _harvest_all_text_recursive(self, node: Dict[str, Any]) -> List[str]:
        all_text = []
        node_text = node.get("text", "").strip()
        if node_text:
            all_text.append(f"--- Section: {node.get('title', 'Untitled')} ---\n{node_text}")
        if "nodes" in node and node["nodes"]:
            for child in node["nodes"]:
                all_text.extend(self._harvest_all_text_recursive(child))
        return all_text

    def ask(self, question: str):
        print(f"\n{'='*25} LOGGING START {'='*25}")
        logger.info(f"QUESTION: {question}")

        # PHASE 1: ROUTING
        routing_prompt = (
            f"Analyze the document map and pick the MOST relevant node IDs to answer the question: '{question}'\n\n"
            f"GUIDELINES:\n"
            f"- You can pick up to 6 IDs for multi-part questions.\n"
            f"- For financials/tables, prioritize nodes with 'Financials' or 'Table' in previews.\n"
            f"- Return ONLY the 4-digit IDs separated by spaces.\n\n"
            f"MAP:\n{self.structure_overview}\n\n"
            f"Return ONLY IDs."
        )
        logger.info("PHASE 1: Routing Query...")
        route_response = llm_completion(model=MODEL, prompt=routing_prompt)

        logger.info(f"ROUTER DECISION: {route_response}")
        # Robust find: look for 4-digit IDs
        relevant_ids = re.findall(r'\d{4}', route_response)

        # PHASE 2: DEEP RETRIEVAL
        logger.info(f"PHASE 2: Harvesting context for IDs: {relevant_ids}")
        context_blocks = []
        for node_id in relevant_ids:
            node = self._get_node_by_id(self.tree_data.get("structure", []), node_id)
            if node:
                harvested = self._harvest_all_text_recursive(node)
                context_blocks.extend(harvested)

        final_context = "\n\n".join(context_blocks)
        if not final_context: 
            logger.warning("No context found for the selected IDs.")
            return "No relevant sections found in the document structure."

        # PHASE 3: SYNTHESIS
        qa_prompt = f"You are a Senior Financial Risk Analyst. Answer using the context. Cite SECTION NAMES.\n\nCONTEXT:\n{final_context}\n\nQUESTION: {question}"
        logger.info(f"PHASE 3: Reasoning over {len(final_context)} chars...")
        answer = llm_completion(model=MODEL, prompt=qa_prompt)

        print(f"{'='*25} LOGGING END {'='*25}\n")
        return answer

def run_interactive_chat():
    # Fix SyntaxWarning with raw string
    TREE_FILE = r"results/json/Godrej_Finance_Limited_Final_RAG_Tree.json"
    try:
        engine = PageIndexChatEngine(TREE_FILE)
    except Exception as e:
        logger.error(f"Engine Load Failure: {e}")
        return

    print(f"\n[READY] Recursive RAG Engine Active (Model: {MODEL})")
    print("Type 'exit' to quit.\n")

    while True:
        query = input("USER > ").strip()
        if query.lower() in ['exit', 'quit']: break
        if not query: continue
        try:
            print(f"\nANALYST:\n{engine.ask(query)}\n")
        except Exception as e:
            logger.error(f"Query Error: {e}")
        print("-" * 70)

if __name__ == "__main__":
    run_interactive_chat()

