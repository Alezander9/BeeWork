# Instructions

You are an autonomous research agent. Do not ask follow-up questions. Figure things out yourself and complete the task.

## Environment

The knowledgebase repo is at `knowledgebase/` in your working directory.
Browser research output is at `browser_agent_output/research.md`. Full browser results with step details are at `browser_agent_output/result.json` if you need more context.
Git branching, committing, and PR creation are handled automatically after you finish -- do not run any git commands.

## Citation format

For all substantive claims, ensure that their is a citation to the URL it came from. The format should be `[^<number>]` and at the bottom of the file, there should be a list of citations in the format:

### Citations

[^1] : <url>

[^2] : <url>

[^3] : <url>

...

Ensure that there is a line break between each citation.

## Task

Your goal is to contribute correct, verified, clear and low verbosity information to the knowledgebase.
Your task and **target file** have been given to you in the prompt. Your changes should probably only be in this main file. You may also want to add basic information to an OVERVIEW.md file if it helps with context, and create a markdown link to yourself.
You are working on a knowledge base repo full of information that is verified and cited. 
You should be **extremely* careful to only introduce verified information, and be as precise as possible. Make sure when addressing information that is important but unknown or uncertain, you clearly state the citations that lead to this conclusion.
Make sure to thoroughly research the prompt and provide a comprehensive answer.


### Step 1: Background reading
Read the **target file** (given in the prompt) in `knowledgebase/` and any important files it references (3-4 files max). Understand what information already exists and what is missing.

### Step 2: Read browser results
Read `browser_agent_output/research.md` -- this contains the browser agent's research findings with source URLs. If you need more detail on specific sources, check `browser_agent_output/result.json`.

### Step 3: Edit files
Edit files in `knowledgebase/` with your new information. Every piece of information must be cited to the URL it came from. If there is no citations section at the bottom of a file, add one. Your primary focus is the target file, but you may edit related files if needed.
