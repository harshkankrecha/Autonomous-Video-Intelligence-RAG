from fastapi import FastAPI
from chatbot import build_graph
from langgraph.checkpoint.postgres import PostgresSaver
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel


load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_id: str
    question: str
    video_id: str

checkpointer = InMemorySaver()
chatbot = build_graph(checkpointer)

@app.post("/chat")
def chat(request: ChatRequest):
    thread_id = f"user:{request.user_id}"
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    result = chatbot.invoke(
        {'question':request.question,'video_id':request.video_id},
        config=config
    )
    return result['answer']