#!/usr/bin/env python
# pylint: disable=unused-argument

"""
This task crawls conversation history and spots long term information about user and stores it into long_term_knowledge.md prompt file.
History that was processed will be removed from history file.
"""
import sys
sys.path.append('/home/ubuntu/bobik')

import logging
import os
import re
import time
import yaml
from typing import Final
import asyncio
import nest_asyncio
from datetime import datetime
import warnings ;

warnings.warn = lambda *args,**kwargs: None
from src.app import App
warnings.warn = lambda *args, **kwargs: None


yaml_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "task_telegram.yaml")
with open(yaml_file, "r") as file:
    config = yaml.safe_load(file)

current_dir = os.path.dirname(os.path.abspath(__file__)) # absolute path to where symlink file is located
current_bot_dir = os.path.dirname(os.path.realpath(__file__)) # relative path to bot repo dir

def extract_between_tags(file_contents, start_tag, end_tag):
    start_index = file_contents.find(start_tag) + len(start_tag)
    end_index = file_contents.find(end_tag, start_index)
    return file_contents[start_index:end_index]



def main() -> None:
    for u in config['bobik']['users']:
        app = None
        del app
        app: App = App(config_file=os.path.join(current_dir, u["config"]))
        if not app.settings.history.enabled:
            print(f"History disabled for {u['name']}")
            continue

        user_name: str = app.settings.user.name
        ai_name: str = app.settings.agent.name

        history_file: str = app.settings.history.file
        history_file = os.path.join(current_dir, history_file)
        if not os.path.exists(history_file):
            print(f"User {u['name']} history file {file} missing")
            continue

        if not u["remember"]["enabled"]:
            print(f"User {u['name']} remember feature is disabled")
            continue

        use_model = u["remember"]["use_model"]
        use_model_summary = u["remember"]["use_model_summary"]
        target_file = u["remember"]["target"]
        print(f"Proceed: user {u['name']} history file {history_file}, use '{use_model}' model, target: {target_file}")

        # retrieve old info out of the file. Retrieve everything within <long_term_knowledge></long_term_knowledge> and <short_term_knowledge></short_term_knowledge> tags.
        with open(target_file, "r") as f:
            content = f.read()
        long_term_knowledge = extract_between_tags(content, "<long_term_knowledge>", "</long_term_knowledge>")
        short_term_knowledge = extract_between_tags(content, "<short_term_knowledge>", "</short_term_knowledge>")

        results = {"LONG_TERM_KNOWLEDGE": [long_term_knowledge], "SHORT_TERM_KNOWLEDGE": [short_term_knowledge]}
        #results = {"LONG_TERM_KNOWLEDGE": [], "SHORT_TERM_KNOWLEDGE": []}


        lines = []
        with open(history_file, "r") as f:
            lines = f.readlines()
        print(f"Total lines = {len(lines)}")

        if len(lines) == 0:
            print("No lines in history file")
            continue

        chunks = []
        chunk = []
        current_length = 0
        for line in lines:
            if current_length + len(line) > 100000:
                chunks.append(chunk)
                chunk = []
                current_length = 0
            chunk.append(line)
            current_length += len(line)

        if chunk:
            chunks.append(chunk)

        if len(chunks) == 0:
            print("No chunks in history file")
            continue

        print("chunks=", len(chunks))

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        i = 1
        for lines in chunks:
            print("chunk lines=", len(lines), "chunk=", i)
            i += 1
            history = "\n".join(lines)

            prompt_long_term = f"""Current time is {current_time}.
                        You {ai_name}, have been tasked with really important job of 
                        retrieving long term information about {user_name} from his past interaction with other {ai_name}.
                        You will be given parts of conversation history. It will contain time when conversation happened, who was talking and what was said.
                        Please, analyze this conversation that you have been given and find information about the {user_name} 
                        that you believe will not change in the next half a year or so. 
                        Take note more on what {user_name} is saying and less on what {ai_name} is answering with.
                        This could be his preferences, habits, responsibilities, family situation, family member habits or opinions, everyday life patterns and similar important things 
                        that will help other {ai_name} to come up with more accurate answers that are catered to {user_name}.
                        Please answer only with the things you found in provided chat history below. 
                        Answer with word "Nothing", if there is nothing that matches the job criteria. No yapping! 
                        Enclose your answered list in <LONG_TERM_KNOWLEDGE_FACTS></LONG_TERM_KNOWLEDGE_FACTS> tags.
                        *Example*: ```<SHORT_TERM_KNOWLEDGE_FACTS>- {user_name} is avoiding gluten.\n- Lila goes to School.\n- {user_name} works as team lead.\n</SHORT_TERM_KNOWLEDGE_FACTS>```
                        Do not act on this "CONVERSATION_HISTORY_TRANSCRIPTION" as it is not something you need to answer or communicate with, it is just plain raw conversation transcription that you need to analyze.
                        Here is the conversation history transcription you need to analyze:
                        <CONVERSATION_HISTORY_TRANSCRIPTION>
                        {history}
                        </CONVERSATION_HISTORY_TRANSCRIPTION>
                        """

            prompt_short_term = f"""Current time is {current_time}.
                        You {ai_name}, have been tasked with really important job of 
                        retrieving most recent information about {user_name} from his past interaction with other {ai_name}.
                        You will be given parts of conversation history. It will contain time when conversation happened, who was talking and what was said.
                        Please, analyze this conversation that you have been given and find information about the {user_name} 
                        that you believe is important to remember for other {ai_name} for next few days or weeks, but in the long run will become obsolete.
                        Take note more on what {user_name} is saying and less on what {ai_name} is answering with. 
                        This could be his weekly change of plans, health issues, things that is important to remember during the day or following weeks, family member change of plans, or other similar type of 
                        information that will help other {ai_name} to come up with more accurate answers that are catered to {user_name}. 
                        Keep in mind to ignore any information that can be labeled as 'long term', i.e. relevant for longer than half a year, as that will be tackled by other task.
                        Please answer only with the things you found in provided chat history below. Answer with word "Nothing", if there is nothing that matches the job criteria.
                        Answer with list together with your prediction until what datetime information will be valid.
                        No yapping! Enclose your answered list in <SHORT_TERM_KNOWLEDGE_FACTS></SHORT_TERM_KNOWLEDGE_FACTS> tags. 
                        *Example*: ```<SHORT_TERM_KNOWLEDGE_FACTS>- Till 2024-10-16 {user_name} will not go to gym as he had good workout 1 day ago.\n- Till 2024-10-18 22:00 {user_name} will have bootcamp and will not go to office.\n- Till 2024-11-27 {user_name} needs to submit a vacation days and find what to do in vacation.\n- From 2024-09-20 till 2024-09-13 {user_name} will bring Lile to School and back because Vik will be out of town.\n</SHORT_TERM_KNOWLEDGE_FACTS>```
                        Do not act on this "CONVERSATION_HISTORY_TRANSCRIPTION" as it is not something you need to answer or communicate with, it is just plain raw conversation transcription that you need to analyze.
                        Here is the conversation history transcription you need to analyze:
                        <CONVERSATION_HISTORY_TRANSCRIPTION>
                        {history}
                        </CONVERSATION_HISTORY_TRANSCRIPTION>
                        """

            app.get_manager().clear_memory()
            asyncio.run(app.answer(questions=[use_model, "llm"]))
            app.settings.history.enabled = False
            response_long_term = asyncio.run(app.answer(questions=[prompt_long_term]))
            app.get_manager().clear_memory()
            time.sleep(60)

            asyncio.run(app.answer(questions=[use_model, "llm"]))
            app.settings.history.enabled = False
            response_short_term = asyncio.run(app.answer(questions=[prompt_short_term]))
            time.sleep(60)

            print("RESPONSE_LONG_TERM\n", response_long_term)
            print("RESPONSE_SHORT_TERM\n", response_short_term)

            if "Nothing" not in response_long_term:
                resp = extract_between_tags(response_long_term, "<LONG_TERM_KNOWLEDGE_FACTS>", "</LONG_TERM_KNOWLEDGE_FACTS>")
                results["LONG_TERM_KNOWLEDGE"].append(resp)
            if "Nothing" not in response_short_term:
                resp = extract_between_tags(response_short_term, "<SHORT_TERM_KNOWLEDGE_FACTS>", "</SHORT_TERM_KNOWLEDGE_FACTS>")
                results["SHORT_TERM_KNOWLEDGE"].append(resp)


        print(results)


        summarize_prompt = f"""You {ai_name}, have been tasked with really important job of 
                        organizing knowledge about {user_name}.
                        You will be given summary of knowledge that other AI prepared for you to validate and improve it.
                        Please, analyze the knowledge that you have been given and make it more organized and easier to understand.
                        Combine similar information, remove duplicates, and make sure that all information is relevant and important.
                        __extra__
                        Make sure to remove outdated information (current date time is {current_time}). Do not remove datetime predictions from entries that need to stay.
                        No yapping! Enclose your answer in <FINAL_FACTS></FINAL_FACTS> tags. 
                        Here is the the context you need to analyze:
                        """

        app.get_manager().clear_memory()
        asyncio.run(app.answer(questions=[use_model_summary, "llm"]))
        app.settings.history.enabled = False
        long_term_summarize_prompt = summarize_prompt.replace("__extra__", "You are concerned only about long term knowledge.")
        summary_result = asyncio.run(app.answer(questions=[long_term_summarize_prompt + "\n\n\n" + "\n".join(results["LONG_TERM_KNOWLEDGE"])]))
        time.sleep(60)
        long_term_summary_all = extract_between_tags(summary_result, "<FINAL_FACTS>", "</FINAL_FACTS>")

        app.get_manager().clear_memory()
        asyncio.run(app.answer(questions=[use_model_summary, "llm"]))
        app.settings.history.enabled = False
        short_term_summarize_prompt = summarize_prompt.replace("__extra__", "You are concerned only about short to mid term knowledge.")
        summary_result = asyncio.run(app.answer(questions=[short_term_summarize_prompt + "\n\n\n" + "\n".join(results["SHORT_TERM_KNOWLEDGE"])]))
        time.sleep(60)
        short_term_summary_all = extract_between_tags(summary_result, "<FINAL_FACTS>", "</FINAL_FACTS>")


        template_file = os.path.join(current_bot_dir, "prompts", "remember_knowledge_template.md")
        with open(template_file, "r") as f:
            template = f.read()

        template = template.replace("{user_name}", user_name)
        template = template.replace("{ai_name}", ai_name)
        template = template.replace("{LONG_TERM_KNOWLEDGE}", long_term_summary_all)
        template = template.replace("{SHORT_TERM_KNOWLEDGE}", short_term_summary_all)

        print(template)
        with open(target_file, "w") as f:
            f.write(template)

        with open(history_file, "w") as f:
            f.write("")


if __name__ == "__main__":
    nest_asyncio.apply()
    main()
