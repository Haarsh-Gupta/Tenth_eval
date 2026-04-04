import os
import base64
import mimetypes
import logging
from typing import Dict, Any, List

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from .config import settings
from .vector_store import RAG_VECTOR_STORE

from .states import AgentState
from .prompts import (
    OCR_PROMPT_TEXT,
    ocr_parser,
    QUERY_GENERATOR_PROMPT,
    query_parser,
    EVALUATION_PROMPT,
    evaluation_parser,
    format_context,
    instructions_prompt
)
from app.utils.image_marker import draw_marks_on_image, create_virtual_marked_sheet

logger = logging.getLogger(__name__)

# ==================== LLM SETUP ====================
llm_pro_3_1 = ChatGoogleGenerativeAI(
    model="gemini-3.1-pro-preview", 
    temperature=0.0, 
    max_retries=2,
    timeout=60.0,
    google_api_key=settings.google_api_key
)

llm_flash_2_5 = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=1.0, 
    # thinking_level="high", # Only supported for reasoning models
    google_api_key=settings.google_api_key
)

llm_pro_2_5 = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro", 
    temperature=0.0, 
    google_api_key=settings.google_api_key
)


# ==================== HELPER: CONTENT PREPARATION ====================
def prepare_image_content(files_path: List[str]) -> List[Dict[str, Any]]:
    # Standard LangChain/Google multimodal format
    content_blocks = [{"type": "text", "text": OCR_PROMPT_TEXT.replace("{format_instructions}", ocr_parser.get_format_instructions())}]
    
    for path in files_path:
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            continue
            
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type is None:
            if path.lower().endswith(('.jpg', '.jpeg')): mime_type = 'image/jpeg' 
            elif path.lower().endswith('.png'): mime_type = 'image/png'
            elif path.lower().endswith('.pdf'): mime_type = 'application/pdf'
            else: mime_type = 'application/octet-stream' 
            
        with open(path, 'rb') as f:
            base64_data = base64.b64encode(f.read()).decode("utf-8")
        
        # Using image_url with data URI for better compatibility
        content_blocks.append({
            "type": "image_url", 
            "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}
        })
        
    return content_blocks

def prepare_image_content_for_evaluation(prompt_text: str, files_path: List[str]) -> List[Dict[str, Any]]:
    content_blocks = [{"type": "text", "text": prompt_text}]
    
    from PIL import Image, ImageOps
    import io

    for path in files_path:
        if not os.path.exists(path): continue
        
        try:
            # Explicitly load and transpose the image so Gemini sees the exact same
            # oriented pixel grid that our drawing tool (image_marker.py) will see.
            img = Image.open(path)
            img = ImageOps.exif_transpose(img).convert("RGB")
            
            # Save to buffer as JPEG
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=95)
            base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            mime_type = "image/jpeg"
        except Exception as e:
            logger.error(f"Image normalization failed for {path}: {e}")
            # Fallback to raw bytes
            mime_type, _ = mimetypes.guess_type(path)
            if mime_type is None: mime_type = 'image/jpeg'
            with open(path, 'rb') as f:
                base64_data = base64.b64encode(f.read()).decode("utf-8")

        content_blocks.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}
        })
    return content_blocks

def _extract_text_from_response(response) -> str:
    if isinstance(response.content, str):
        return response.content
    elif isinstance(response.content, list):
        return "".join(
            p.get("text", "") if isinstance(p, dict) else (p.text if hasattr(p, "text") else str(p))
            for p in response.content
        )
    return str(response.content)

# ==================== GRAPH NODES ====================

def ocr_node(state: AgentState) -> Dict:
    """Step 1: Extract Question and Answer from image(s)."""
    logger.info("📝 OCR Node: Extracting text from images...")
    
    # Bypass OCR if question and student_answer are already provided
    if state.get("question") and state.get("student_answer"):
        logger.info("📝 OCR Node: Question and Answer provided directly. Bypassing OCR.")
        return {}

    files_path = state.get("files_path", [])
    
    if not files_path:
        return {"question": "No files provided", "student_answer": "No files provided"}
        
    message_content = prepare_image_content(files_path)
    if len(message_content) == 1: # Only prompt text, no images
        return {"question": "Files could not be loaded", "student_answer": ""}
        
    # For multimodal calls, include instruction in the text block for maximum compatibility
    ocr_instruction = "CRITICAL: You are a literal OCR extractor. Your ONLY goal is to transcribe text EXACTLY as it appears in the image. DO NOT correct any mistakes, typos, or grammatical errors. If a student wrote it wrong, you MUST extract it wrong."
    
    # Prepend instruction to the text component of message_content
    for block in message_content:
        if block["type"] == "text":
            block["text"] = f"{ocr_instruction}\n\n{block['text']}"
            break
            
    msg = HumanMessage(content=message_content)
    try:
        # Primary OCR: 3.1 Pro
        response = llm_pro_3_1.invoke([msg])
        data = ocr_parser.parse(_extract_text_from_response(response))
    except Exception as e:
        logger.warning(f"Primary OCR (3.1) failed: {e}. Falling back to 2.5 Pro.")
        try:
            # Fallback OCR: 2.5 Pro
            response = llm_pro_2_5.invoke([msg])
            data = ocr_parser.parse(_extract_text_from_response(response))
        except Exception as e2:
            logger.error(f"Fallback OCR (2.5) also failed: {e2}")
            return {"question": "Error during OCR", "student_answer": f"Details: {e2}"}
    
    return {
        "question": data.get("question", ""),
        "student_answer": data.get("answer", "")
    }

def query_node(state: AgentState) -> Dict:
    """Step 2: Generate RAG lookup queries based on the Question."""
    logger.info("🧠 Query Node: Generating RAG queries...")
    # Defensive casting to string to avoid Pydantic validation errors
    question = str(state.get("question", ""))
    
    try:
        prompt_str = QUERY_GENERATOR_PROMPT.format(question=question)
        response = llm_flash_2_5.invoke([HumanMessage(content=prompt_str)])
        data = query_parser.parse(_extract_text_from_response(response))
        
        # New queries
        new_queries = data.get("queries", [])
        return {"search_queries": new_queries}
    except Exception as e:
        logger.error(f"Query Generator Error: {e}")
        # Add a fallback query just in case
        return {"search_queries": [question]}

def rag_node(state: AgentState) -> Dict:
    """Step 3: Retrieve Class X specific context from knowledge base."""
    logger.info("🔎 RAG Node: Searching Pinecone for 'History class tenth'...")
    queries = state.get("search_queries", [])
    use_rerank = state.get("use_reranking", False)
    
    # Use a dictionary to keep only unique chunks by content
    unique_context_map = {}
    
    for q in queries:
        try:
            # Filter solely for History Class 10 book as per user request
            filter_dict = {"book_name": "History Class 10"}
            # Fetch 10 if reranking, else 3
            fetch_k = 10 if use_rerank else 3
            results = RAG_VECTOR_STORE.search_and_rerank(
                query=q, k=3, fetch_k=fetch_k, filter=filter_dict, rerank=use_rerank
            )
            
            for doc in results:
                content = getattr(doc, "page_content", "") # Handle cases if it's not a Doc object
                if hasattr(doc, "page_content"):
                    content = doc.page_content.strip()
                else:
                    content = str(doc).strip()
                    
                if content not in unique_context_map:
                    unique_context_map[content] = {
                        "content": content,
                        "book_name": doc.metadata.get("book_name", "Unknown") if hasattr(doc, "metadata") else "History class tenth"
                    }
        except Exception as e:
            logger.error(f"RAG Error on query '{q}': {e}")
            
    final_context = list(unique_context_map.values())
    logger.info(f"🔎 RAG Node: Found {len(final_context)} unique context items.")
    return {"context": final_context}


def evaluation_node(state: AgentState) -> Dict:
    """Step 4: Evaluate the student's answer using the text context and images."""
    logger.info("👨‍🏫 Evaluation Node: Grading student answer...")
    # Defensive casting to string to avoid Pydantic validation errors
    question = str(state.get("question", ""))
    student_answer = str(state.get("student_answer", ""))
    context_str = format_context(state.get("context", []))
    instructions = state.get("instructions") or instructions_prompt
    files_path = state.get("files_path", [])
    
    prompt_text = EVALUATION_PROMPT.format(
        question=question,
        student_answer=student_answer,
        context=context_str,
        instructions=instructions,
        format_instructions=evaluation_parser.get_format_instructions()
    )
    
    try:
        if files_path:
            content = prepare_image_content_for_evaluation(prompt_text, files_path)
            response = llm_flash_2_5.invoke([HumanMessage(content=content)])
        else:
            response = llm_flash_2_5.invoke([HumanMessage(content=prompt_text)])
            
        eval_data = evaluation_parser.parse(_extract_text_from_response(response))
        
        # Draw marks on image if available
        annotated_paths = []
        if eval_data.get("visual_annotations"):
            if files_path:
                for img_path in files_path:
                    try:
                        marked_path = draw_marks_on_image(
                            image_path=img_path,
                            annotations=eval_data["visual_annotations"],
                            marks_awarded=eval_data.get("marks_awarded", 0),
                            total_marks=eval_data.get("total_marks", 10)
                        )
                        if marked_path:
                            annotated_paths.append(marked_path)
                    except Exception as draw_error:
                        logger.error(f"Drawing Error: {draw_error}")
            else:
                # Create a virtual sheet if no input image exists
                try:
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        virtual_path = create_virtual_marked_sheet(
                            text=student_answer,
                            annotations=eval_data["visual_annotations"],
                            marks_awarded=eval_data.get("marks_awarded", 0),
                            total_marks=eval_data.get("total_marks", 10),
                            output_path=tmp.name
                        )
                        if virtual_path:
                            annotated_paths.append(virtual_path)
                except Exception as virt_error:
                    logger.error(f"Virtual Sheet Error: {virt_error}")
        
        return {
            "feedback": eval_data,
            "annotated_files_path": annotated_paths
        }
    except Exception as e:
        logger.error(f"Evaluation Error: {e}")
        return {"feedback": {"error": str(e)}, "annotated_files_path": []}

# ==================== GRAPH BUILD ====================

def create_class_x_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("ocr", ocr_node)
    workflow.add_node("query", query_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("evaluation", evaluation_node)
    
    # Establish edges
    workflow.set_entry_point("ocr")
    workflow.add_edge("ocr", "query")
    workflow.add_edge("query", "rag")
    workflow.add_edge("rag", "evaluation")
    workflow.add_edge("evaluation", END)
    
    return workflow.compile()

# Instantiated graph ready to use
class_x_evaluator = create_class_x_graph()

