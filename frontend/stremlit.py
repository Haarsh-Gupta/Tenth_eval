import streamlit as st
import os
import tempfile
import sys
from typing import List, Optional

# Add the project root to sys.path to allow imports from app.*
# streamlit_app.py is in class_x_evaluation/
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from app.agent import ClassXEvaluationAgent
from app.prompts import instructions_prompt

# Page config
st.set_page_config(page_title="Class X History Evaluation", page_icon="📚", layout="wide")

# Custom CSS for premium look
st.markdown("""
    <style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
    }
    div[data-testid="stExpander"] {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        border: 1px solid rgba(128, 128, 128, 0.2);
    }
    .feedback-card {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #4CAF50;
        border-top: 1px solid rgba(128, 128, 128, 0.2);
        border-right: 1px solid rgba(128, 128, 128, 0.2);
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 20px;
    }
    .metric-container {
        background-color: rgba(76, 175, 80, 0.1);
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    /* Ensure text visibility */
    .stMarkdown, .stText, .stJson, .feedback-card h3, .feedback-card p, div[data-testid="stExpander"] p {
        color: inherit !important;
    }
    .feedback-card h3 {
        margin-top: 0;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📚 Class X History Evaluation Pipeline")
st.markdown("Automated grading for Class X History using specialized knowledge retrieval (RAG).")
st.markdown("---")

# Initialize Agent
@st.cache_resource
def get_agent():
    return ClassXEvaluationAgent()

agent = get_agent()
metadata = agent.get_metadata()

# Sidebar for metadata
with st.sidebar:
    st.header("Pipeline Info")
    st.info(f"**Model:** {metadata.get('model_name')}")
    st.info(f"**Provider:** {metadata.get('model_provider')}")
    st.write(metadata.get('notes'))
    
    st.markdown("---")
    st.subheader("Instructions")
    st.markdown("""
    1. **Upload** an image/PDF or **Paste** the text.
    2. Click **Run Evaluation**.
    3. Review the **Thinking** process and **RAG** context.
    4. See the final **Marks** and **Feedback**.
    """)

# Input Section
st.header("📥 Input Student Work")
tab1, tab2, tab3 = st.tabs(["📄 Upload Image/PDF", "✍️ Manual Text Input", "⚙️ Settings"])

with tab1:
    uploaded_files = st.file_uploader("Upload student answer sheet (Images or PDF)", 
                                    type=["jpg", "jpeg", "png", "pdf"], 
                                    accept_multiple_files=True)
    if uploaded_files:
        st.markdown("### 🖼️ Upload Preview")
        cols = st.columns(min(len(uploaded_files), 3))
        for i, uploaded_file in enumerate(uploaded_files):
            with cols[i % 3]:
                st.image(uploaded_file, caption=uploaded_file.name, width='stretch')

with tab2:
    col_in1, col_in2 = st.columns(2)
    with col_in1:
        manual_question = st.text_area("Question", placeholder="Paste the question text here...", height=150)
    with col_in2:
        manual_answer = st.text_area("Student Answer", placeholder="Paste the student's answer text here...", height=150)

with tab3:
    st.subheader("Evaluation Instructions")
    st.info("Set the criteria for how the student's answer should be evaluated.")
    eval_instructions = st.text_area(
        "Instructions", 
        value=st.session_state.get("eval_instructions", instructions_prompt),
        height=200,
        help="Provide specific rules for the AI examiner to follow."
    )
    st.session_state["eval_instructions"] = eval_instructions

# Run Evaluation
if st.button("🚀 Run Evaluation", width='stretch'):
    file_paths = []
    
    # Save uploaded files to temp directory
    if uploaded_files:
        for uploaded_file in uploaded_files:
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                file_paths.append(tmp_file.name)
    
    # Check if we have any input
    has_text = manual_question.strip() != "" and manual_answer.strip() != ""
    
    if not file_paths and not has_text:
        st.warning("⚠️ Please provide either uploaded files or both manual question and answer.")
    else:
        with st.status("🚀 Evaluation in Progress...", expanded=True) as status:
            try:
                # Use instructions from session state
                current_instr = st.session_state.get("eval_instructions", instructions_prompt)
                
                # Use the streaming method to show progress
                stream = agent.stream_evaluation(
                    question=manual_question if has_text else None,
                    student_answer=manual_answer if has_text else None,
                    file_paths=file_paths if not has_text else None,
                    instructions=current_instr
                )
                
                final_state = {}
                for node_name, state_update in stream:
                    if node_name == "ocr":
                        status.write("📝 **Step 1:** Extracting text from images (OCR)...")
                    elif node_name == "query":
                        status.write("🧠 **Step 2:** Analyzing question and generating search queries...")
                    elif node_name == "rag":
                        status.write("🔎 **Step 3:** Retrieving relevant facts from Class 10 History textbook...")
                    elif node_name == "evaluation":
                        status.write("👨‍🏫 **Step 4:** Grading answer and generating visual annotations...")
                    
                    # Accumulate state safely
                    if state_update and isinstance(state_update, dict):
                        final_state.update(state_update)
                
                # Format final result (matching full_evaluation structure)
                result = {
                    "question": final_state.get("question"),
                    "student_answer": final_state.get("student_answer"),
                    "search_queries": final_state.get("search_queries"),
                    "context": final_state.get("context"),
                    "feedback_res": final_state.get("feedback"),
                    "annotated_files_path": final_state.get("annotated_files_path", [])
                }

                # Store in session state for persistence
                st.session_state["eval_result"] = result
                st.session_state["last_file_paths"] = file_paths
                st.session_state["has_text_input"] = has_text
                
                status.update(label="✅ Evaluation Complete!", state="complete", expanded=False)
                st.rerun() # Refresh to show results outside the button block
                
            except Exception as e:
                status.update(label="❌ Evaluation Failed", state="error")
                st.error(f"Error: {e}")
                st.exception(e)

# --- PERSISTENT RESULTS DISPLAY ---
result = st.session_state.get("eval_result")
file_paths = st.session_state.get("last_file_paths", [])
has_text = st.session_state.get("has_text_input", False)

if result:
    st.markdown("---")
    res_col1, res_col2 = st.columns([2, 1])
    
    with res_col1:
        # 1. Answer Sheet Comparison (Initial vs Marked)
        annotated_files = result.get('annotated_files_path', [])
        if annotated_files or file_paths:
            st.header("📸 Answer Sheet Comparison")
            num_images = max(len(file_paths or []), len(annotated_files or []))
            
            for i in range(num_images):
                pv_col1, pv_col2 = st.columns(2)
                with pv_col1:
                    st.markdown("**Initial Answer Sheet**")
                    if file_paths and i < len(file_paths) and os.path.exists(file_paths[i]):
                        st.image(file_paths[i], width='stretch')
                with pv_col2:
                    st.markdown("**Marked Answer Sheet**")
                    if i < len(annotated_files) and os.path.exists(annotated_files[i]):
                        st.image(annotated_files[i], width='stretch')
                st.markdown("---")
    
    with res_col2:
        # Final Result Metrics
        st.header("📊 Evaluation")
        feedback = result.get('feedback_res', {})
        if isinstance(feedback, dict):
            st.metric("Marks", f"{feedback.get('marks_awarded', 0)}/{feedback.get('total_marks', 10)}")
            st.metric("Performance", feedback.get('overall_performance', 'N/A').title())
            
            st.markdown(f"""
            <div class="feedback-card">
                <h4>Teacher Feedback</h4>
                <p>{feedback.get('content_feedback', 'No feedback.')}</p>
            </div>
            """, unsafe_allow_html=True)

    # Secondary Details
    with st.expander("📝 OCR & RAG Details"):
        tab_ocr, tab_rag = st.tabs(["Extracted Text", "Knowledge Source"])
        with tab_ocr:
            st.subheader("Extracted Question")
            st.code(result.get('question', ''))
            st.subheader("Extracted Student Answer")
            st.code(result.get('student_answer', ''))
        with tab_rag:
            for item in result.get('context', []):
                st.markdown(f"**Source:** {item.get('book_name')}")
                st.info(item.get('content'))

    if st.button("🗑️ Reset and Clear Results"):
        # Cleanup files
        marked_paths = result.get('annotated_files_path', [])
        all_files = file_paths + (marked_paths if marked_paths else [])
        for p in all_files:
            if p and os.path.exists(str(p)): 
                os.remove(str(p))
        st.session_state["eval_result"] = None
        st.rerun()
                

