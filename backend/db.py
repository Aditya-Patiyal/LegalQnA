from __future__ import annotations

from typing import Any

from supabase import Client, ClientOptions, create_client

from .config import SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


def get_service_client() -> Client:
    """Bypasses row-level security entirely. Only for scripts/index_law_kb.py —
    never call this from a request handler."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_public_client() -> Client:
    """Unauthenticated client for reading shared reference data (law_sections),
    which is public-read regardless of who's asking."""
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_user_client(access_token: str) -> Client:
    """A Supabase client scoped to one signed-in user.

    Every query made through this client is subject to the row-level security
    policies in supabase/schema.sql — a user can only ever see their own rows,
    enforced by Postgres itself, not by an `.eq("user_id", ...)` filter we might
    forget to add. This is the fix for the old app's "every visitor is the same
    guest user" bug: there is no shared client and no way to accidentally query
    across users.
    """
    return create_client(
        SUPABASE_URL,
        SUPABASE_ANON_KEY,
        options=ClientOptions(headers={"Authorization": f"Bearer {access_token}"}),
    )


def insert_document(db: Client, user_id: str, filename: str, storage_path: str, file_type: str) -> dict[str, Any]:
    result = db.table("documents").insert({
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path,
        "file_type": file_type,
        "upload_status": "processing",
    }).execute()
    return result.data[0]


def update_document_status(db: Client, document_id: int, **fields: Any) -> None:
    db.table("documents").update(fields).eq("id", document_id).execute()


def get_document(db: Client, document_id: int) -> dict[str, Any] | None:
    result = db.table("documents").select("*").eq("id", document_id).limit(1).execute()
    return result.data[0] if result.data else None


def list_documents(db: Client) -> list[dict[str, Any]]:
    result = db.table("documents").select("*").order("created_at", desc=True).execute()
    return result.data


def delete_document(db: Client, document_id: int) -> None:
    db.table("chat_history").delete().eq("document_id", document_id).execute()
    db.table("document_chunks").delete().eq("document_id", document_id).execute()
    db.table("documents").delete().eq("id", document_id).execute()


def insert_document_chunks(db: Client, document_id: int, user_id: str, chunks: list[dict[str, Any]]) -> None:
    if not chunks:
        return
    rows = [{**chunk, "document_id": document_id, "user_id": user_id} for chunk in chunks]
    for i in range(0, len(rows), 200):
        db.table("document_chunks").insert(rows[i:i + 200]).execute()


def get_all_chunks(db: Client, document_id: int) -> list[dict[str, Any]]:
    result = db.table("document_chunks").select("*").eq("document_id", document_id).execute()
    return result.data


def match_chunks(db: Client, document_id: int, user_id: str, query_embedding: list[float], limit: int = 8) -> list[dict[str, Any]]:
    result = db.rpc("match_document_chunks", {
        "query_embedding": query_embedding,
        "match_document_id": document_id,
        "match_user_id": user_id,
        "match_count": limit,
    }).execute()
    return result.data


def insert_chat_message(db: Client, user_id: str, document_id: int | None, question: str, answer: str, sources: list[Any]) -> None:
    db.table("chat_history").insert({
        "user_id": user_id,
        "document_id": document_id,
        "question": question,
        "answer": answer,
        "sources_json": sources,
    }).execute()


def get_chat_history(db: Client, document_id: int, limit: int = 3) -> list[dict[str, str]]:
    result = (
        db.table("chat_history")
        .select("question, answer")
        .eq("document_id", document_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    history: list[dict[str, str]] = []
    for row in reversed(result.data):
        history.append({"role": "user", "content": row["question"]})
        history.append({"role": "assistant", "content": row["answer"]})
    return history


def delete_chat_history(db: Client, document_id: int) -> None:
    db.table("chat_history").delete().eq("document_id", document_id).execute()


def insert_generated_document(db: Client, user_id: str, template_type: str, storage_path: str, input_json: dict[str, Any]) -> dict[str, Any]:
    result = db.table("generated_documents").insert({
        "user_id": user_id,
        "template_type": template_type,
        "storage_path": storage_path,
        "input_json": input_json,
    }).execute()
    return result.data[0]


def get_generated_document(db: Client, doc_id: int) -> dict[str, Any] | None:
    result = db.table("generated_documents").select("*").eq("id", doc_id).limit(1).execute()
    return result.data[0] if result.data else None


def list_generated_documents(db: Client) -> list[dict[str, Any]]:
    result = db.table("generated_documents").select("*").order("created_at", desc=True).execute()
    return result.data
