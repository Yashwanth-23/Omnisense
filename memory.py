from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

def build_vector_db():
    print("1. Loading the transcript...")
    # Loading the text file you just created
    loader = TextLoader("transcript.txt", encoding="utf-8")
    docs = loader.load()

    print("2. Slicing text into chunks...")
    # Break the text into xxx character blocks with a xxx-character overlap so the sentences won't cut in half (You can set them based on your transcript)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=300)
    chunks = text_splitter.split_documents(docs)
    print(f"   Created {len(chunks)} discrete memory chunks.")

    print("3. Loading local HuggingFace embedding model...")
    # This is a free, fast, local model that turns words into numbers
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    print("4. Building the ChromaDB vector database...")
    # This mathematically maps your chunks and saves them to a folder on your hard drive
    db = Chroma.from_documents(chunks, embeddings, persist_directory="./chroma_db")
    
    print("\n[SUCCESS] Memory Bank created! Your text is now searchable math.")

if __name__ == "__main__":
    try:
        build_vector_db()
    except Exception as e:
        print(f"\n[ERROR] {e}")