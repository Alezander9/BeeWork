# Instructions

You are an autonomous agent. Do not ask follow-up questions. Figure things out yourself and complete the task.

## Environment

The knowledgebase repo is located at `knowledgebase/` in your working directory. All files you create should go inside `knowledgebase/`.

## Task

I want to create a knowledge base on everything related to the California renewable gas industry. Specifically I want you to look at all the major companies and impacts that relate to this industry. Create the file structure in the `knowledgebase/` repository, but do not populate any of the files with information yet. You can use the tools/search_web.py script to find information on the web about this topic.

## Tools

### search_web.py

Usage: `python tools/search_web.py "<objective>" <output_filename>`

**Important:** Always save output files to a path within the project directory (e.g., `knowledgebase/web_searches/research.json`). Do NOT use `/tmp/` or any other external directory — the sandbox will reject writes outside the project.