import streamlit as st
import requests

st.set_page_config(page_title="Omnisense OS", layout="wide")
st.title("🧠 Omnisense")


# --- SIDEBAR ---
st.markdown("""
    <style>
        /* 1. Turn the default chevrons invisible */
        [data-testid="collapsedControl"] svg, 
        [data-testid="stSidebarCollapseButton"] svg {
            visibility: hidden !important;
        }
        
        /* 2. CLOSED STATE: Inject the Lock */
        [data-testid="collapsedControl"] {
            position: relative;
        }
        [data-testid="collapsedControl"]::after {
            content: "🔒";
            font-size: 24px;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            visibility: visible !important;
            pointer-events: none; /* CRITICAL: Allows clicks to pass through to the button */
        }
        
        /* 3. OPEN STATE: Inject the Unlock */
        [data-testid="stSidebarCollapseButton"] {
            position: relative;
        }
        [data-testid="stSidebarCollapseButton"]::after {
            content: "🔓";
            font-size: 24px;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            visibility: visible !important;
            pointer-events: none; /* CRITICAL: Allows clicks to pass through to the button */
        }
    </style>
""", unsafe_allow_html=True)

# --- THE OMNI-INPUT PANEL ---
st.sidebar.header("Feed Omnisense")

# Create tabs for different input types
tab1, tab2 = st.sidebar.tabs(["Web Links", "Local Files"])

with tab1:
    yt_url = st.text_input("Paste YouTube or Web URL:")
    if st.button("Process URL"):
        with st.spinner("Processing Web Data..."):
            res = requests.post("http://host.docker.internal:8000/process_video", json={"url": yt_url})
            st.success(res.json().get("message", "Processed!"))

with tab2:
    # Accept multiple file types!
    uploaded_file = st.file_uploader("Upload PDF, Image, or Video", type=['pdf', 'png', 'jpg', 'mp4'])
    if st.button("Process File") and uploaded_file is not None:
        with st.spinner("Ingesting Local File..."):
            # We will send the actual file bytes to a new FastAPI endpoint
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            res = requests.post("http://host.docker.internal:8000/process_file", files=files)
            st.success(res.json().get("message", "Processed!"))

# --- CLEAR CHAT BUTTON ---
st.sidebar.divider()
if st.sidebar.button("🗑️ Clear Chat History"):
    st.session_state.messages = []
    st.rerun()

# --- THE CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Ask Omnisense anything...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            res = requests.post("http://host.docker.internal:8000/chat", json={"message": user_input})
            answer = res.json().get("agent_response", "Error connecting to brain.")
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})