The search_web.py script is a tool that uses the parallel api to get web information about some specific topic. This tool is used by the orchestrator to get web information about some specific topic. You should use the Parrallel api, through the requests library in python. Below is the curl format.

"""
curl --request POST \
    --url https://api.parallel.ai/v1beta/search \
    --header 'Content-Type: application/json' \
    --header 'x-api-key: <api-key>' \
    --header 'parallel-beta: search-extract-2025-10-10' \
    --data '{
    "objective": "What was the GDP of France in 2023?"
}'
"""

The api key should be loaded used load_dotenv() function from the dotenv library. The api key is stored in the .env file as PARALLEL_API_KEY. Create a plan, focusing on concise and clean code. The search_web.py should be a script that can be ran with the objective as a command line argument, and should print the output to the console.