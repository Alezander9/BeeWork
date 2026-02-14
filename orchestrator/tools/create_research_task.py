import argparse
import json
import os
import re


RESEARCH_TASKS_DIR = "/root/code/research_tasks"


def sanitize_filename(topic):
    """Convert a topic string into a safe filename."""
    name = topic.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = name.strip("-")
    return name or "unnamed"


def main():
    parser = argparse.ArgumentParser(
        description="Create a research task to populate a knowledge base file."
    )
    parser.add_argument("--topic", required=True, help="The topic of the research agent")
    parser.add_argument("--prompt", required=True, help="The prompt for the research agent")
    parser.add_argument("--file-path", required=True, help="The path of the file in the knowledge base to edit")
    parser.add_argument("--websites", required=True, help="A website to search for information")
    args = parser.parse_args()

    os.makedirs(RESEARCH_TASKS_DIR, exist_ok=True)

    task = {
        "topic": args.topic,
        "prompt": args.prompt,
        "file_path": args.file_path,
        "websites": args.websites,
    }

    filename = sanitize_filename(args.topic) + ".json"
    filepath = os.path.join(RESEARCH_TASKS_DIR, filename)

    # If a file with the same name already exists, add a numeric suffix
    if os.path.exists(filepath):
        base = sanitize_filename(args.topic)
        i = 2
        while os.path.exists(os.path.join(RESEARCH_TASKS_DIR, f"{base}-{i}.json")):
            i += 1
        filepath = os.path.join(RESEARCH_TASKS_DIR, f"{base}-{i}.json")

    with open(filepath, "w") as f:
        json.dump(task, f, indent=2)

    print(f"Research task saved to {filepath}")
    print(f"  Topic:    {args.topic}")
    print(f"  Prompt:   {args.prompt}")
    print(f"  File:     {args.file_path}")
    print(f"  Websites: {args.websites}")


if __name__ == "__main__":
    main()
