from __future__ import annotations

from supabase import Client

DOCUMENTS_BUCKET = "documents"
GENERATED_BUCKET = "generated"


def upload_document_file(db: Client, user_id: str, storage_name: str, content: bytes, content_type: str) -> str:
    path = f"{user_id}/{storage_name}"
    db.storage.from_(DOCUMENTS_BUCKET).upload(
        path, content, {"content-type": content_type, "upsert": "false"}
    )
    return path


def download_document_file(db: Client, storage_path: str) -> bytes:
    return db.storage.from_(DOCUMENTS_BUCKET).download(storage_path)


def delete_document_file(db: Client, storage_path: str) -> None:
    db.storage.from_(DOCUMENTS_BUCKET).remove([storage_path])


def upload_generated_file(db: Client, user_id: str, storage_name: str, content: bytes) -> str:
    path = f"{user_id}/{storage_name}"
    db.storage.from_(GENERATED_BUCKET).upload(
        path, content, {"content-type": "application/pdf", "upsert": "false"}
    )
    return path


def signed_download_url(db: Client, bucket: str, storage_path: str, expires_in: int = 300) -> str:
    result = db.storage.from_(bucket).create_signed_url(storage_path, expires_in)
    return result["signedURL"] if "signedURL" in result else result["signed_url"]
