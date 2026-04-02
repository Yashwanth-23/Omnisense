# 🧠 Omnisense: Local Multimodal RAG AI

Omnisense is a fully private, locally hosted AI assistant equipped with a Multimodal Retrieval-Augmented Generation (RAG) architecture. It doesn't just read text, it can **see** images and **hear** audio, storing everything in a persistent vector database to provide intelligent, hallucination-free answers using local LLMs.

Because everything runs locally via Docker and Ollama, **zero data ever leaves your machine.**

## ✨ Core Capabilities

* 📖 **The Text (Document Analysis):** Upload PDFs or provide webpage URLs. Omnisense parses, chunks, and memorizes massive documents using LangChain and PyMuPDF.
* 👁️ **The Vision (OCR):** Upload receipts, screenshots, or photos. Extracts text right out of the pixels using Tesseract OCR and Pillow.
* 🎙️ **The Audio (Transcription):** Upload `.mp4`, `.mp3`, or `.wav` files. Transcribes spoken words, handles heavy accents, and cuts through background noise using OpenAI's Whisper model.
* 🧠 **The Memory Engine:** Converts all processed text, vision, and audio into vector embeddings, storing them permanently in ChromaDB for instant semantic retrieval.

## 🛠️ Tech Stack

* **Frontend Interface:** Streamlit
* **Backend API:** FastAPI, Python
* **Large Language Model:** Llama 3.2 (via Ollama)
* **Audio Processing:** Whisper (Small)
* **Image Processing:** Tesseract OCR, Pillow
* **Vector Database:** ChromaDB
* **Orchestration:** Docker & Docker Compose

---

## 🚀 Getting Started

### Prerequisites
Before running Omnisense, ensure you have the following installed on your machine:
1. Docker Desktop
2. Ollama

### 1. Download the Local Model
Omnisense relies on Llama 3.2 to process the data and answer your questions. Pull the model to your local machine:

    ollama run llama3.2

### 2. Clone the Repository
Download the project files to your computer:

    git clone https://github.com/Yashwanth-23/Omnisense.git
    cd Omnisense

### 3. Build and Launch
Use Docker Compose to build the environment and start the servers. This will automatically install all dependencies, including the Whisper models and Tesseract OS packages:

    docker-compose up --build

*(Note: The first time you process an audio file, it may take a minute or two to download the Whisper weights into the container).*

### 4. Access the UI
Once the terminal shows the Uvicorn server is running, open your web browser and navigate to `http://localhost:8501`
---
![Omnisense User Interface](ui.png)
## 🛡️ Privacy
Omnisense is designed for absolute privacy. It does not require API keys, it does not send telemetry, and it operates entirely offline (aside from the initial model downloads). Your files and databases remain on your local hard drive.