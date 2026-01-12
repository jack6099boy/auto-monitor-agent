"""
Multi-Lab API Server for AIOps Agent

A simple FastAPI server that supports multiple laboratories.
Each lab has its own RAG system and agent instance.

Usage:
    uvicorn agent.api_server:app --host 0.0.0.0 --port 8000
"""

import os
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from .agent import build_agent, get_rag_system, list_active_labs, reset_agent
from .config import LabConfig

app = FastAPI(
    title="AIOps Agent API",
    description="Multi-lab intelligent testing operations system",
    version="2.0.0"
)

# Allowed lab IDs (configure as needed)
ALLOWED_LABS = os.getenv("ALLOWED_LABS", "lab1,lab2,lab3,lab4,lab5").split(",")


# ============ Request/Response Models ============

class QueryRequest(BaseModel):
    query: str
    lab_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "query": "How to handle connection timeout error?",
                "lab_id": "lab1"
            }
        }


class QueryResponse(BaseModel):
    lab_id: str
    query: str
    response: str


class AnalyzeRequest(BaseModel):
    log_content: str
    lab_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "log_content": "ERROR: Connection timeout at 2024-01-01 10:00:00",
                "lab_id": "lab1"
            }
        }


class AnalyzeResponse(BaseModel):
    lab_id: str
    analysis: str


class LabStatus(BaseModel):
    lab_id: str
    documents_indexed: int
    status: str


# ============ Helper Functions ============

def validate_lab_id(lab_id: str):
    """Validate lab ID"""
    if lab_id not in ALLOWED_LABS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid lab_id: {lab_id}. Allowed: {ALLOWED_LABS}"
        )


def get_lab_config(lab_id: str) -> LabConfig:
    """Get configuration for a specific lab"""
    return LabConfig(
        lab_id=lab_id,
        lab_name=f"Laboratory {lab_id}",
        sop_dir=f"sop/{lab_id}",
        log_dir=f"logs/{lab_id}",
        hints_dir=f"hints/{lab_id}",
        chroma_db_dir="./chroma_db",  # Shared, isolated by collection
        drain3_state_file=f"drain3_state_{lab_id}.bin"
    )


def get_lab_rag(lab_id: str):
    """Get or create RAG system for a specific lab with correct config"""
    config = get_lab_config(lab_id)
    return get_rag_system(lab_id=lab_id, config=config)


# ============ API Endpoints ============

@app.get("/")
async def root():
    """API root"""
    return {
        "service": "AIOps Agent API",
        "version": "2.0.0",
        "labs": ALLOWED_LABS
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "allowed_labs": ALLOWED_LABS,
        "active_labs": list_active_labs()
    }


@app.get("/labs", response_model=List[str])
async def get_labs():
    """List all allowed lab IDs"""
    return ALLOWED_LABS


@app.get("/labs/{lab_id}/status", response_model=LabStatus)
async def get_lab_status(lab_id: str):
    """Get status for a specific lab"""
    validate_lab_id(lab_id)

    try:
        rag = get_lab_rag(lab_id)
        doc_count = rag.chroma_collection.count()
        return LabStatus(
            lab_id=lab_id,
            documents_indexed=doc_count,
            status="active"
        )
    except Exception as e:
        return LabStatus(
            lab_id=lab_id,
            documents_indexed=0,
            status=f"error: {str(e)}"
        )


@app.post("/query", response_model=QueryResponse)
async def query_sop(request: QueryRequest):
    """
    Query SOP documents for a specific lab.

    This endpoint queries the RAG system to find relevant SOP documentation.
    """
    validate_lab_id(request.lab_id)

    try:
        rag = get_lab_rag(request.lab_id)
        response = rag.query(request.query)
        return QueryResponse(
            lab_id=request.lab_id,
            query=request.query,
            response=str(response) if response else "No relevant information found."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_log(request: AnalyzeRequest):
    """
    Analyze log content using the Agent.

    The agent will use Drain3 for pattern analysis and RAG for SOP lookup.
    """
    validate_lab_id(request.lab_id)

    try:
        agent = build_agent(request.lab_id)

        prompt = f"""Analyze the following log content and provide:
1. Whether this is an anomaly
2. Possible causes
3. Recommended actions based on SOP

Log content:
{request.log_content}
"""
        result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        response = result["messages"][-1].content

        return AnalyzeResponse(
            lab_id=request.lab_id,
            analysis=response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=AnalyzeResponse)
async def chat_with_agent(request: QueryRequest):
    """
    General chat endpoint with the Agent.

    Use this for free-form questions to the agent.
    """
    validate_lab_id(request.lab_id)

    try:
        agent = build_agent(request.lab_id)
        result = agent.invoke({"messages": [HumanMessage(content=request.query)]})
        response = result["messages"][-1].content

        return AnalyzeResponse(
            lab_id=request.lab_id,
            analysis=response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/labs/{lab_id}/rebuild-index")
async def rebuild_lab_index(lab_id: str):
    """Force rebuild RAG index for a specific lab"""
    validate_lab_id(lab_id)

    try:
        # Reset and rebuild
        reset_agent(lab_id)
        rag = get_rag_system(lab_id)
        rag.rebuild_index()

        return {
            "lab_id": lab_id,
            "status": "success",
            "documents_indexed": rag.chroma_collection.count()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Startup Event ============

@app.on_event("startup")
async def startup_event():
    """Initialize on startup (optional: pre-warm labs)"""
    print(f"AIOps Agent API starting...")
    print(f"Allowed labs: {ALLOWED_LABS}")

    # Optional: Pre-initialize specific labs
    # for lab_id in ALLOWED_LABS[:1]:  # Only first lab
    #     get_rag_system(lab_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
