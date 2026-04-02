from fastapi import FastAPI, UploadFile, File
import chromadb
from langchain_community.chat_models import ChatOllama
from youtube_transcript_api import YouTubeTranscriptApi
import fitz  # PyMuPDF for reading PDFs
from langchain_community.document_loaders import WebBaseLoader
import pytesseract
from PIL import Image
import io
import whisper
import os
import gc


app = FastAPI()

# 1. Setup ChromaDB
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="youtube_memories")

# 2. Setup Ollama
llm = ChatOllama(model="llama3.2", base_url="http://host.docker.internal:11434", temperature=0, num_ctx=2048)

@app.post("/process_video")
async def process_video(data: dict):
    url = data.get("url")
    try:
        # --- 1: YOUTUBE VIDEOS ---
        if "youtube.com" in url or "youtu.be" in url:
            if "v=" in url:
                video_id = url.split("v=")[-1].split("&")[0]
            else:
                video_id = url.split("/")[-1]
                
            ytt_api = YouTubeTranscriptApi()
            fetched_transcript = ytt_api.fetch(video_id, languages=['te', 'en'])
            full_text = " ".join([snippet.text for snippet in fetched_transcript])
            
            collection.add(
                documents=[full_text],
                metadatas=[{"source": url}],
                ids=[video_id]
            )
            return {"status": "success", "message": f"Memorized YouTube Video: {video_id}"}
            
        # --- 2: REGULAR WEBPAGES / ARTICLES ---
        else:
            # 1. Load the webpage
            loader = WebBaseLoader(url)
            docs = loader.load()
            
            # 2. Extract the raw text
            raw_text = docs[0].page_content
            
            # 3. Clean up the text (remove massive blank spaces from HTML menus)
            clean_text = " ".join(raw_text.split())
            
            # 4. Create a unique ID from the URL
            doc_id = url.replace("https://", "").replace("http://", "").replace("/", "_")[:40]
            
            # 5. Inject into Memory
            collection.add(
                documents=[clean_text],
                metadatas=[{"source": url}],
                ids=[doc_id]
            )
            return {"status": "success", "message": f"Memorized Web Article: {url[:30]}..."}
            
    except Exception as e:
        return {"status": "error", "message": f"Processing Error: {str(e)}"}
    
@app.post("/process_file")
async def process_file(file: UploadFile = File(...)):
    try:
        # Read the file bytes into memory
        content = await file.read()
        
        # --- 1. PDF PROCESSING ---
        if file.filename.lower().endswith(".pdf"):
            # Open the PDF directly from memory
            pdf_document = fitz.open(stream=content, filetype="pdf")
            
            documents = []
            metadatas = []
            ids = []
            
            # Read it page by page (This acts as a natural text chunker!)
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                text = page.get_text("text")
                
                # Only save pages that actually have text
                if text.strip(): 
                    documents.append(text)
                    metadatas.append({"source": file.filename, "page": page_num + 1})
                    ids.append(f"{file.filename}_page_{page_num + 1}")
                    
            # Inject into ChromaDB
            if documents:
                collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
            return {"status": "success", "message": f"Memorized PDF: {file.filename} ({len(documents)} pages)"}
        
        # --- 2. MULTI-MODAL PLACEHOLDERS ---
        # --- 1: THE IMAGE PROCESSING (OCR) ---
        elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            
            img_stream= io.BytesIO(content)
            img_stream.seek(0)

            # 1. Read the image bytes into memory
            image = Image.open(img_stream)
            
            # 2. Extract the text using Tesseract
            extracted_text = pytesseract.image_to_string(image)
            
            # 3. Clean up and check if it actually found anything
            clean_text = extracted_text.strip()
            if not clean_text:
                return {"status": "error", "message": "No readable text found in this image."}
            
            # 4. Inject into ChromaDB Memory
            doc_id = f"img_{file.filename}"
            collection.add(
                documents=[clean_text],
                metadatas=[{"source": file.filename, "type": "image"}],
                ids=[doc_id]
            )
            
            return {"status": "success", "message": f"Memorized Image Text: {file.filename}"}
    
        # --- 2: THE AUDIO (WHISPER) ---
        elif file.filename.lower().endswith(('.mp4', '.mp3', '.wav', '.m4a')):
            
            # 1. Whisper needs a physical file on the hard drive, not just memory bytes
            temp_path = f"temp_{file.filename}"
            with open(temp_path, "wb") as f:
                f.write(content)

            # 2. Load the model 
            print(f"DEBUG: Loading Whisper model and transcribing {file.filename}...")
            model = whisper.load_model("small")
            result = model.transcribe(temp_path, fp16=False)
            
            # 3. Clean up the temporary file so Docker doesn't fill up
            os.remove(temp_path)

            # --- FREE THE MEMORY ---
            del model
            gc.collect()
            
            extracted_text = result["text"].strip()
            
            if not extracted_text:
                return {"status": "error", "message": "Whisper couldn't hear any words."}
            
            # 4. Inject into Memory
            doc_id = f"audio_{file.filename}"
            collection.add(
                documents=[extracted_text],
                metadatas=[{"source": file.filename, "type": "audio_transcript"}],
                ids=[doc_id]
            )
            
            return {"status": "success", "message": f"Transcribed Audio: {file.filename}"}

    except Exception as e:
        # This closes the try block and handles any errors
        return {"status": "error", "message": f"Processing failed: {str(e)}"}

@app.post("/chat")
async def chat_endpoint(data: dict):
    user_query = data.get("message")
    
    try:
        # Check how many memories exist so ChromaDB doesn't crash on small PDFs
        db_size = collection.count()
        if db_size == 0:
            return {"status": "success", "agent_response": "My memory is empty. Please upload a file or URL first!"}
            
        # Fetch up to 5 chunks, or fewer if the document is small (you can tweak according to the documents you feed)
        fetch_count = min(db_size, 5)
        results = collection.query(query_texts=[user_query], n_results=fetch_count)
        
        # Clean the context
        context = " ".join(results['documents'][0]) if results['documents'] else "No memory found."
        
    except Exception as e:
        return {"status": "error", "agent_response": f"Database Error: {str(e)}"}
    
    # --- THE OMNI-PROMPT (You can change it depending on your needs and responses)---
    prompt = f"""
    [SYSTEM ROLE]
    You are Omnisense, an intelligent and helpful AI assistant. You answer questions based ONLY on the provided MEMORY context.

    [RULES]
    1. The MEMORY may be a video transcript, a PDF document, or extracted image text.
    2. Answer the user's question naturally and clearly based on the text below.
    3. You are allowed to use basic logic to identify document types (e.g., if a document starts with "Dear Hiring Manager", you can infer it is a cover letter).
    4. If the MEMORY does not contain enough information to answer the question, say "I cannot find this information in the uploaded documents." Do not invent facts.

    MEMORY:
    {context}

    QUESTION:
    {user_query}
    """
    
    print(f"DEBUG - WHAT THE AI READS: {context}")
    response = llm.invoke(prompt)
    return {"status": "success", "agent_response": response.content}