I want to make a significant modification to how the pipeline runs. It should operate in two steps now.

Step 1: Run the orchestrator agent to generate the research tasks.

Step 2: It should create two queues, that both spawn seperate research and reviewer agents. You can set the size of each of the queues. The research queue, will spawn processses that start a research agent. When the research agent is done, it should move the task to the reviewer queue. The reviewer queue, will spawn processses that start a reviewer agent. It is imporatant that the same rules about not having multiple reviwer agents working on the same file should apply here, but it is ok for multiple research agents to work on the same file. The reviewer and research agents should both run at the same time. 

This is a complicated task that will likely requrire modifying the run_researcher_agent.py file. We want them to treat each task as basically an processes, where the research agents are populated into the review agents. 

Create a careful plan for how you will modify the files to achieve this. Make sure to ask clarifying questions, focusing on writing clear and concise code. Make sure to overhaul the current full_pipeline.py file to support this new functionality.