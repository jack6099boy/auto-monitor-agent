import os
from docling.document_converter import DocumentConverter
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI
import chromadb


class RAGSystem:
    def __init__(self, sop_dir="sop", persist_dir="./chroma_db"):
        self.sop_dir = sop_dir
        self.persist_dir = persist_dir
        self.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-large-zh-v1.5")
        self.db = chromadb.PersistentClient(path=persist_dir)
        self.chroma_collection = self.db.get_or_create_collection("sop_docs")
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        self.index = None
        self.llm = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            api_base="https://openrouter.ai/api/v1",
            model="gpt-4o-mini"
        )

    def load_documents(self):
        # Use Docling to convert documents
        converter = DocumentConverter()
        documents = []
        for file in os.listdir(self.sop_dir):
            if file.endswith(('.pdf', '.docx', '.txt', '.md')):  # Assuming these formats
                result = converter.convert(os.path.join(self.sop_dir, file))
                documents.append(result.document.export_to_markdown())
        # For LlamaIndex, we need Document objects
        from llama_index.core import Document
        llama_docs = [Document(text=doc) for doc in documents]
        return llama_docs

    def build_index(self):
        documents = self.load_documents()
        if documents:
            self.index = VectorStoreIndex.from_documents(
                documents,
                storage_context=self.storage_context,
                embed_model=self.embed_model
            )

    def query(self, query_str):
        if self.index:
            query_engine = self.index.as_query_engine(llm=self.llm)
            response = query_engine.query(query_str)
            return response
        else:
            return "Index not built yet."


if __name__ == "__main__":
    rag = RAGSystem()
    rag.build_index()
    # Example query
    result = rag.query("What is the SOP for handling errors?")
    print(result)