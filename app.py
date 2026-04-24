from fastapi import FastAPI
from chatbot import build_graph
from langgraph.checkpoint.postgres import PostgresSaver
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

DB_URI = os.getenv('DB_URI')
checkpointer = PostgresSaver.from_conn_string(DB_URI)

checkpointer.setup()
chatbot = build_graph(checkpointer)

@app.post("/chat")
def chat(user_id: str, question: str, video_id: str):
    thread_id = f"user:{user_id}"
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    result = chatbot.invoke(
        {'question':question,'video_id':video_id},
        config=config
    )
    return result['answer']