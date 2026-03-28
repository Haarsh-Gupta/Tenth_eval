from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
load_dotenv()


model = ChatGoogleGenerativeAI(model="gemini-3.1-pro-preview")

res = model.invoke("hello")

print(res.text)

