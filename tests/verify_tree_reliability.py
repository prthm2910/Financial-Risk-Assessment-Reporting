import json
import os
import sys
from typing import List, Dict, Any
from dotenv import load_dotenv
import litellm

# 1. Setup
load_dotenv()
litellm.api_base = "https://integrate.api.nvidia.com/v1"
litellm.api_key = os.getenv("NVIDIA_API_KEY")
MODEL = "openai/meta/llama-3.1-70b-instruct"

class TreeReliabilityChecker:
    def __init__(self, tree_path: str):
        if not os.path.exists(tree_path):
            raise FileNotFoundError(f"Tree file not found: {tree_path}")
        
        with open(tree_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.doc_name = self.data.get("doc_name", "Unknown Document")
        self.nodes = self._flatten_tree(self.data.get("structure", []))
        print(f"--- Reliability Checker Initialized for: {self.doc_name} ---")
        print(f"--- Indexed {len(self.nodes)} document nodes ---\n")

    def _flatten_tree(self, structure: List[Dict[str, Any]], flat_list=None) -> List[Dict[str, Any]]:
        """Recursively flattens the hierarchical tree for easier searching."""
        if flat_list is None:
            flat_list = []
        
        for item in structure:
            # Create a searchable record for each node
            node_record = {
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "text": item.get("text", ""),
                "node_id": item.get("node_id", "")
            }
            flat_list.append(node_record)
            
            # Recurse into children if they exist
            if "nodes" in item and item["nodes"]:
                self._flatten_tree(item["nodes"], flat_list)
            elif "children" in item and item["children"]: # Handle variations in key names
                self._flatten_tree(item["children"], flat_list)
                
        return flat_list

    def retrieve_context(self, query: str, top_k: int = 3) -> str:
        """
        Simple keyword-based relevance scoring to find the best nodes.
        In a production RAG, this would use embeddings.
        """
        query_words = set(query.lower().split())
        scored_nodes = []

        for node in self.nodes:
            score = 0
            search_blob = (node["title"] + " " + node["summary"] + " " + node["text"]).lower()
            
            # Basic keyword overlap score
            for word in query_words:
                if len(word) > 3: # Ignore small words
                    score += search_blob.count(word)
            
            if score > 0:
                scored_nodes.append((score, node))

        # Sort by score descending
        scored_nodes.sort(key=lambda x: x[0], reverse=True)
        
        # Build context string from top results
        context_parts = []
        for _, node in scored_nodes[:top_k]:
            part = f"SECTION: {node['title']}\nSUMMARY: {node['summary']}\nCONTENT: {node['text'][:1000]}..."
            context_parts.append(part)
        
        return "\n\n".join(context_parts) if context_parts else "No relevant context found in the tree."

    def ask_question(self, question: str):
        """Asks the LLM to answer the question using retrieved context from the tree."""
        context = self.retrieve_context(question)
        
        system_prompt = f"""
        You are a Financial Risk Analyst. Use the provided context from a hierarchical document tree to answer the user's question accurately.
        If the answer is not in the context, state that you don't have enough information.
        
        CONTEXT FROM DOCUMENT TREE:
        ---
        {context}
        ---
        """

        try:
            response = litellm.completion(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error calling model: {str(e)}"

def interactive_session():
    # Path to our finalized RAG tree
    TREE_FILE = "Godrej_Final_RAG_Tree.json"
    
    try:
        checker = TreeReliabilityChecker(TREE_FILE)
    except Exception as e:
        print(f"Failed to start session: {e}")
        return

    print("Type your questions below to test the JSON Tree reliability.")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        query = input("QUESTION > ").strip()
        
        if query.lower() in ['exit', 'quit']:
            print("Ending reliability check session. Goodbye!")
            break
        
        if not query:
            continue

        print("\nThinking...")
        answer = checker.ask_question(query)
        print(f"\nANSWER:\n{answer}\n")
        print("-" * 50)

if __name__ == "__main__":
    interactive_session()
