from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv
from typing import Optional
import uuid

# Load environment variables
load_dotenv(override=True)


# Initialize OpenAI client
client = OpenAI()


# Load personality details
def load_personality():
    with open("me.txt", "r", encoding="utf-8") as f:
        return f.read().strip()


PERSONALITY = load_personality()

messages = [
    {"role": "system", "content": PERSONALITY},
    {"role": "user", "content": "Hi there"},
]

# Call OpenAI API
response = client.chat.completions.create(
    model="gpt-4o-mini", 
    messages=messages
)

print("OpenAI response:", response)
        