-- Legal AI Platform v2 — Supabase schema
-- Run this once in the Supabase SQL editor (or via `supabase db push`).
-- Auth is handled entirely by Supabase Auth (auth.users) — there is no
-- custom users/sessions table here, unlike the old SQLite version.

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- documents
-- ---------------------------------------------------------------------------
create table if not exists documents (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  storage_path text not null,              -- path inside the `documents` storage bucket
  file_type text not null,
  upload_status text not null default 'processing',
  extracted_text text not null default '',
  chunk_count integer not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists documents_user_id_idx on documents(user_id);

alter table documents enable row level security;

create policy "documents_select_own" on documents
  for select using (auth.uid() = user_id);
create policy "documents_insert_own" on documents
  for insert with check (auth.uid() = user_id);
create policy "documents_update_own" on documents
  for update using (auth.uid() = user_id);
create policy "documents_delete_own" on documents
  for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- document_chunks — replaces ChromaDB
-- ---------------------------------------------------------------------------
-- HuggingFace sentence-transformers/all-MiniLM-L6-v2 produces 384-dim vectors.
-- Change the dimension below if you switch embedding models.
create table if not exists document_chunks (
  id bigint generated always as identity primary key,
  document_id bigint not null references documents(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  chunk_index integer not null,
  text text not null,
  page_number integer,
  section_heading text,
  clause_number text,
  char_start integer,
  char_end integer,
  embedding vector(384),
  created_at timestamptz not null default now()
);

create index if not exists document_chunks_document_id_idx on document_chunks(document_id);
create index if not exists document_chunks_user_id_idx on document_chunks(user_id);
-- Approximate nearest-neighbour index for cosine similarity search.
create index if not exists document_chunks_embedding_idx
  on document_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

alter table document_chunks enable row level security;

create policy "chunks_select_own" on document_chunks
  for select using (auth.uid() = user_id);
create policy "chunks_insert_own" on document_chunks
  for insert with check (auth.uid() = user_id);
create policy "chunks_delete_own" on document_chunks
  for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- chat_history
-- ---------------------------------------------------------------------------
create table if not exists chat_history (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  document_id bigint references documents(id) on delete cascade,
  question text not null,
  answer text not null,
  sources_json jsonb not null default '[]',
  created_at timestamptz not null default now()
);

create index if not exists chat_history_user_document_idx on chat_history(user_id, document_id);

alter table chat_history enable row level security;

create policy "chat_history_select_own" on chat_history
  for select using (auth.uid() = user_id);
create policy "chat_history_insert_own" on chat_history
  for insert with check (auth.uid() = user_id);
create policy "chat_history_delete_own" on chat_history
  for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- generated_documents
-- ---------------------------------------------------------------------------
create table if not exists generated_documents (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  template_type text not null,
  storage_path text not null,              -- path inside the `generated` storage bucket
  input_json jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists generated_documents_user_id_idx on generated_documents(user_id);

alter table generated_documents enable row level security;

create policy "generated_select_own" on generated_documents
  for select using (auth.uid() = user_id);
create policy "generated_insert_own" on generated_documents
  for insert with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Storage buckets (run once — Supabase Storage, not a SQL table)
-- ---------------------------------------------------------------------------
-- Create these two buckets in the Supabase dashboard (Storage tab), both
-- PRIVATE (not public), then apply the policies below:
--   1. "documents"  — uploaded PDFs/DOCX
--   2. "generated"  — AI-generated PDFs
--
-- insert into storage.buckets (id, name, public) values ('documents', 'documents', false);
-- insert into storage.buckets (id, name, public) values ('generated', 'generated', false);

create policy "documents_bucket_own_folder"
  on storage.objects for all
  using (bucket_id = 'documents' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'documents' and (storage.foldername(name))[1] = auth.uid()::text);

create policy "generated_bucket_own_folder"
  on storage.objects for all
  using (bucket_id = 'generated' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'generated' and (storage.foldername(name))[1] = auth.uid()::text);

-- ---------------------------------------------------------------------------
-- law_sections — shared reference data (Indian law knowledge base), not
-- per-user. Indexed once via scripts/index_law_kb.py using the service-role
-- key; read by every user through the anon key, hence the public-read policy.
-- ---------------------------------------------------------------------------
create table if not exists law_sections (
  id text primary key,
  act text not null,
  act_short text not null,
  section text not null,
  title text not null,
  description text not null,
  category text,
  punishment text,
  embedding vector(384)
);

create index if not exists law_sections_embedding_idx
  on law_sections using ivfflat (embedding vector_cosine_ops) with (lists = 50);

alter table law_sections enable row level security;

create policy "law_sections_public_read" on law_sections
  for select using (true);

create or replace function match_law_sections(
  query_embedding vector(384),
  match_count int default 5
)
returns table (
  id text, act text, act_short text, section text, title text,
  description text, category text, punishment text, similarity float
)
language sql stable
as $$
  select
    law_sections.id, law_sections.act, law_sections.act_short, law_sections.section,
    law_sections.title, law_sections.description, law_sections.category, law_sections.punishment,
    1 - (law_sections.embedding <=> query_embedding) as similarity
  from law_sections
  order by law_sections.embedding <=> query_embedding
  limit match_count;
$$;

-- ---------------------------------------------------------------------------
-- pgvector similarity search helper (called from Python via .rpc())
-- ---------------------------------------------------------------------------
create or replace function match_document_chunks(
  query_embedding vector(384),
  match_document_id bigint,
  match_user_id uuid,
  match_count int default 8
)
returns table (
  id bigint,
  text text,
  page_number integer,
  section_heading text,
  clause_number text,
  similarity float
)
language sql stable
as $$
  select
    document_chunks.id,
    document_chunks.text,
    document_chunks.page_number,
    document_chunks.section_heading,
    document_chunks.clause_number,
    1 - (document_chunks.embedding <=> query_embedding) as similarity
  from document_chunks
  where document_chunks.document_id = match_document_id
    and document_chunks.user_id = match_user_id
  order by document_chunks.embedding <=> query_embedding
  limit match_count;
$$;
