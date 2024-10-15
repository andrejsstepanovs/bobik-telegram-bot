import os
import re
import pycron
from datetime import datetime
import arrow


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

def get_entries_to_execute(config, user_timezone):
    now = datetime.now()
    if user_timezone is None:
        user_timezone = "local"
    atime = arrow.get(now)
    user_time = atime.to(user_timezone)

    entries_to_execute = []
    for category, entries in config.items():
        for entry in entries:
            if pycron.is_now(s=entry["schedule"], dt=user_time):
                entries_to_execute.append({
                    "prompt": entry["prompt"],
                    "schedule": entry["schedule_human"],
                    "topic": category,
                })
    return entries_to_execute
