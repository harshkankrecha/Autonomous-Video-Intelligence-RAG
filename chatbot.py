from youtube_transcript_api import YouTubeTranscriptApi,TranscriptsDisabled
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from typing import TypedDict,Annotated,Literal
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage,HumanMessage,SystemMessage

load_dotenv()

model = ChatGroq(model="llama-3.1-8b-instant")

ytt_api = YouTubeTranscriptApi()

#need to overwork
video_id = 'Gfr50f6ZBvo'
question = 'is the topic of nuclear fusion discussed in this video? if yes then what was discussed?'

initial_state = {'video_id':video_id,'question':question}

class ChatbotState(TypedDict):
    video_id: str
    transcript: str
    transcript_chunks: list[str]
    context:str
    question:str
    answer:str
    user_intent:Literal['QA','Summarization','TimestampFinder','NotesGeneration']

class IntentClassificationSchema(BaseModel):
    user_intent:Literal['QA','Summarization','TimestampFinder','NotesGeneration'] = Field(description='Identify the intent of user from the query.')

strucured_model = model.with_structured_output(IntentClassificationSchema)

def generate_transcript(state:ChatbotState):
    transcript = ''
    try:
        fetched_transcript = ytt_api.fetch(video_id,languages=['en'])
        for snippet in fetched_transcript:
            transcript+=''.join(snippet.text)
        #print(transcript)
    except TranscriptsDisabled:
        print("No caption present in the video")
    return {'transcript':transcript}

def identify_user_intent(state:ChatbotState):
    question=state['question']
    prompt = strucured_model
    output = strucured_model.invoke(prompt)
    return {'user_intent':output.user_intent}

def generate_transcript_chunk(state:ChatbotState):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.create_documents([state['transcript']])
    return {'transcript_chunks':chunks}

def generate_context(state:ChatbotState):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
    vector_store = Chroma.from_documents(documents=state['transcript_chunks'],collection_name="transcript_embeddings",embedding=embeddings,)
    retriever = vector_store.as_retriever(search_type="similarity",search_kwargs={'k':4})
    retrieved_docs = retriever.invoke(state['question'])
    context = '\n\n'.join(doc.page_content for doc in retrieved_docs)
    return {'context':context}

def generate_response(state:ChatbotState):
    context = state['context']
    question = state['question']
    prompt = PromptTemplate(template=f"You are a helpful assistant. Answer only from the provided transcript context.If the context is not enough just say don't know: {context}. Question:{question}",input_variables=['context','question'])
    query = prompt.invoke({"context":context,'question':question})
    #print(context)
    response = model.invoke(query)
    #print(final_prompt)
    answer = response.content
    return {'answer':answer}  

graph = StateGraph(ChatbotState)

graph.add_node('generate_transcript',generate_transcript)
graph.add_node('generate_transcript_chunk',generate_transcript_chunk)
graph.add_node('generate_context',generate_context)
graph.add_node('generate_response',generate_response)

graph.add_edge(START,'generate_transcript')
graph.add_edge('generate_transcript','generate_transcript_chunk')
graph.add_edge('generate_transcript_chunk','generate_context')
graph.add_edge('generate_context','generate_response')
graph.add_edge('generate_response',END)

chatbot = graph.compile()

final_state = chatbot.invoke(initial_state)

print(final_state['answer'])