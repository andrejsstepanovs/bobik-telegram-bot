import os
import re

def extract_and_split(text, start_tag="<formatted_text>", end_tag="</formatted_text>", delimiter="----"):
    # Use regex for more robust tag matching
    pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    sections = re.findall(pattern, text, re.DOTALL)

    # Use list comprehension for splitting and flattening in one step
    split_sections = [
        subsection.strip()
        for section in sections
        for subsection in section.split(delimiter)
        if subsection.strip()
    ]

    return split_sections

def format_response_prompt(replacement_text: str, current_dir: str) -> str:
    file = os.path.join(current_dir, "prompts", "telegram_markdown.md")
    if not os.path.exists(file):
        return f"Error: File {file} not found"

    with open(file, "r") as f:
        content: str = f.read()
        question = content.replace("{{TEXT_TO_FORMAT}}", replacement_text)
        return question
