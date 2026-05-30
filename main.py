from fastapi import FastAPI
from chatbot import build_graph
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import ConnectionPool
from pydantic import BaseModel
from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres import PostgresSaver


load_dotenv()
DB_URI = os.getenv('DB_URI')
chatbot = None
checkpointer = None
pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global chatbot, checkpointer, pool
    pool = ConnectionPool(
        conninfo=DB_URI,
        min_size=1,
        max_size=10
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    chatbot = build_graph(checkpointer)
    print("App started successfully")
    yield
    pool.close()
    print("App shutdown")

app = FastAPI(lifespan=lifespan)

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

@app.post("/chat")
def chat(request: ChatRequest):
    thread_id = f"{request.user_id}:{request.video_id}"
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

@app.get("/history")
def history(video_id: str, user_id: str):
    thread_id = f"{user_id}:{video_id}"
    state = chatbot.get_state(config={"configurable": {"thread_id": thread_id}})
    history = state.values.get("history", [])
    return {"history": history[-5:]}