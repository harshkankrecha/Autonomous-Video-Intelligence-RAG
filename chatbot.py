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
from langgraph.checkpoint.postgres import PostgresSaver


load_dotenv()

model = ChatGroq(model="llama-3.1-8b-instant")

ytt_api = YouTubeTranscriptApi()

#need to overwork
video_id = 'Gfr50f6ZBvo'
#question = 'is the topic of nuclear fusion discussed in this video? if yes then what was discussed?'
question='generate notes of this video'
initial_state = {'video_id':video_id,'question':question}



class ChatbotState(TypedDict):
    video_id: str
    transcript: str
    transcript_chunks: list[str]
    context:str
    question:str
    answer:str
    user_intent:Literal['QA','TimestampFinder','NotesGeneration']

class IntentClassificationSchema(BaseModel):
    user_intent:Literal['QA','TimestampFinder','NotesGeneration'] = Field(description='Identify the intent of user from the query.')

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

def generate_transcript_chunk(state:ChatbotState):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.create_documents([state['transcript']])
    return {'transcript_chunks':chunks}

def identify_user_intent(state:ChatbotState):
    question=state['question']
    messages = [
        SystemMessage(content="You are a great intent evaluator. You are unbiased by opinions."),
        HumanMessage(content=f"""Evaluate this {question}. Identify what user wants from this question.
        ### Respond ONLY in structured format:
        - user_intent: 'QA' or 'TimestampFinder'or 'NotesGeneration'
        If the intent is none of the above then return QA """)]
    output = strucured_model.invoke(messages)
    return {'user_intent':output.user_intent}

def generate_context(state:ChatbotState):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
    vector_store = Chroma.from_documents(documents=state['transcript_chunks'],collection_name="transcript_embeddings",embedding=embeddings,)
    retriever = vector_store.as_retriever(search_type="similarity",search_kwargs={'k':4})
    retrieved_docs = retriever.invoke(state['question'])
    context = '\n\n'.join(doc.page_content for doc in retrieved_docs)
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
    #print(context)
    response = model.invoke(query)
    #print(final_prompt)
    answer = response.content
    return {'answer':answer}  

def router(state:ChatbotState):
    return state['user_intent']

def build_graph(checkpointer):
    graph = StateGraph(ChatbotState)
    graph.add_node('generate_transcript',generate_transcript)
    graph.add_node('generate_transcript_chunk',generate_transcript_chunk)
    graph.add_node('generate_context',generate_context)
    graph.add_node('generate_answer',generate_answer)
    graph.add_node('generate_notes',generate_notes)
    graph.add_node('identify_user_intent',identify_user_intent)
    graph.add_edge(START,'generate_transcript')
    graph.add_edge('generate_transcript','generate_transcript_chunk')
    graph.add_edge('generate_transcript_chunk','generate_context')
    graph.add_edge('generate_context','identify_user_intent')
    graph.add_conditional_edges('identify_user_intent',router,{
        'QA':'generate_answer',
        'NotesGeneration':'generate_notes'
    })
    graph.add_edge('generate_notes',END)
    graph.add_edge('generate_answer',END)
    chatbot = graph.compile(checkpointer=checkpointer)
    return chatbot