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
            "mode": "agentic"
        },
    )
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python search_web.py <objective> <output_filename>")
        sys.exit(1)
    result = search_web(sys.argv[1])
    filename = sys.argv[2]
    with open(filename, "w") as f:
        f.write(json.dumps(result, indent=2))
    print(f"Results written to {filename}")
