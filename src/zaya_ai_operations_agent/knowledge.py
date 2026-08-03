from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .llm import LLMProviderFactory
from .memory import MemoryStore
from .orchestrator import AgentManager
from .scheduler import Scheduler
from .tasks import get_task
from .workflows import WorkflowManager
from .workspaces import UserManager, WorkspaceManager


@dataclass(slots=True)
class DocumentChunk:
    id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class KnowledgeDocument:
    id: str
    title: str
    content: str
    file_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class EmbeddingInterface:
    """Interface for embedding generation."""

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class SimpleEmbedding(EmbeddingInterface):
    """Deterministic lightweight embedding implementation for testing."""

    def embed(self, text: str) -> list[float]:
        tokens = re.findall(r"\w+", text.lower())
        vector = [0.0] * 8
        for index, token in enumerate(tokens[:8]):
            vector[index % 8] += float(len(token))
        return vector


class VectorStore:
    """Abstraction for vector storage so a different backend can be plugged in later."""

    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    def upsert(self, item: dict[str, Any]) -> None:
        self._items.append(item)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        return self._items[:top_k]

    def delete(self, document_id: str) -> None:
        self._items = [item for item in self._items if item.get("document_id") != document_id]


class KnowledgeManager:
    """Modular knowledge base manager with ingestion, chunking, metadata, and search."""

    def __init__(self, memory_store: Optional[MemoryStore] = None, embedding: Optional[EmbeddingInterface] = None, vector_store: Optional[VectorStore] = None, scheduler: Optional[Scheduler] = None, agent_manager: Optional[AgentManager] = None, workflow_manager: Optional[WorkflowManager] = None, llm_provider: Optional[Any] = None) -> None:
        self.memory_store = memory_store
        self.embedding = embedding or SimpleEmbedding()
        self.llm_provider = llm_provider or LLMProviderFactory.create()
        self.user_manager = UserManager(memory_store=memory_store)
        self.workspace_manager = WorkspaceManager(memory_store=memory_store)
        self.vector_store = vector_store or VectorStore()
        self.scheduler = scheduler or Scheduler()
        self.agent_manager = agent_manager
        self.workflow_manager = workflow_manager
        self.documents: dict[str, KnowledgeDocument] = {}

    def _get_memory(self) -> MemoryStore:
        if self.memory_store is None:
            self.memory_store = MemoryStore(Path("~/.zaya_ai_operations_agent/knowledge.json").expanduser())
        return self.memory_store

    def _load_documents(self) -> dict[str, KnowledgeDocument]:
        memory = self._get_memory()
        stored_documents = memory.get("knowledge_documents", [])
        if not self.documents:
            self.documents = {doc["id"]: KnowledgeDocument(**doc) for doc in stored_documents}
        return self.documents

    def ingest_document(self, path: str | Path, title: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> KnowledgeDocument:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        content = self._read_content(path)
        document = KnowledgeDocument(
            id=path.stem.lower().replace(" ", "-") + f"-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            title=title or path.stem,
            content=content,
            file_type=path.suffix.lower().lstrip("."),
            metadata=metadata or {},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self.documents[document.id] = document
        self._persist_document(document)
        self._chunk_and_index(document)
        return document

    def _persist_document(self, document: KnowledgeDocument) -> None:
        memory = self._get_memory()
        stored_documents = memory.get("knowledge_documents", [])
        stored_documents = [entry for entry in stored_documents if entry.get("id") != document.id]
        stored_documents.append(asdict(document))
        memory.set("knowledge_documents", stored_documents)

    def _chunk_and_index(self, document: KnowledgeDocument, chunk_size: int = 300) -> None:
        chunks = self._chunk_text(document.content, chunk_size=chunk_size)
        for index, chunk_text in enumerate(chunks):
            chunk = DocumentChunk(
                id=f"{document.id}-chunk-{index}",
                document_id=document.id,
                text=chunk_text,
                metadata={"title": document.title, "file_type": document.file_type, "created_at": document.created_at},
            )
            vector = self.embedding.embed(chunk_text)
            self.vector_store.upsert({"id": chunk.id, "document_id": document.id, "text": chunk_text, "embedding": vector, "metadata": chunk.metadata})

    def _chunk_text(self, content: str, chunk_size: int = 300) -> list[str]:
        cleaned = re.sub(r"\s+", " ", content).strip()
        if not cleaned:
            return []
        words = cleaned.split()
        chunks = []
        for index in range(0, len(words), chunk_size):
            chunks.append(" ".join(words[index:index + chunk_size]))
        return chunks

    def _read_content(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".md":
            return path.read_text(encoding="utf-8")
        if suffix == ".txt":
            return path.read_text(encoding="utf-8")
        if suffix == ".pdf":
            return self._read_pdf(path)
        return path.read_text(encoding="utf-8")

    def _read_pdf(self, path: Path) -> str:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        self._load_documents()
        query_vector = self.embedding.embed(query)
        hits = self.vector_store.search(query_vector, top_k=top_k)
        return [
            {
                "document_id": hit.get("document_id"),
                "text": hit.get("text"),
                "metadata": hit.get("metadata", {}),
            }
            for hit in hits
        ]

    def list_documents(self) -> list[dict[str, Any]]:
        self._load_documents()
        return [
            {
                "id": document.id,
                "title": document.title,
                "file_type": document.file_type,
                "metadata": document.metadata,
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            }
            for document in sorted(self.documents.values(), key=lambda item: item.created_at)
        ]

    def delete_document(self, document_id: str) -> None:
        self.documents.pop(document_id, None)
        self.vector_store.delete(document_id)
        memory = self._get_memory()
        stored_documents = memory.get("knowledge_documents", [])
        memory.set("knowledge_documents", [entry for entry in stored_documents if entry.get("id") != document_id])
