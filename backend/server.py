import datetime
import json
import logging
import os
import traceback
import uuid

import boto3
from botocore.exceptions import ClientError
from deepagents import create_deep_agent
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel

from context import prompt

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Bedrock configuration - see Q42 on https://edwarddonner.com/faq if the Region gives you problems
AWS_REGION = os.getenv("DEFAULT_AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.amazon.nova-2-lite-v1:0")

# LangChain chat model backed by AWS Bedrock. Created once at import time and
# reused across requests (the deep agent is rebuilt per request so the system
# prompt's datetime stays fresh).
bedrock_model = ChatBedrockConverse(
    model_id=BEDROCK_MODEL_ID,
    region_name=AWS_REGION,
    max_tokens=2000,
    temperature=0.9,
    top_p=0.9,
)

# Memory storage configuration
USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET", "")
MEMORY_DIR = os.getenv("MEMORY_DIR", "../memory")

# Initialize S3 client if needed
if USE_S3:
    s3_client = boto3.client("s3")


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


class Message(BaseModel):
    role: str
    content: str
    timestamp: str


# Memory management functions
def get_memory_path(session_id: str) -> str:
    return f"{session_id}.json"


def load_conversation(session_id: str) -> list[dict]:
    """Load conversation history from storage"""
    if USE_S3:
        try:
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=get_memory_path(session_id))
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return []
            raise
    else:
        # Local file storage
        file_path = os.path.join(MEMORY_DIR, get_memory_path(session_id))
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return []


def save_conversation(session_id: str, messages: list[dict]):
    """Save conversation history to storage"""
    if USE_S3:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=get_memory_path(session_id),
            Body=json.dumps(messages, indent=2),
            ContentType="application/json",
        )
    else:
        # Local file storage
        os.makedirs(MEMORY_DIR, exist_ok=True)
        file_path = os.path.join(MEMORY_DIR, get_memory_path(session_id))
        with open(file_path, "w") as f:
            json.dump(messages, f, indent=2)


def _extract_text(content) -> str:
    """Normalize a LangChain message's content to plain text.

    Bedrock (via ChatBedrockConverse) may return either a plain string or a
    list of content blocks; flatten either into a single string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "".join(parts)
    return str(content)


async def call_bedrock(conversation: list[dict], user_message: str) -> str:
    """Run the LangChain deep agent (backed by AWS Bedrock) with history."""

    # Build the deep agent per request so the system prompt's datetime is fresh.
    agent = create_deep_agent(model=bedrock_model, system_prompt=prompt())

    # Convert stored history into LangChain-style messages, dropping metadata
    # such as timestamps and keeping only the last 50 turns.
    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation[-50:]
    ]
    messages.append({"role": "user", "content": user_message})

    try:
        result = await agent.ainvoke({"messages": messages})
        return _extract_text(result["messages"][-1].content)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ValidationException":
            print(f"Bedrock validation error: {e}")
            raise HTTPException(status_code=400, detail="Invalid message format for Bedrock")
        elif error_code == "AccessDeniedException":
            print(f"Bedrock access denied: {e}")
            raise HTTPException(status_code=403, detail="Access denied to Bedrock model")
        else:
            print(f"Bedrock error: {e}")
            raise HTTPException(status_code=500, detail=f"Bedrock error: {e!s}")


@app.get("/")
async def root():
    return {
        "message": "AI Digital Twin API (LangChain Deep Agents on AWS Bedrock)",
        "memory_enabled": True,
        "storage": "S3" if USE_S3 else "local",
        "ai_model": BEDROCK_MODEL_ID
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "use_s3": USE_S3,
        "bedrock_model": BEDROCK_MODEL_ID
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        # Load conversation history
        conversation = load_conversation(session_id)

        # Call the Bedrock-backed deep agent for a response
        assistant_response = await call_bedrock(conversation, request.message)

        # Update conversation history
        conversation.append(
            {"role": "user", "content": request.message, "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat()}
        )
        conversation.append(
            {
                "role": "assistant",
                "content": assistant_response,
                "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            }
        )

        # Save conversation
        save_conversation(session_id, conversation)

        return ChatResponse(response=assistant_response, session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in chat endpoint")
        logger.error("\n--- Full Exception Traceback (Detailed) ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    """Retrieve conversation history"""
    try:
        conversation = load_conversation(session_id)
        return {"session_id": session_id, "messages": conversation}
    except Exception as e:
        logger.exception("Error in chat endpoint")
        logger.error("\n--- Full Exception Traceback (Detailed) ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)