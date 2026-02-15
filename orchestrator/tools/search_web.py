import sys
import json
import requests
from dotenv import load_dotenv
import os

load_dotenv()

def search_web(objective: str) -> str:
    response = requests.post(
        "https://api.parallel.ai/v1beta/search",
        headers={
            "Content-Type": "application/json",
            "x-api-key": os.getenv("PARALLEL_API_KEY"),
            "parallel-beta": "search-extract-2025-10-10",

        },
        json={
            "objective": objective,
            "mode": "agentic",
            "max_results": 15, # here is where we change number of results
            "excerpts": {"max_chars_per_result": 1500}, # here is where we change chars per results
        },
    )
    response.raise_for_status()
    return response.json()

WEB_SEARCHES_DIR = "/root/code/web_searches"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tools/search_web.py <objective> <filename>")
        sys.exit(1)
    result = search_web(sys.argv[1])
    filepath = os.path.join(WEB_SEARCHES_DIR, sys.argv[2])
    with open(filepath, "w") as f:
        f.write(json.dumps(result, indent=2))
    print(f"Results written to {filepath}")
