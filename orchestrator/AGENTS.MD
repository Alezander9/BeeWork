# Instructions

You are an autonomous agent. Do not ask follow-up questions. Figure things out yourself and complete the task.

## Environment

The knowledgebase repo is located at `knowledgebase/` in your working directory. All files you create should go inside `knowledgebase/`.

## Task

Your project requirements are defined in `PROJECT.MD`. Read it first -- it is your primary directive. Everything you do should follow the objectives, structure, and scope described there.

Follow these steps:

1. **Read `PROJECT.MD`** to understand what the knowledge base should contain.

2. **Research**: Use `tools/search_web.py` to search for information relevant to the project. Perform multiple searches to get a comprehensive view of the space.

3. **Create file structure**: Based on your research, create an organized file structure in `knowledgebase/` with markdown files. USe the file structure as described in `PROJECT.MD` as a rough blueprint, but don't be afraid to deviate from it if you find something interesting. Do not populate the files with detailed content -- just add a title and brief placeholder. Every folder should have a OVERVIEW.md file, which should be a summary of the folder's contents. Again, don't populate the OVERVIEW.md files with detailed content -- just add a title and brief placeholder.

4. **Create research tasks**: For each file in the knowledge base, create research tasks using `tools/create_research_task.py`. 

Create research tasks: For each file in the knowledge base, create 2–10 separate research tasks. Each task should target the same file but cover a different subtopic and use a different website as its source. Do NOT create only one task per file — a single source produces shallow, one-sided content. For example, for a company file like knowledgebase/companies/socalgas.md, you would spawn separate agents that target the same file but use different websites as their source, or try to find different information on the same website:

- Agent 1 (company's own site): --topic "SoCalGas overview" --websites "https://www.socalgas.com"
- Agent 2 (regulator): --topic "SoCalGas regulatory filings" --websites "https://www.cpuc.ca.gov"
- Agent 3 (news): --topic "SoCalGas RNG news" --websites "https://www.reuters.com"

Follow the scope constraints in `PROJECT.MD` for how many tasks to create.

## Tools

### search_web.py

Usage: `python tools/search_web.py "<objective>" <filename>`

Searches the web and saves results to `web_searches/<filename>`. The output directory is managed automatically -- just provide a filename (e.g., `research.json`). Read the saved file to extract information.

### create_research_task.py

Usage: `python tools/create_research_task.py --topic "<topic>" --prompt "<prompt>" --file-path "<path>" --websites "<url>"`

Creates a research task to populate a specific file in the knowledge base.

- `--topic`: The topic for this research task
- `--prompt`: Detailed instructions for what information the agent should find and write
- `--file-path`: The path of the knowledge base file to edit (e.g., "knowledgebase/companies/example.md")
- `--websites`: A relevant website to search for information (e.g., "https://example.com")
