from youtube_transcript_api import YouTubeTranscriptApi,TranscriptsDisabled
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from typing import TypedDict,Annotated,Literal
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage,HumanMessage,SystemMessage
from langchain_postgres import PGVector
from langchain_core.documents import Document
from sqlalchemy import create_engine, Column, String, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import os

load_dotenv()
DB_URI = os.getenv('DB_URI')

model = ChatGroq(model="llama-3.1-8b-instant")

ytt_api = YouTubeTranscriptApi()

Base = declarative_base()

class VideoTranscript(Base):
    __tablename__ = "video_transcripts"
    video_id = Column(String, primary_key=True)
    transcript = Column(Text)
    is_indexed = Column(Boolean, default=False, nullable=False)


engine = create_engine(DB_URI)
SessionLocal = sessionmaker(bind=engine)

class ChatbotState(TypedDict):
    video_id: str
    transcript: str
    transcript_chunks: list[str]
    context:str
    question:str
    answer:str
    user_intent:Literal['QA','NotesGeneration']

class IntentClassificationSchema(BaseModel):
    user_intent:Literal['QA','NotesGeneration'] = Field(description='Identify the intent of user text from the query.')

strucured_model = model.with_structured_output(IntentClassificationSchema)

def get_transcript_from_db(video_id):
    session = SessionLocal()
    result = session.query(VideoTranscript).filter_by(video_id=video_id).first()
    session.close()
    return result.transcript if result else None

def generate_transcript(state: ChatbotState):
    video_id = state["video_id"]
    cached = get_transcript_from_db(video_id)
    if cached:
        return {"transcript": cached}
    transcript = ""
    try:
        fetched_transcript = ytt_api.fetch(video_id, languages=["en"])
        for snippet in fetched_transcript:
            transcript += snippet.text + " "
        save_transcript(video_id, transcript)
    except TranscriptsDisabled:
        return {"transcript": ""}
    return {"transcript": transcript}

def save_transcript(video_id, transcript):
    session = SessionLocal()
    existing = session.query(VideoTranscript).filter_by(video_id=video_id).first()
    if not existing:
        session.add(VideoTranscript(video_id=video_id, transcript=transcript))
        session.commit()
    session.close()
    
def identify_user_intent(state:ChatbotState):
    question=state['question']
    messages = [
        SystemMessage(content="You are a great intent evaluator. You are unbiased by opinions."),
        HumanMessage(content=f"""Evaluate this {question}. Identify what user wants from this question.
        ### Respond ONLY in structured format:
        - user_intent: 'QA' or 'NotesGeneration' only
        If the intent is none of the above then return QA""")]
    output = strucured_model.invoke(messages)
    return {'user_intent':output.user_intent}
def mark_indexed(video_id):
    session = SessionLocal()
    row = session.query(VideoTranscript).filter_by(video_id=video_id).first()
    if row:
        row.is_indexed = True
        session.commit()
    session.close()
def is_video_indexed(video_id):
    session = SessionLocal()
    row = session.query(VideoTranscript)\
        .filter_by(video_id=video_id)\
        .first()
    session.close()
    return row is not None and row.is_indexed

def conditional_video_indexing(state: ChatbotState):
    video_id = state['video_id']
    transcript = state['transcript']
    if is_video_indexed(video_id):return {}
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunks = text_splitter.create_documents([transcript])
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )

    docs = [
        Document(
            page_content=chunk.page_content,
            metadata={"video_id": video_id}
        )
        for chunk in chunks
    ]

    PGVector.from_documents(
        documents=docs,
        collection_name="youtube_content",
        embedding=embeddings,
        connection=DB_URI,
        use_jsonb=True,
    )
    print("=== INDEXING NODE ENTERED ===")
    print("VIDEO ID:", video_id)
    print("TRANSCRIPT LENGTH:", len(transcript))
    print("NUM CHUNKS:", len(chunks))
    mark_indexed(video_id)
    return {'transcript_chunks':chunks}


def generate_context(state:ChatbotState):
    
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )
    vector_store = PGVector(
        collection_name="youtube_content",
        embeddings=embeddings,
        connection=DB_URI,
    )   
    print("=== INDEXING COMPLETED ===")
    test = vector_store.similarity_search("test", k=1)
    print("POST-INDEX SEARCH RESULT:", len(test)) 
    retriever = vector_store.as_retriever(search_type="mmr",search_kwargs={'k':5,"filter": {"video_id": state["video_id"]}})
    retrieved_docs = retriever.invoke(state['question'])
    context = '\n\n'.join(doc.page_content for doc in retrieved_docs)
    print(context)
    return {'context':context}

def generate_notes(state:ChatbotState):
    prompt = f"""
    Create structured notes from:
    {state['context']}
    Include:
    - Headings
    - Bullet points
    - Key insights
    """
    notes = model.invoke(prompt).content
    return {'answer':notes}

def generate_answer(state:ChatbotState):
    context = state['context']
    question = state['question']
    prompt = PromptTemplate(template=f"You are a helpful assistant. Answer only from the provided transcript context.If the context is not enough just say don't know: {context}. Question:{question}",input_variables=['context','question'])
    query = prompt.invoke({"context":context,'question':question})
    response = model.invoke(query)
    answer = response.content
    return {'answer':answer}  

def router(state:ChatbotState):
    return state['user_intent']

def build_graph(checkpointer):
    graph = StateGraph(ChatbotState)
    graph.add_node('generate_transcript',generate_transcript)
    graph.add_node('generate_context',generate_context)
    graph.add_node('generate_answer',generate_answer)
    graph.add_node('generate_notes',generate_notes)
    graph.add_node('identify_user_intent',identify_user_intent)
    graph.add_node('conditional_video_indexing', conditional_video_indexing)
    
    graph.add_edge(START,'generate_transcript')
    graph.add_edge('generate_transcript','conditional_video_indexing')
    graph.add_edge('conditional_video_indexing','generate_context')
    graph.add_edge('generate_context','identify_user_intent')
    graph.add_conditional_edges('identify_user_intent',router,{
        'QA':'generate_answer',
        'NotesGeneration':'generate_notes'
    })
    graph.add_edge('generate_notes',END)
    graph.add_edge('generate_answer',END)
    chatbot = graph.compile(checkpointer=checkpointer)
    return chatbot