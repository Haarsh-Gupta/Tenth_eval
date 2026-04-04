import os
import uuid
import json
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from app.graph import class_x_evaluator
from app.states import AgentState
import uvicorn
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CBSE Answer Sheet Evaluator API")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories for uploads and results
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static directory to serve images
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

# Human-readable step labels
STEP_LABELS = {
    "ocr": {"message": "📝 Extracting text from answer sheets (OCR)...", "icon": "scan"},
    "query": {"message": "🧠 Generating search queries...", "icon": "search"},
    "rag": {"message": "📚 Retrieving reference context from knowledge base...", "icon": "database"},
    "evaluation": {"message": "🎯 Evaluating answers and generating feedback...", "icon": "grade"},
}


@app.post("/evaluate")
async def evaluate(
    files: List[UploadFile] = File(...),
    instructions: str = Form(None),
    use_reranking: bool = Form(False)
):
    """
    Evaluates answer sheets and streams status updates via SSE.
    """
    # 1. Save uploaded files
    temp_paths = []
    original_filenames = []
    for file in files:
        file_id = str(uuid.uuid4())
        ext = os.path.splitext(file.filename)[1]
        filename = f"{file_id}{ext}"
        path = os.path.join(UPLOAD_DIR, filename)
        
        try:
            content = await file.read()
            with open(path, "wb") as f:
                f.write(content)
            temp_paths.append(path)
            original_filenames.append(filename)
        except Exception as e:
            logger.error(f"Error saving file {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Could not save file: {file.filename}")

    async def event_generator():
        # Initialize LangGraph state
        state: AgentState = {
            "files_path": temp_paths,
            "instructions": instructions,
            "use_reranking": use_reranking,
            "search_queries": [],
            "context": [],
            "feedback": None,
            "annotated_files_path": []
        }

        try:
            # Send init event
            yield {
                "event": "status",
                "data": json.dumps({
                    "step": "init",
                    "message": "🚀 Initializing evaluation pipeline...",
                    "icon": "rocket",
                    "status": "running"
                })
            }

            # Accumulate graph state from the stream
            accumulated_state = dict(state)
            completed_steps = []

            async for output in class_x_evaluator.astream(state):
                for node_name, node_output in output.items():
                    label = STEP_LABELS.get(node_name, {
                        "message": f"Processing {node_name}...",
                        "icon": "cog"
                    })

                    # Mark previous step as completed
                    if completed_steps:
                        prev = completed_steps[-1]
                        prev_label = STEP_LABELS.get(prev, {"message": f"{prev} done"})
                        yield {
                            "event": "status",
                            "data": json.dumps({
                                "step": prev,
                                "message": f"✅ {prev_label['message'].split('...')[0]} — Done",
                                "icon": "check",
                                "status": "completed"
                            })
                        }

                    # Send current step as running
                    yield {
                        "event": "status",
                        "data": json.dumps({
                            "step": node_name,
                            "message": label["message"],
                            "icon": label["icon"],
                            "status": "running"
                        })
                    }

                    completed_steps.append(node_name)

                    # Merge node output into accumulated state
                    if isinstance(node_output, dict):
                        accumulated_state.update(node_output)

            # Mark last step as completed
            if completed_steps:
                last = completed_steps[-1]
                last_label = STEP_LABELS.get(last, {"message": f"{last} done"})
                yield {
                    "event": "status",
                    "data": json.dumps({
                        "step": last,
                        "message": f"✅ {last_label['message'].split('...')[0]} — Done",
                        "icon": "check",
                        "status": "completed"
                    })
                }

            # Prepare the final result
            annotated_files = [
                os.path.basename(p)
                for p in accumulated_state.get("annotated_files_path", [])
            ]
            feedback = accumulated_state.get("feedback", {})

            # Send final result payload
            yield {
                "event": "result",
                "data": json.dumps({
                    "feedback": feedback,
                    "annotated_files": annotated_files,
                    "original_files": original_filenames,
                    "static_url_prefix": "/static/",
                    "question_extracted": accumulated_state.get("question", ""),
                    "answer_extracted": accumulated_state.get("student_answer", ""),
                    "search_queries": accumulated_state.get("search_queries", []),
                    "context": accumulated_state.get("context", [])
                })
            }

        except Exception as e:
            logger.error(f"Graph execution error: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)})
            }

    return EventSourceResponse(event_generator())

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
