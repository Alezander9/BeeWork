# Instructions

You are an autonomous agent. Do not ask follow-up questions. Figure things out yourself and complete the task.

## Environment

The knowledgebase repo is located at `knowledgebase/` in your working directory. All files you create should go inside `knowledgebase/`.

## Task

I want to create a knowledge base on everything related to the California renewable gas industry. Specifically I want you to look at all the major companies. This should be a brief overview of the companies and their role in the industry.

Follow these steps:

1. **Research**: Use `tools/search_web.py` to search for information about California renewable gas companies, industry players, regulations, and key topics. Perform multiple searches to get a comprehensive view.

2. **Create file structure**: Based on your research, create an organized file structure in `knowledgebase/` with markdown files for each company and topic. Do not populate the files with detailed content — just add a title and brief placeholder.

3. **Spawn research agents**: For **each file** in the knowledge base, spawn **3–5 separate research agents** using `tools/start_research_agent.py`. Each agent should target the **same file** but cover a **different subtopic** and use a **different website** as its source. Do NOT spawn only one agent per file — a single source produces shallow, one-sided content. For example, for a company file like `knowledgebase/companies/socalgas.md`, you would spawn separate agents like:
   - Agent 1 (company's own site): `--topic "SoCalGas overview" --websites "https://www.socalgas.com"`
   - Agent 2 (regulator): `--topic "SoCalGas regulatory filings" --websites "https://www.cpuc.ca.gov"`
   - Agent 3 (news): `--topic "SoCalGas RNG news" --websites "https://www.reuters.com"`

## Tools

### search_web.py

Usage: `python tools/search_web.py "<objective>" <filename>`

Searches the web and saves results to `web_searches/<filename>`. The output directory is managed automatically — just provide a filename (e.g., `research.json`). Read the saved file to extract information for the knowledgebase.

### start_research_agent.py

Usage: `python tools/start_research_agent.py --topic "<topic>" --prompt "<prompt>" --file-path "<path>" --websites "<url>"`

Starts a research agent to populate a specific file in the knowledge base.

- `--topic`: The topic for this agent (e.g., "SoCalGas renewable gas programs")
- `--prompt`: Detailed instructions for what information the agent should find and write
- `--file-path`: The path of the knowledge base file to edit (e.g., "knowledgebase/companies/socalgas.md")
- `--websites`: A relevant website to search for information (e.g., "https://www.socalgas.com")
