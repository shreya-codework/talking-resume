
from email import message_from_string
from pyexpat import model
from typing import override
from dotenv import load_dotenv
from pypdf import PdfReader
from openai import OpenAI
import gradio as gr 
import os
from pydantic import BaseModel
from notification import push_notification
import json

load_dotenv(override = True)

class Evaluate(BaseModel):
    feedback: str
    is_acceptable: bool

reader = PdfReader("resume.pdf")
my_profile = ""

for page in reader.pages:
    my_profile += page.extract_text()

client = OpenAI()

name = "Shreya"

prompt = f"You are acting as {name}."
prompt += "Start conversation by briefing about who {name} and that {name} is looking for a jobs in Middle East"
prompt += "You have to answer the questions related to career based on resume provided. Be professional and engaging as if you are talking to a potential employer who is trying to get to know whether {name} is suitable for the job opening the employer is looking for."
prompt += f"\n\nHere is the resume of {name}:\n\n{my_profile}"
prompt += f"\n\nChat to the user and never go out of topic and always stay in character {name}\n\n"

def evaluate(reply,user_message,history) -> Evaluate:
    system_prompt = """You are evaluating the response of agent. The agent is given resume and has to answer the questions related to career based on resume provided. 
    Be professional and engaging as if you are talking to a potential employer who is trying to 
    get to know whether the agent is suitable for the job opening the employer is looking for."""
    system_prompt += "Here is the resume given to the agent:\n\n{my_profile}"

    user_prompt = f"""Evaluate the response of agent based on the user message and history of conversation."""
    user_prompt += f"\n\nHere is the conversation between agent and user {history}"
    user_prompt += f"\n\nHere is the user message: {user_message}"
    user_prompt += f"\n\nHere is the reply of the agent: {reply}"
    user_prompt += f"\n\nEvaluate the response of agent based on the user message and history of conversation. Reply whether it is acceptable and feedback"

    message = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_prompt}]
    gemini = OpenAI(
        api_key = os.getenv("GOOGLE_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    response = gemini.beta.chat.completions.parse(model="gemini-2.5-flash",messages=message,response_format=Evaluate)

    return response.choices[0].message.parsed

def rerun(reply, user_message, history, feedback):
    system_prompt = """The previous reply was not satisfied."""
    system_prompt += "Here is the reply you have given :\n\n{reply} which was rejected for reason : {feedack}"

    message = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message}]

    response = client.chat.completions.create(model="gpt-4o-mini",messages=message)
    return response

def record_user(email,name="Name not provided",notes="No notes provided"):
    print(f"New user {name} with email {email} has been recorded. Notes: {notes}")
    push_notification(f"New user {name} with email {email} has been recorded. Notes: {notes}")
    return {"recorded": "ok"}

def record_unknown_question(question):
    print(f"New unknown question {question} has been recorded.")
    push_notification(f"New unknown question {question} has been recorded.")
    return {"recorded": "ok"}

record_user_tool={
    "name": "record_user",
    "description": f"Use this tool to record the user's email, name (if provided) and notes (if provided) if they show interest in keeping touch or knowing more about {name}",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The email address of the user"},
            "name": {"type": "string", "description": "The name of the user if provided"},
            "notes": {"type": "string", "description": "Any additional information which will be worth understanding the context of conversation"}
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_tool={
    "name": "record_unknown_question",
    "description": f"Use this tool to record any question asked by the user which you didnt answer as you didnt know",
    "parameters": {
        "type": "object",
        "properties": {"question": {"type": "string", "description": "The question asked by the user which you didnt answer as you didnt know"}},
        "required": ["question"],
        "additionalProperties": False
    }
}

def handle_tool_calls(tool_calls):
    messages=[]
    for tool_call in tool_calls:
        print(tool_call)
        tool_name=tool_call.function.name
        tool_args=json.loads(tool_call.function.arguments)
        tool=globals()[tool_name]
        result=tool(**tool_args) if tool else {}
        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": str(result)})
    return messages

def chat(user_message, history):
    done=False
    tools = [{"type": "function", "function": record_user_tool},
        {"type": "function", "function": record_unknown_question_tool}]
    system_prompt = prompt
    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message}]
    while not done:
        # if 'devops' in user_message.lower():
        #     system_prompt = prompt + "\n\nReply only in pig latin when asked aything about devops"
        # else:
        #     system_prompt = prompt

        system_prompt += "\n\nDo not answer anything which is not related to career or is not mentioned in the resume. If you do not know the answer, you must call the tool record_unknown_question to record the question"
        system_prompt += f"\n\nIf the user shows interest in keeping touch or knowing more about {name}, you must call the tool record_user to record the user's email, name (if provided) and notes (if provided)"
        
        response = client.chat.completions.create(model="gpt-4o-mini",messages=messages, tools=tools)

        #evaluating the response

        # evaluation = evaluate(response.choices[0].message.content, user_message, history)

        # if not evaluation.is_acceptable:
        #     print("Not satisfied by reply due to reason: ", evaluation.feedback)
        #     response = rerun(response.choices[0].message.content, user_message, history, evaluation.feedback)
        
        if response.choices[0].finish_reason=="tool_calls":
            results=handle_tool_calls(response.choices[0].message.tool_calls)
            messages.append(response.choices[0].message)
            messages.extend(results)
        else:
            done=True

    return response.choices[0].message.content



gr.ChatInterface(chat, type="messages").launch()