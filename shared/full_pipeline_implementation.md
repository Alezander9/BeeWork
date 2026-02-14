Implement full_pipeline.py The full pipeline is in charge of running each stage of our project.

Orchestrator is in charge of basic research and create the first draft of the knowledgebase. It also returns the research tasks to use.

Next it runs all the research tasks in parallel using run_research_agent.py. Each research task is run in a separate modal sandbox.

It is important that the pipeline is flexible enough such that we dont have to rerun the whole process, and if one part fails, we have already saved the outputs of previous stages. Additionally, it should be designed to be flexible to adding new stages to the pipeline.

Create a thorough plan, and ask clarifying questions before starting implementation. Make sure to write clean and clear code.
