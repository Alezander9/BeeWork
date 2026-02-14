import sys
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
        json={"objective": objective},
    )
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search_web.py <objective>")
        sys.exit(1)
    result = search_web(sys.argv[1])
    print(result)
