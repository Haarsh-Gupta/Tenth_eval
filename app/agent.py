from typing import List, Optional, Dict, Any, Generator
from .graph import class_x_evaluator
from .prompts import instructions_prompt

class ClassXEvaluationAgent:
    def __init__(self):
        self.graph = class_x_evaluator

    def get_metadata(self) -> dict:
        return {
            "model_name": "Tiered (Pro 3.1/2.5 & Flash 2.5)",
            "model_provider": "Google Generative AI",
            "notes": "Multimodal OCR with Pro fallback, RAG-enhanced evaluation using Flash.",
            "ocr_primary": "Gemini 3.1 Pro",
            "ocr_fallback": "Gemini 2.5 Pro",
            "reasoning": "Gemini 2.5 Flash"
        }

    def stream_evaluation(self, question: Optional[str] = None, student_answer: Optional[str] = None, file_paths: Optional[List[str]] = None, instructions: Optional[str] = None) -> Generator:
        """Yield progress as the evaluation graph runs."""
        initial_state = {
            "files_path": file_paths or [],
            "question": question,
            "student_answer": student_answer,
            "instructions": instructions or instructions_prompt,
            "search_queries": [],
            "context": [],
            "feedback": None
        }
        
        # Stream the graph execution
        for event in self.graph.stream(initial_state):
            # Each 'event' is a dict where keys are node names and values are their state updates
            if not event:
                continue
            for node_name, state_update in event.items():
                if state_update is not None:
                    yield node_name, state_update

    def full_evaluation(self, question: Optional[str] = None, student_answer: Optional[str] = None, file_paths: Optional[List[str]] = None, instructions: Optional[str] = None) -> Dict[str, Any]:
        """Run the full evaluation pipeline (Synchronous)."""
        initial_state = {
            "files_path": file_paths or [],
            "question": question,
            "student_answer": student_answer,
            "instructions": instructions or instructions_prompt,
            "search_queries": [],
            "context": [],
            "feedback": None
        }
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        # Format result for UI
        return {
            "question": final_state.get("question"),
            "student_answer": final_state.get("student_answer"),
            "search_queries": final_state.get("search_queries"),
            "context": final_state.get("context"),
            "feedback_res": final_state.get("feedback"),
            "annotated_files_path": final_state.get("annotated_files_path", [])
        }
