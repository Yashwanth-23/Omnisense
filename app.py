import streamlit as st
import requests
import config

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
        # Input validation for URL
        if not yt_url or not yt_url.strip():
            st.warning("Please enter a URL first.")
        else:
            with st.spinner("Processing Web Data..."):
                try:
                    res = requests.post(f"{config.BACKEND_URL}/process_video", json={"url": yt_url.strip()}, timeout=300)
                    if res.status_code == 200:
                        st.success(res.json().get("message", "Processed!"))
                    else:
                        st.error(f"Error {res.status_code}: {res.text}")
                except requests.exceptions.Timeout:
                    st.error("Request timed out after 5 minutes.")
                except requests.exceptions.ConnectionError:
                    st.error("Failed to connect to the backend server.")
                except requests.exceptions.JSONDecodeError:
                    st.error("Received an invalid JSON response from the server.")
                except Exception as e:
                    st.error(f"An unexpected error occurred: {e}")

with tab2:
    # Accept multiple file types, including the new audio and image formats
    uploaded_file = st.file_uploader("Upload PDF, Image, Video, or Audio", type=['pdf', 'png', 'jpg', 'jpeg', 'mp4', 'mp3', 'wav', 'm4a'])
    if st.button("Process File"):
        # Input validation for file
        if uploaded_file is None:
            st.warning("Please upload a file first.")
        else:
            with st.spinner("Ingesting Local File..."):
                try:
                    # We send the actual file bytes to the FastAPI endpoint
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    res = requests.post(f"{config.BACKEND_URL}/process_file", files=files, timeout=300)
                    if res.status_code == 200:
                        st.success(res.json().get("message", "Processed!"))
                    else:
                        st.error(f"Error {res.status_code}: {res.text}")
                except requests.exceptions.Timeout:
                    st.error("Request timed out after 5 minutes.")
                except requests.exceptions.ConnectionError:
                    st.error("Failed to connect to the backend server.")
                except requests.exceptions.JSONDecodeError:
                    st.error("Received an invalid JSON response from the server.")
                except Exception as e:
                    st.error(f"An unexpected error occurred: {e}")

# --- CLEAR CHAT BUTTON ---
st.sidebar.divider()
if st.sidebar.button("🗑️ Clear Chat History"):
    st.session_state.messages = []
    st.rerun()

# --- CLEAR MEMORY BUTTON ---
if st.sidebar.button("🧹 Clear All Memory"):
    with st.spinner("Clearing memory..."):
        try:
            res = requests.post(f"{config.BACKEND_URL}/clear_memory", timeout=300)
            if res.status_code == 200:
                st.success("Memory cleared successfully!")
            else:
                st.error(f"Error {res.status_code}: {res.text}")
        except requests.exceptions.Timeout:
            st.error("Request timed out after 5 minutes.")
        except requests.exceptions.ConnectionError:
            st.error("Failed to connect to the backend server.")
        except requests.exceptions.JSONDecodeError:
            st.error("Received an invalid JSON response from the server.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

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
            try:
                # Send the last 10 messages for multi-turn context
                history = st.session_state.messages[-10:]
                payload = {
                    "message": user_input,
                    "history": history
                }
                res = requests.post(f"{config.BACKEND_URL}/chat", json=payload, timeout=300)
                
                if res.status_code == 200:
                    answer = res.json().get("agent_response", "Error connecting to brain.")
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.error(f"Error {res.status_code}: {res.text}")
            except requests.exceptions.Timeout:
                st.error("Request timed out after 5 minutes.")
            except requests.exceptions.ConnectionError:
                st.error("Failed to connect to the backend server.")
            except requests.exceptions.JSONDecodeError:
                st.error("Received an invalid JSON response from the server.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")