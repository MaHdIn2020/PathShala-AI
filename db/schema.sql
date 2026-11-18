-- Run once. docker-compose mounts this into the init dir. Dim 1024 = bge-m3. Change both if you change model.
create extension if not exists vector;

create table if not exists textbooks (
  id serial primary key,
  title text not null,
  class_level int not null check (class_level between 1 and 12),
  subject text not null,
  source_url text,
  sha256 text,
  parser_version text,
  source text,  -- e.g. 'NCTB-PrimaryText (Mendeley, CC BY 4.0)'
  created_at timestamptz default now(),
  unique (class_level, subject)
);

create table if not exists chunks (
  id bigserial primary key,
  textbook_id int not null references textbooks(id) on delete cascade,
  chunk_ref text unique,   -- dataset chunk_id: <class>-<subject>-<chapter_no>-<chunk_index>
  chapter_no int,
  chapter text,            -- chapter title
  page_start int,          -- NULL for the Mendeley dataset (it has no page numbers)
  page_end int,
  text text not null,
  contextual_text text,
  embedding vector(1024),
  tokens int,
  fts tsvector generated always as (to_tsvector('simple', coalesce(contextual_text,'') || ' ' || text)) stored
);
create index if not exists chunks_emb_idx on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_fts_idx on chunks using gin (fts);
create index if not exists chunks_book_idx on chunks (textbook_id);

create table if not exists queries (
  id bigserial primary key,
  session_id text,
  class_level int,
  subject text,
  question text,
  topic text,
  top_score real,
  refused boolean,
  reason text,
  latency_ms int,
  cost_usd real,
  created_at timestamptz default now()
);

create table if not exists feedback (
  id bigserial primary key,
  query_id bigint references queries(id) on delete cascade,
  helpful boolean not null,
  comment text,
  created_at timestamptz default now()
);

create table if not exists eval_runs (
  id bigserial primary key,
  label text,
  metrics jsonb not null,
  created_at timestamptz default now()
);
