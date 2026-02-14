import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Start a research agent to populate a knowledge base file."
    )
    parser.add_argument("--topic", required=True, help="The topic of the research agent")
    parser.add_argument("--prompt", required=True, help="The prompt for the research agent")
    parser.add_argument("--file-path", required=True, help="The path of the file in the knowledge base to edit")
    parser.add_argument("--websites", required=True, help="A website to search for information")
    args = parser.parse_args()

    print(f"Starting research agent...")
    print(f"  Topic:    {args.topic}")
    print(f"  Prompt:   {args.prompt}")
    print(f"  File:     {args.file_path}")
    print(f"  Websites: {args.websites}")


if __name__ == "__main__":
    main()
