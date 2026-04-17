import asyncio
import os
import json
import logging
import sys
import time
import threading
import random
from dotenv import load_dotenv
import litellm

# 1. Load environment variables
load_dotenv()

# 2. Configure litellm globally for NVIDIA NIM
litellm.api_base = "https://integrate.api.nvidia.com/v1"
litellm.api_key = os.getenv("NVIDIA_API_KEY")

# --- Rate Limiter Implementation ---
class RateLimiter:
    """
    Simple Thread-Safe Thread-Blocking Rate Limiter.
    Ensures at least (60/RPM) seconds between requests.
    """
    def __init__(self, rpm: int):
        self.interval = 60.0 / rpm
        self.last_call = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_call
            if elapsed < self.interval:
                sleep_time = self.interval - elapsed
                # Add a tiny bit of jitter to avoid "thundering herd" if many threads wait
                time.sleep(sleep_time + random.uniform(0.05, 0.2))
            self.last_call = time.time()

# Initialize global rate limiter (35 RPM for NVIDIA NIM)
global_rate_limiter = RateLimiter(rpm=35)

# Patch litellm.completion globally to include rate limiting
# This ensures PageIndex's internal calls are gated without changing its source code.
original_litellm_completion = litellm.completion

def rate_limited_completion(*args, **kwargs):
    global_rate_limiter.wait()
    return original_litellm_completion(*args, **kwargs)

litellm.completion = rate_limited_completion

# 3. Add PageIndex to path for imports
sys.path.append(os.path.join(os.getcwd(), 'PageIndex'))

from PageIndex.page_index_md import md_to_tree
from PageIndex.utils import ConfigLoader

# 4. Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler("pageindex_nim.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PageIndex-NIM-Runner")

async def run_forensic_indexing():
    INPUT_MD = "Tata_Motors_Forensic_Report.md"
    OUTPUT_JSON = "Tata_Motors_PageIndex_Tree.json"
    
    # Using Llama 3.1 70B via standard OpenAI routing (most stable for NIM)
    MODEL = "openai/meta/llama-3.1-70b-instruct"
    
    if not os.path.exists(INPUT_MD):
        logger.error(f"Input file not found: {INPUT_MD}")
        return

    logger.info(f"Starting Rate-Limited PageIndex construction using model: {MODEL}")
    
    try:
        # We use the native md_to_tree which handles the # hierarchy
        result = await md_to_tree(
            md_path=INPUT_MD,
            if_thinning=False, 
            min_token_threshold=5000,
            if_add_node_summary='yes',
            summary_token_threshold=200,
            model=MODEL,
            if_add_doc_description='yes',
            if_add_node_text='yes', 
            if_add_node_id='yes'
        )

        # Save to the results folder
        output_dir = './results'
        os.makedirs(output_dir, exist_ok=True)
        final_output = os.path.join(output_dir, OUTPUT_JSON)

        with open(final_output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        
        logger.info(f"PIPELINE SUCCESS: PageIndex tree saved to {final_output}")
        print(f"\n--- SUCCESS: PageIndex tree generated at {final_output} ---")

    except Exception as e:
        logger.error(f"PIPELINE CRASH: {str(e)}", exc_info=True)
        print(f"\n--- ERROR: PageIndex generation failed: {e} ---")

if __name__ == "__main__":
    asyncio.run(run_forensic_indexing())
