# 🎥 Autonomous Video Intelligence RAG

A **Retrieval-Augmented Generation (RAG)** based chatbot that allows users to chat with YouTube videos. It can generate **QA responses** and **structured notes** from video transcripts using LLMs, vector search, and workflow orchestration.

Built using **RAG, LangGraph, LangChain, PostgreSQL (PGVector), Supabase, FastAPI, and Groq LLMs (LLaMA 3)**.



# 🚀 Features

* 🔍 Ask questions about YouTube videos
* 📝 Generate structured notes from video content
* ⚡ Efficient transcript caching in PostgreSQL
* 🧠 Semantic search using PGVector embeddings
* 🔄 Conditional indexing (avoids duplicate embedding)
* 🧩 LangGraph-based workflow orchestration
* 🤖 Intent classification (QA vs Notes Generation)
* 🌐 FastAPI backend for API access



# 🧰 Tech Stack

* **Backend:** FastAPI
* **LLM:** Groq (LLaMA 3.1)
* **Framework:** RAG + LangChain + LangGraph
* **Vector DB:** PostgreSQL + PGVector
* **Embeddings:** sentence-transformers (`all-mpnet-base-v2`)
* **Transcript API:** YouTubeTranscriptApi
* **ORM:** SQLAlchemy
* **State Management:** LangGraph StateGraph


# 🧠 Key Components

## 🔹 1. Transcript Handling

* Fetches YouTube captions
* Stores in PostgreSQL

## 🔹 2. Conditional Indexing

* Checks if video already indexed
* Prevents duplicate embeddings

## 🔹 3. Vector Search

* Uses PGVector for semantic retrieval
* Retrieves top-k relevant chunks

## 🔹 4. Intent Classification

* Classifies query into:

  * QA
  * NotesGeneration

## 🔹 5. LangGraph Workflow

* Controls full pipeline execution
* Handles routing between QA and Notes nodes

