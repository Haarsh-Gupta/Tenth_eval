import os
from pydantic_settings import BaseSettings

# Determine the absolute path to the .env file at the project root
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(ROOT_DIR, ".env")

from pydantic import Field

class Settings(BaseSettings):
    google_api_key: str = Field(alias="GOOGLE_API_KEY")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    pinecone_api_key: str = Field(alias="PINECONE_API_KEY")
    rag_index_name: str = Field(alias="RAG_INDEX_NAME")

    model_config = {
        "env_file": ENV_PATH,
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()
