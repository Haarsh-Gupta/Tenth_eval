from pinecone import Pinecone
from .config import settings
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


# ==================== ABSTRACT BASE CLASSES ====================

class EmbeddingModel(ABC):
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        pass


class VectorStoreBase(ABC):
    @abstractmethod
    def similarity_search(self, query: str, k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[str]:
        """Search for similar documents."""
        pass

    @abstractmethod
    def similarity_search_by_vector(self, embedding: List[float], k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List[str]:
        """Search for similar documents by vector."""
        pass

    @abstractmethod
    def get_documents_by_id(self, ids: List[str]) -> List[str]:
        """Get documents by their IDs."""
        pass

    @abstractmethod
    def get_documents_by_id_list(self, id_list: List[str]) -> List[str]:
        """Get documents by a list of IDs."""
        pass


# ==================== VECTOR STORE IMPLEMENTATION ====================

class PineconeVectorStoreWrapper(VectorStoreBase):
    """Pinecone-backed vector store wrapper."""

    def __init__(self, index_name: str, embedding: EmbeddingModel, namespace: str = "default", text_key: str = "text", pinecone_api_key: str = None):
        api_key = pinecone_api_key or settings.pinecone_api_key
        self.namespace = namespace
        self.pc = Pinecone(api_key=api_key)

        try:
            if not self.pc.has_index(index_name):
                raise ValueError(f"Index '{index_name}' does not exist in Pinecone.")
        except Exception as e:
            raise ValueError(f"Error checking for index '{index_name}': {e}")

        self.index = self.pc.Index(index_name)
        # self.reranker = reranker
        self.store = PineconeVectorStore(index=self.index, embedding=embedding, namespace=namespace, text_key=text_key)

    def similarity_search(self, query: str, k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List:
        return self.store.similarity_search(query, k=k, filter=filter)

    def similarity_search_by_vector(self, embedding: List[float], k: int = 5, filter: Optional[Dict[str, Any]] = None) -> List:
        return self.store.similarity_search_by_vector(embedding, k=k, filter=filter)

    def get_documents_by_id(self, id: str) -> Dict[str, Any]:
        """Fetch a single vector + metadata from Pinecone by ID."""
        result = self.index.fetch(ids=[id], namespace=self.namespace)
        vectors = result.vectors  
        if id in vectors:
            vec = vectors[id]
            return {"id": id, "metadata": vec.metadata if vec.metadata else {}}
        return {}

    def get_documents_by_id_list(self, id_list: List[str]) -> List[Dict[str, Any]]:
        """Fetch multiple vectors + metadata from Pinecone by IDs."""
        result = self.index.fetch(ids=id_list, namespace=self.namespace)
        vectors = result.vectors 
        return [
            {"id": vid, "metadata": vectors[vid].metadata if vectors[vid].metadata else {}}
            for vid in id_list if vid in vectors
        ]

    def search_and_rerank(self , query: str , k : int = 5 , fetch_k : int = 20 , filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # if not self.reranker:
        #     raise ValueError("Reranker was not provided during initialization of this store.")
        
        # Fallback: just return similarity search results directly
        return self.store.similarity_search(query , k=k , filter=filter)

        # inital_docs = self.store.similarity_search(query , k=fetch_k , filter=filter)
        # if not inital_docs:
        #     return []
        # docs_for_rerank = []
        # for doc in inital_docs:
        #     docs_for_rerank.append({
        #         "content" : doc.page_content,
        #         "metadata" : doc.metadata,
        #         "original_doc" : doc
        #     })
        # reranked_docs = self.reranker.rerank(
        #     query = query, 
        #     documents = docs_for_rerank ,
        #     content_key = "content" ,
        #     top_k=k
        # )
        # return [d["original_doc"] for d in reranked_docs]


# ==================== INITIALIZE EMBEDDINGS ====================

openai_api_key = settings.openai_api_key
pinecone_api_key = settings.pinecone_api_key
rag_index_name = settings.rag_index_name

openai_embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_api_key)


# ==================== INITIALIZE PINECONE INDEXES & STORES ====================


RAG_VECTOR_STORE = PineconeVectorStoreWrapper(
    index_name=rag_index_name,
    embedding=openai_embeddings,
    namespace="default"
)

logger.info("✅ Vector stores initialized successfully")


# from pprint import pprint
# query = "India's economic growth rate for the first quarter (April-June) of the current financial year has quickened to a five-quarter high of 7.8%, driven by strong performances in manufacturing, construction, and services sectors. This data release has prompted government reassurances regarding economic momentum and has spurred discussions on US tariffs and domestic spending" 
# pprint(NEWS_VECTOR_STORE.similarity_search(query = query , k = 1))
# pprint(NEWS_VECTOR_STORE.get_documents_by_id(id = "68b282bd1b337cbcf29e3e6f"))
# pprint(RAG_VECTOR_STORE.get_documents_by_id(id = "0002618e-39cd-40dc-a378-feb2e4b8f04d"))



# query = "french revolution" 
# pprint(RAG_VECTOR_STORE.search_and_rerank(query = query , k = 2 , fetch_k=10))
# query = "what is shanti bill" 
# pprint(NEWS_VECTOR_STORE.search_and_rerank(query = query , k = 2 , fetch_k=10))

