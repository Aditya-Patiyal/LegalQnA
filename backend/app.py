from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import db, storage
from .ai_generator import smart_generate
from .auth import CurrentUser, get_current_user
from .clause_service import extract_clause
from .config import CORS_ORIGINS, MAX_UPLOAD_BYTES
from .document_parser import chunk_text_structured, extract_text
from .embeddings import add_structured_chunks
from .generator import build_pdf
from .indian_law_kb import lookup_section, search_law_by_topic, semantic_search_laws
from .rag_pipeline import answer_law_question, answer_question, stream_answer_question, stream_law_question
from .risk_engine import analyze_document

app = FastAPI(title="Legal AI Platform", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def get_db(user: CurrentUser = Depends(get_current_user)):
    return db.get_user_client(user.access_token), user


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


class ChatRequest(BaseModel):
    document_id: int
    question: str


class ClauseRequest(BaseModel):
    document_id: int
    clause_type: str


class RiskRequest(BaseModel):
    document_id: int


class GenerateRequest(BaseModel):
    template_type: str
    name: str
    address: str
    issue_description: str
    date: str
    force_generate: bool = False


class LawSearchRequest(BaseModel):
    topic: str
    limit: int = 5


class LawQuestionRequest(BaseModel):
    question: str


def _process_document(dbc, user_id: str, document_id: int, file_bytes: bytes, suffix: str, filename: str) -> None:
    import tempfile
    import os as _os

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        try:
            extracted_text = extract_text(tmp_path)
        except Exception:
            db.update_document_status(dbc, document_id, upload_status="error")
            return

        try:
            structured_chunks = chunk_text_structured(tmp_path)
            chunk_count = add_structured_chunks(dbc, document_id, user_id, structured_chunks)
        except Exception:
            chunk_count = 0

        db.update_document_status(
            dbc, document_id,
            extracted_text=extracted_text, chunk_count=chunk_count, upload_status="ready",
        )
    finally:
        _os.unlink(tmp_path)


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...), ctx=Depends(get_db)) -> dict[str, Any]:
    dbc, user = ctx
    suffix = ("." + file.filename.rsplit(".", 1)[-1].lower()) if file.filename and "." in file.filename else ""
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large — max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")

    storage_name = f"{uuid4().hex}{suffix}"
    storage_path = storage.upload_document_file(dbc, user.id, storage_name, content, file.content_type or "application/octet-stream")

    original_filename = file.filename or storage_name
    document = db.insert_document(dbc, user.id, original_filename, storage_path, suffix.replace(".", ""))

    _process_document(dbc, user.id, document["id"], content, suffix, original_filename)
    document = db.get_document(dbc, document["id"])
    return {"document": document}


@app.get("/api/documents")
def list_documents(ctx=Depends(get_db)) -> dict[str, Any]:
    dbc, _ = ctx
    return {"documents": db.list_documents(dbc)}


@app.get("/api/documents/{document_id}")
def get_document(document_id: int, ctx=Depends(get_db)) -> dict[str, Any]:
    dbc, _ = ctx
    document = db.get_document(dbc, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"document": document}


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: int, ctx=Depends(get_db)) -> dict[str, str]:
    dbc, _ = ctx
    document = db.get_document(dbc, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    storage.delete_document_file(dbc, document["storage_path"])
    db.delete_document(dbc, document_id)
    return {"message": "Document deleted successfully"}


@app.delete("/api/chat-history/{document_id}")
def delete_chat_history(document_id: int, ctx=Depends(get_db)) -> dict[str, str]:
    dbc, _ = ctx
    db.delete_chat_history(dbc, document_id)
    return {"message": "Chat history cleared"}


@app.get("/api/chat-history/{document_id}")
def chat_history(document_id: int, ctx=Depends(get_db)) -> dict[str, Any]:
    dbc, user = ctx
    return {"messages": db.get_chat_history(dbc, document_id, limit=50)}


@app.post("/api/chat")
def chat(payload: ChatRequest, ctx=Depends(get_db)) -> dict[str, Any]:
    dbc, user = ctx
    document = db.get_document(dbc, payload.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    history = db.get_chat_history(dbc, payload.document_id)
    result = answer_question(dbc, user.id, payload.document_id, payload.question, history=history)
    db.insert_chat_message(dbc, user.id, payload.document_id, payload.question, result["answer"], result["sources"])
    return result


@app.post("/api/chat/stream")
def chat_stream(payload: ChatRequest, ctx=Depends(get_db)) -> StreamingResponse:
    dbc, user = ctx
    document = db.get_document(dbc, payload.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    history = db.get_chat_history(dbc, payload.document_id)

    def event_generator():
        full_answer: list[str] = []
        final_event: dict[str, Any] = {}
        for event in stream_answer_question(dbc, user.id, payload.document_id, payload.question, history=history):
            if event["type"] == "token":
                full_answer.append(event["content"])
            else:
                final_event = event
            yield f"data: {json.dumps(event)}\n\n"
        db.insert_chat_message(dbc, user.id, payload.document_id, payload.question, "".join(full_answer), final_event.get("sources", []))

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/clauses/extract")
def clauses(payload: ClauseRequest, ctx=Depends(get_db)) -> dict[str, Any]:
    dbc, user = ctx
    document = db.get_document(dbc, payload.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return extract_clause(dbc, user.id, payload.document_id, payload.clause_type)


@app.post("/api/risk/analyze")
def risk(payload: RiskRequest, ctx=Depends(get_db)) -> dict[str, Any]:
    dbc, _ = ctx
    document = db.get_document(dbc, payload.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return analyze_document(dbc, payload.document_id)


@app.post("/api/generate-document")
def generate_document(payload: GenerateRequest, ctx=Depends(get_db)) -> dict[str, Any]:
    dbc, user = ctx
    result = smart_generate(
        template_type=payload.template_type, name=payload.name, address=payload.address,
        date=payload.date, issue_description=payload.issue_description, force_generate=payload.force_generate,
    )

    if result["status"] == "mismatch":
        c = result["classification"]
        return {"status": "mismatch", "message": c.get("message_to_user", "Your description doesn't match the selected document type."), "suggested_type": c.get("suggested_type"), "mismatch_reason": c.get("mismatch_reason"), "detected_intent": c.get("detected_intent")}
    if result["status"] == "needs_info":
        c = result["classification"]
        return {"status": "needs_info", "message": c.get("message_to_user", "More information is needed to generate this document."), "missing_info": c.get("missing_info", [])}
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Failed to generate document"))

    content = result["content"]
    pdf_bytes = build_pdf(content)
    storage_name = f"{payload.template_type}-{uuid4().hex}.pdf"
    storage_path = storage.upload_generated_file(dbc, user.id, storage_name, pdf_bytes)
    record = db.insert_generated_document(dbc, user.id, payload.template_type, storage_path, payload.model_dump())
    return {"status": "success", "file_id": record["id"], "preview": content, "download_url": f"/api/download/{record['id']}"}


@app.get("/api/generated-documents")
def generated_documents(ctx=Depends(get_db)) -> dict[str, Any]:
    dbc, _ = ctx
    return {"generated_documents": db.list_generated_documents(dbc)}


@app.get("/api/download/{file_id}")
def download(file_id: int, ctx=Depends(get_db)) -> dict[str, str]:
    dbc, _ = ctx
    record = db.get_generated_document(dbc, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    url = storage.signed_download_url(dbc, storage.GENERATED_BUCKET, record["storage_path"])
    return {"url": url}


@app.post("/api/law/lookup")
def law_lookup(payload: LawQuestionRequest) -> dict[str, Any]:
    result = lookup_section(payload.question)
    if not result:
        return {"found": False, "message": f"Could not find section matching '{payload.question}'. Try formats like 'IPC 420', 'Section 302 IPC', or 'BNS 318'."}
    return result


@app.post("/api/law/search")
def law_search(payload: LawSearchRequest) -> dict[str, Any]:
    topic_results = search_law_by_topic(payload.topic, limit=payload.limit)
    semantic_results = semantic_search_laws(payload.topic, limit=payload.limit)
    return {"topic_matches": topic_results, "semantic_matches": semantic_results}


@app.post("/api/law/ask")
def law_ask(payload: LawQuestionRequest) -> dict[str, Any]:
    return answer_law_question(payload.question)


@app.post("/api/law/ask/stream")
def law_ask_stream(payload: LawQuestionRequest) -> StreamingResponse:
    def event_generator():
        for event in stream_law_question(payload.question):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
