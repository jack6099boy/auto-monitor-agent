import os
import json
import hashlib
from docling.document_converter import DocumentConverter
from llama_index.core import VectorStoreIndex, StorageContext, Document
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI
import chromadb


class RAGSystem:
    def __init__(self, sop_dir="sop", persist_dir="./chroma_db", lab_id="default"):
        self.sop_dir = sop_dir
        self.persist_dir = persist_dir
        self.lab_id = lab_id
        self.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-large-zh-v1.5")
        self.db = chromadb.PersistentClient(path=persist_dir)

        # Use lab_id as collection name for multi-lab support
        collection_name = f"sop_docs_{lab_id}" if lab_id != "default" else "sop_docs"
        self.chroma_collection = self.db.get_or_create_collection(collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        self.index = None
        self.llm = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            api_base="https://openrouter.ai/api/v1",
            model="gpt-4o-mini"
        )
        self._cache_file = os.path.join(persist_dir, f".doc_cache_{lab_id}.json")

    def _get_document_files(self) -> list:
        """Get list of document files in SOP directory"""
        if not os.path.exists(self.sop_dir):
            return []

        files = []
        for file in os.listdir(self.sop_dir):
            if file.endswith(('.pdf', '.docx', '.txt', '.md', '.pptx')):
                files.append(os.path.join(self.sop_dir, file))
        return sorted(files)

    def _file_hash(self, filepath: str) -> str:
        """Calculate file hash"""
        try:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def _get_current_hashes(self, doc_files: list) -> dict:
        """Get current file hashes"""
        return {f: self._file_hash(f) for f in doc_files}

    def _documents_unchanged(self, doc_files: list) -> bool:
        """Check if documents have changed (via hash comparison)"""
        if not os.path.exists(self._cache_file):
            return False

        try:
            with open(self._cache_file, 'r') as f:
                cached_hashes = json.load(f)
        except (json.JSONDecodeError, IOError):
            return False

        current_hashes = self._get_current_hashes(doc_files)
        return cached_hashes == current_hashes

    def _save_document_cache(self, doc_files: list):
        """Save document hashes to cache file"""
        os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
        current_hashes = self._get_current_hashes(doc_files)
        with open(self._cache_file, 'w') as f:
            json.dump(current_hashes, f)

    def _index_exists(self) -> bool:
        """Check if index already exists"""
        try:
            count = self.chroma_collection.count()
            return count > 0
        except Exception:
            return False

    def load_documents(self) -> list:
        """Load and convert documents from SOP directory"""
        if not os.path.exists(self.sop_dir):
            print(f"SOP directory not found: {self.sop_dir}")
            return []

        converter = DocumentConverter()
        documents = []

        for file in os.listdir(self.sop_dir):
            if file.endswith(('.pdf', '.docx', '.txt', '.md', '.pptx')):
                file_path = os.path.join(self.sop_dir, file)
                try:
                    result = converter.convert(file_path)
                    doc_text = result.document.export_to_markdown()
                    # Add metadata for better retrieval
                    documents.append(Document(
                        text=doc_text,
                        metadata={
                            "source": file,
                            "lab_id": self.lab_id
                        }
                    ))
                except Exception as e:
                    print(f"Error converting {file}: {e}")

        return documents

    def build_index(self):
        """Build or load RAG index (with smart caching)"""
        doc_files = self._get_document_files()

        # Check if existing index can be reused
        if self._index_exists():
            if self._documents_unchanged(doc_files):
                print(f"Loading existing index from {self.persist_dir} ({self.chroma_collection.count()} vectors)")
                try:
                    self.index = VectorStoreIndex.from_vector_store(
                        vector_store=self.vector_store,
                        embed_model=self.embed_model
                    )
                    print("Index loaded successfully from existing store.")
                    return
                except Exception as e:
                    print(f"Failed to load existing index: {e}. Rebuilding...")
            else:
                print("Documents changed, rebuilding index...")

        # Build new index
        self._rebuild_index(doc_files)

    def _rebuild_index(self, doc_files: list):
        """Force rebuild the index"""
        print("Building new index...")
        documents = self.load_documents()

        if documents:
            self.index = VectorStoreIndex.from_documents(
                documents,
                storage_context=self.storage_context,
                embed_model=self.embed_model
            )
            # Save document cache
            self._save_document_cache(doc_files)
            print(f"Index built successfully with {len(documents)} documents.")
        else:
            print("No documents found to index.")

    def rebuild_index(self):
        """Force rebuild index (when SOP files are updated)"""
        print("Force rebuilding index...")

        # Clear existing collection
        collection_name = self.chroma_collection.name
        self.db.delete_collection(collection_name)
        self.chroma_collection = self.db.get_or_create_collection(collection_name)
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        # Rebuild
        doc_files = self._get_document_files()
        self._rebuild_index(doc_files)

    def query(self, query_str: str):
        """Query the RAG system"""
        if self.index:
            query_engine = self.index.as_query_engine(llm=self.llm)
            response = query_engine.query(query_str)
            return response
        else:
            return "Index not built yet."

    def add_document(self, file_path: str):
        """Add a single document to the index (incremental update)"""
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"

        try:
            converter = DocumentConverter()
            result = converter.convert(file_path)
            doc_text = result.document.export_to_markdown()

            doc = Document(
                text=doc_text,
                metadata={
                    "source": os.path.basename(file_path),
                    "lab_id": self.lab_id
                }
            )

            if self.index:
                self.index.insert(doc)
                print(f"Document added: {file_path}")
                # Update cache
                doc_files = self._get_document_files()
                self._save_document_cache(doc_files)
                return "Document added successfully."
            else:
                return "Index not built yet. Call build_index() first."

        except Exception as e:
            return f"Error adding document: {e}"


if __name__ == "__main__":
    rag = RAGSystem()
    rag.build_index()
    # Example query
    result = rag.query("What is the SOP for handling errors?")
    print(result)
