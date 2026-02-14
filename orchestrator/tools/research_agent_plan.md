start_research_agent.py is a script that the orchestrator will use to fill in specific details for a file in the knowledge base. A research agent will have the following arguments:

- topic: The topic of the research agent
- prompt: The prompt for the research agent
- file_path: The path of the file in the knowledge base to edit
- websites: A website to search for information

For every file, we should have multiple research agents assigned to work on it. Different research agents can search for different information and fill in different parts of the file. The orchestrator should use its research from web searches to create tasks for each agent. For now, the start_research_agent.py script will simply print out its arguments, but in the future it will actually run code. 

Additionally, modify the prompt in AGENTS.MD to align with the new objective. 

Create a plan and ask any clarifying questions, writing clean and concise code. 
