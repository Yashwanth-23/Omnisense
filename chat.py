from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
import chromadb

print("Loading Omnisense LangGraph Agent...")

# 1. Connect to the Vector Database
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_collection(name="langchain")

# 2. Build the Tool
@tool
def search_video_memory(query: str) -> str:
    """Query the audio or video or webpage transcription database. Use this tool to retrieve dialogue, events, and context from media files the user has uploaded. Input should be a specific search query based on the user's question."""
    print(f"\n[🔧 TOOL TRIGGERED] Searching database for: {query}")
    results = collection.query(query_texts=[query], n_results=1)
    
    if results['documents'] and results['documents'][0]:
        return results['documents'][0][0]
    return "No information found in the memory."

# 3. Initialize the Modern Chat Model
llm = ChatOllama(model="llama3.2")
tools = [search_video_memory]

# 4. Create the LangGraph Agent
agent_executor = create_react_agent(llm, tools)

print("\nOmnisense Agent Online. Type 'quit' to exit.")
print("-" * 50)

# 5. The Chat Loop
while True:
    user_input = input("\nYou: ")
    if user_input.lower() == 'quit':
        break
    
    try:
        # LangGraph expects a list of messages
        response = agent_executor.invoke({"messages": [("user", user_input)]})
        
        # The final answer is the content of the last message in the list
        final_answer = response["messages"][-1].content
        print(f"\n🤖 OMNISENSE: {final_answer}")
        
    except Exception as e:
        print(f"\n[ERROR] Agent got confused: {e}")