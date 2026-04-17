import os
import litellm
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Setup credentials - using the correct NVIDIA_API_KEY as requested
api_key = os.getenv("NVIDIA_API_KEY")
api_base = "https://integrate.api.nvidia.com/v1"

print(f"Testing with API Base: {api_base}")
print(f"NVIDIA_API_KEY present: {bool(api_key)}")

# Testing Qwen 2.5 and Llama 3.1 variants to find the winning string
test_models = [
    "openai/qwen/qwen-2.5-72b-instruct",
    "nvidia_nim/qwen/qwen-2.5-72b-instruct",
    "openai/meta/llama-3.1-70b-instruct",
    "nvidia_nim/meta/llama-3.1-70b-instruct"
]

for model in test_models:
    print(f"\n--- Testing Model: {model} ---")
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "Say 'Test Successful'"}],
            api_base=api_base,
            api_key=api_key,
            temperature=0.1
        )
        print(f"SUCCESS: {response.choices[0].message.content}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {str(e)}")

print("\n--- Test Finished ---")
