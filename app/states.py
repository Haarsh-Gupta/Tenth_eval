from typing import List, Dict, Any, Optional, TypedDict
import operator
from typing import Annotated

class AgentState(TypedDict):
    # --- Input ---
    files_path: List[str] # List of image/pdf paths
    instructions: Optional[str] # Evaluation instructions
    use_reranking: bool # Use BM25 reranking
    
    # --- Extracted from images (OCR Node) ---
    question: Optional[str]
    student_answer: Optional[str]
    
    # --- Planning/Query Generation Node ---
    search_queries: Annotated[List[str], operator.add]
    
    # --- Knowledge Retrieval Node ---
    context: Annotated[List[Dict[str, Any]], operator.add]
    
    # --- Evaluation Node ---
    feedback: Optional[Dict[str, Any]]
    annotated_files_path: List[str] # Paths to images with visual marks
