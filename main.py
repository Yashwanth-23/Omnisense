import os
import io
import gc
import logging
import asyncio
import tempfile
import socket
from urllib.parse import urlparse
import ipaddress
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import chromadb
from langchain_ollama import ChatOllama
from youtube_transcript_api import YouTubeTranscriptApi
import pymupdf as fitz
from langchain_community.document_loaders import WebBaseLoader
import pytesseract
from PIL import Image
from faster_whisper import WhisperModel
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL, "INFO"))

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class VideoRequest(BaseModel):
    url: str

class MessageDict(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[MessageDict]] = []

# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Omnisense API",
    description="Local Multimodal RAG Assistant",
    version="1.0.0"
)

# Setup ChromaDB
client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
collection = client.get_or_create_collection(name=config.CHROMA_COLLECTION)

# Setup Ollama
llm = ChatOllama(
    model=config.OLLAMA_MODEL, 
    base_url=config.OLLAMA_BASE_URL, 
    temperature=config.LLM_TEMPERATURE, 
    num_ctx=config.LLM_CONTEXT_WINDOW
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP
)

# ---------------------------------------------------------------------------
# Whisper Singleton (Lazy Load)
# ---------------------------------------------------------------------------
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper model lazily...")
        _whisper_model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper_model

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_valid_url(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False
    
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False
    except ValueError:
        try:
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except socket.gaierror:
            pass 
    return True

def chunk_and_upsert(text: str, source: str, base_id: str, doc_type: str = "text"):
    chunks = text_splitter.split_text(text)
    if not chunks:
        return 0
    
    docs = []
    metadatas = []
    ids = []
    
    for i, chunk in enumerate(chunks):
        docs.append(chunk)
        metadatas.append({"source": source, "type": doc_type})
        ids.append(f"{base_id}_chunk_{i}")
        
    collection.upsert(
        documents=docs,
        metadatas=metadatas,
        ids=ids
    )
    return len(chunks)

def sync_ocr(image_bytes: bytes) -> str:
    img_stream = io.BytesIO(image_bytes)
    image = Image.open(img_stream)
    return pytesseract.image_to_string(image)

def sync_whisper(file_path: str) -> str:
    model = get_whisper_model()
    segments, _ = model.transcribe(file_path)
    return " ".join([segment.text for segment in segments])

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "memories": collection.count()}

@app.post("/clear_memory")
async def clear_memory():
    global collection
    try:
        client.delete_collection(name=config.CHROMA_COLLECTION)
        collection = client.get_or_create_collection(name=config.CHROMA_COLLECTION)
        return {"status": "success", "message": "Memory cleared and recreated."}
    except Exception as e:
        logger.error(f"Error clearing memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear memory")

@app.post("/process_video")
async def process_video(req: VideoRequest):
    url = req.url
    if not is_valid_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL or private IP blocked.")
        
    try:
        if "youtube.com" in url or "youtu.be" in url:
            if "v=" in url:
                video_id = url.split("v=")[-1].split("&")[0]
            else:
                video_id = url.split("/")[-1]
                
            ytt_api = YouTubeTranscriptApi()
            fetched_transcript = await asyncio.to_thread(ytt_api.fetch, video_id, languages=['te', 'en'])
            
            if fetched_transcript and isinstance(fetched_transcript[0], dict):
                full_text = " ".join([snippet.get("text", "") for snippet in fetched_transcript])
            else:
                full_text = " ".join([getattr(snippet, "text", "") for snippet in fetched_transcript])
            
            num_chunks = chunk_and_upsert(full_text, url, video_id, "youtube")
            return {"status": "success", "message": f"Memorized YouTube Video: {video_id} ({num_chunks} chunks)"}
            
        else:
            loader = WebBaseLoader(url)
            docs = await asyncio.to_thread(loader.load)
            raw_text = docs[0].page_content
            clean_text = " ".join(raw_text.split())
            doc_id = url.replace("https://", "").replace("http://", "").replace("/", "_")[:40]
            
            num_chunks = chunk_and_upsert(clean_text, url, doc_id, "web_article")
            return {"status": "success", "message": f"Memorized Web Article: {url[:30]}... ({num_chunks} chunks)"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process Video Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process_file")
async def process_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        max_bytes = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail=f"File exceeds maximum size of {config.MAX_UPLOAD_SIZE_MB}MB")
            
        filename = file.filename.lower()
        
        if filename.endswith(".pdf"):
            pdf_document = fitz.open(stream=content, filetype="pdf")
            total_chunks = 0
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                text = page.get_text("text")
                if text.strip():
                    total_chunks += chunk_and_upsert(text, file.filename, f"{file.filename}_page_{page_num + 1}", "pdf")
            
            return {"status": "success", "message": f"Memorized PDF: {file.filename} ({total_chunks} chunks)"}
            
        elif filename.endswith(('.png', '.jpg', '.jpeg')):
            extracted_text = await asyncio.to_thread(sync_ocr, content)
            clean_text = extracted_text.strip()
            
            if not clean_text:
                raise HTTPException(status_code=400, detail="No readable text found in this image.")
                
            doc_id = f"img_{file.filename}"
            num_chunks = chunk_and_upsert(clean_text, file.filename, doc_id, "image")
            return {"status": "success", "message": f"Memorized Image Text: {file.filename} ({num_chunks} chunks)"}
            
        elif filename.endswith(('.mp4', '.mp3', '.wav', '.m4a')):
            ext = os.path.splitext(filename)[1]
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_path = temp_file.name
            try:
                temp_file.write(content)
                temp_file.close()
                
                logger.info(f"Transcribing {file.filename}...")
                extracted_text = await asyncio.to_thread(sync_whisper, temp_path)
                extracted_text = extracted_text.strip()
                
                if not extracted_text:
                    raise HTTPException(status_code=400, detail="Whisper couldn't hear any words.")
                    
                doc_id = f"audio_{file.filename}"
                num_chunks = chunk_and_upsert(extracted_text, file.filename, doc_id, "audio")
                return {"status": "success", "message": f"Transcribed Audio: {file.filename} ({num_chunks} chunks)"}
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    user_query = req.message
    history = req.history or []
    
    try:
        db_size = collection.count()
        if db_size == 0:
            return {"status": "success", "agent_response": "My memory is empty. Please upload a file or URL first!"}
            
        fetch_count = min(db_size, config.MAX_CONTEXT_CHUNKS)
        results = collection.query(query_texts=[user_query], n_results=fetch_count)
        
        context = " ".join(results['documents'][0]) if results and results.get('documents') and results['documents'][0] else "No memory found."
        
    except Exception as e:
        logger.error(f"Database Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
        
    estimated_tokens = len(context) // 4
    if estimated_tokens > config.LLM_CONTEXT_WINDOW:
        max_chars = config.LLM_CONTEXT_WINDOW * 4
        context = context[:max_chars]
        logger.warning(f"Context truncated to fit within {config.LLM_CONTEXT_WINDOW} tokens.")
        
    history_text = ""
    if history:
        recent_history = history[-5:]
        history_text = "[CONVERSATION HISTORY]\n"
        for msg in recent_history:
            history_text += f"{msg.role.upper()}: {msg.content}\n"
            
    prompt = f"""
[SYSTEM ROLE]
You are Omnisense, an intelligent and helpful AI assistant. You answer questions based ONLY on the provided MEMORY context.

[RULES]
1. The MEMORY may be a video transcript, a PDF document, or extracted image text.
2. Answer the user's question naturally and clearly based on the text below.
3. You are allowed to use basic logic to identify document types.
4. If the MEMORY does not contain enough information to answer the question, say "I cannot find this information in the uploaded documents." Do not invent facts.

{history_text}

[MEMORY]
{context}

[QUESTION]
{user_query}
"""
    
    logger.debug(f"Omni-Prompt Context length: {len(context)}")
    
    try:
        response = await llm.ainvoke(prompt)
        return {"status": "success", "agent_response": response.content}
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")