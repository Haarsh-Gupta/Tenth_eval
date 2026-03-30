from app.agent import ClassXEvaluationAgent
from logger import setup_logger
import json

def test_run():
    setup_logger()
    agent = ClassXEvaluationAgent()
    
    print("\n🚀 Starting test evaluation...")
    # Perform a dummy evaluation (will likely return 'No files' message)
    result = agent.full_evaluation(
        question="What were the causes of the French Revolution?",
        student_answer="The French Revolution was caused by social inequality, financial crisis, and enlightenment ideas."
    )
    
    print("\n✅ Evaluation results:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_run()