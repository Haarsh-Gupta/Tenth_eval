from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

# ==================== 1. OUTPUT SCHEMAS ====================

class OCRSchema(BaseModel):
    """Schema for extracting question and answer from provided images."""
    question: str = Field(description="The question written or printed in the document.")
    answer: str = Field(description="The student's handwritten or typed answer corresponding to the question.")

class QueryGenerationSchema(BaseModel):
    """Schema for generating a search query from the question."""
    queries: List[str] = Field(description="1-3 optimized search queries to retrieve relevant historical text from the Class tenth History book.")

class VisualAnnotation(BaseModel):
    """Schema for marking errors on the answer sheet image."""
    text: str = Field(description="The specific text snippet that is incorrect.")
    issue_type: Literal["spelling", "grammar", "content_error", "missing_info", "wrong_sentence"] = Field(description="The nature of the issue.")
    coordinates: List[int] = Field(description="The normalized [ymin, xmin, ymax, xmax] coordinates (0-1000) for the location of this error on the image.")
    marking_style: Literal["circle", "cross", "underline", "tick", "highlight", "suggestion_box"] = Field(description="Which visual mark to use.")
    suggestion: Optional[str] = Field(description="Corrected text or proposed improvement for this specific error.")

class EvaluationSchema(BaseModel):
    """Schema for Evaluation Node."""
    marks_awarded: int = Field(description="The marks awarded to the student.")
    total_marks: int = Field(description="Total possible marks for this question (default assume 5 if not mentioned).")
    spelling_grammar_issues: List[str] = Field(description="List of spelling or grammar mistakes found, if any.")
    content_feedback: str = Field(description="Detailed feedback comparing student answer with the actual reference material.")
    overall_performance: Literal["poor", "average", "good", "excellent"] = Field(description="Overall rating.")
    visual_annotations: Optional[List[VisualAnnotation]] = Field(description="List of visual markings to draw on the original image for transparency.")
    suggested_rewrite: Optional[str] = Field(description="A complete improved version of the student's answer.")

# ==================== 2. PARSERS ====================

ocr_parser = JsonOutputParser(pydantic_object=OCRSchema)
query_parser = JsonOutputParser(pydantic_object=QueryGenerationSchema)
evaluation_parser = JsonOutputParser(pydantic_object=EvaluationSchema)


# ==================== 3. PROMPT TEMPLATES ====================

# --- OCR PROMPT ---
# Note: For Vision/OCR, we often pass the prompt text as part of the HumanMessage content.
# We'll just define the text template here.
OCR_PROMPT_TEXT = """You are an expert OCR and text extractor. 

CRITICAL: Extract the EXACT text as written, verbatim. DO NOT correct spellings, DO NOT fix grammar, and DO NOT autocomplete partial words. If a word is misspelled (e.g., "histry" instead of "history"), you MUST extract it exactly as it appears in the image. Your goal is absolute fidelity to the source image, including all errors.

I have provided an image or document containing a student's answer sheet. 
Your task is to clearly separate and extract the Question asked and the Answer written by the student.

Make sure to capture all the text accurately, paying attention to the context to separate the question from the answer.


Output MUST be a valid JSON matching this schema:
{format_instructions}

"""

instructions_prompt = """
1. Examine if the student's answer correctly points out the facts present in the reference text.
2. Identify and highlight every single spelling or grammatical error.
3. Identify sentences that are irrelevant or don't logically answer the question - mark these as "wrong_sentence".
4. For every error found, provide a "suggestion" field with the correct or improved version of that snippet.
5. Award marks fairly out of 10 based on Class X CBSE standards.
6. Give actionable feedback mentioning what is missing or incorrect.
"""

OCR_PROMPT = PromptTemplate(
    template=OCR_PROMPT_TEXT,
    input_variables=[],
    partial_variables={"format_instructions": ocr_parser.get_format_instructions()}
)


# --- QUERY GENERATOR PROMPT ---
QUERY_GENERATOR_PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""You are an expert history teacher for Class X.
    
Based on the following question asked in the exam, formulate 1 to 3 search queries to find the relevant material in the "History class tenth" textbook using a semantic vector search.

QUESTION: "{question}"

Output MUST be a valid JSON matching this schema:
{format_instructions}
""",
    partial_variables={"format_instructions": query_parser.get_format_instructions()}
)


# --- EVALUATION PROMPT ---
EVALUATION_PROMPT = PromptTemplate(
    input_variables=["question", "student_answer", "context", "instructions"],
    template="""You are a strict yet constructive Class X History examiner.

Evaluate the student's answer based on the provided reference text from the textbook. 
Also, identify the exact locations of errors (spelling, grammar, or logic) on the student's answer sheet image to provide visual marks.

Assume total_marks = 5

### SPECIFIC INSTRUCTIONS FOR VISUAL ANNOTATIONS:
1. **Wrong Sentences**: Mark red highlights over sentences that are factually incorrect or irrelevant to the question.
2. **Spelling Mistakes**: Circle every misspelled word in red.
3. **Suggestions**: For each error, provide a concise correction or a "suggested line" which would have been better.

### QUESTION ASKED:
{question}

### STUDENT'S ANSWER:
{student_answer}

### REFERENCE TEXT (From Textbook):
{context}

### INSTRUCTIONS:
{instructions}

### COORDINATES GUIDELINE:
Determine the bounding box [ymin, xmin, ymax, xmax] for any identified errors on the student's answer image using a 0-1000 normalized coordinate system where 0 is the top/left and 1000 is the bottom/right.

Output MUST be a valid JSON matching this schema:
{format_instructions}
""",
    partial_variables={"format_instructions": evaluation_parser.get_format_instructions()}
)

# ==================== 4. HELPER FUNCTIONS ====================

def format_context(context_items: List[dict]) -> str:
    """Formatter to convert retrieved dictionary documents to string context."""
    if not context_items:
        return "No relevant textbook context found."
    
    formatted_text = ""
    for idx, item in enumerate(context_items, 1):
        content = item.get("content", "").strip()
        book_name = item.get("book_name", "History class tenth")
        formatted_text += f"--- Source {idx} ({book_name}) ---\n{content}\n\n"
        
    return formatted_text
