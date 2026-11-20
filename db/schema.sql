-- Run once. docker-compose mounts this into the init dir. Dim 1024 = bge-m3. Change both if you change model.
create extension if not exists vector;

create table if not exists textbooks (
  id serial primary key,
  title text not null,
  curriculum_id text not null default 'nctb',
  textbook_medium text not null default 'bangla_version' check (textbook_medium in ('bangla_version', 'english_version', 'unknown')),
  edition_year int default 2024,
  class_level int not null check (class_level between 1 and 12),
  subject text not null,
  source_url text,
  source_license text default 'CC BY 4.0',
  sha256 text,
  parser_version text,
  source text,  -- e.g. 'NCTB-PrimaryText (Mendeley, CC BY 4.0)'
  created_at timestamptz default now(),
  unique (curriculum_id, textbook_medium, class_level, subject)
);
create index if not exists textbooks_identity_idx on textbooks (curriculum_id, textbook_medium, class_level, subject);

create table if not exists chunks (
  id bigserial primary key,
  textbook_id int not null references textbooks(id) on delete cascade,
  chunk_ref text unique,   -- dataset chunk_id (prefixed with en- for English Version)
  chapter_no int,
  chapter text,            -- chapter title
  page_start int,          -- chapter start page from chapters_config when available
  page_end int,            -- chapter end page from chapters_config when available
  text text not null,
  contextual_text text,
  embedding vector(1024),
  tokens int,
  fts tsvector generated always as (to_tsvector('simple', coalesce(contextual_text,'') || ' ' || text)) stored
);
create index if not exists chunks_emb_idx on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_fts_idx on chunks using gin (fts);
create index if not exists chunks_book_idx on chunks (textbook_id);
create index if not exists chunks_book_chapter_idx on chunks (textbook_id, chapter_no);

create table if not exists queries (
  id bigserial primary key,
  session_id text,
  curriculum_id text default 'nctb',
  textbook_medium text default 'bangla_version',
  answer_language text default 'bn',
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

create table if not exists learning_events (
  id bigserial primary key,
  event_key text unique,
  session_id text not null,
  curriculum_id text not null default 'nctb',
  textbook_medium text not null default 'bangla_version',
  class_level int not null,
  subject text not null,
  chapter text not null,
  learning_objective text,
  event_type text not null default 'practice_attempt',
  question_id text,
  selected_option text,
  is_correct boolean not null,
  likely_misconception text,
  created_at timestamptz default now()
);
create index if not exists learning_events_session_idx on learning_events (session_id);
create index if not exists learning_events_topic_idx on learning_events (curriculum_id, textbook_medium, class_level, subject, chapter);

create table if not exists session_mastery (
  session_id text not null,
  curriculum_id text not null default 'nctb',
  textbook_medium text not null default 'bangla_version',
  class_level int not null,
  subject text not null,
  chapter text not null,
  mastery real not null default 0.5,
  attempts int not null default 0,
  correct int not null default 0,
  last_misconception text,
  updated_at timestamptz default now(),
  primary key (session_id, curriculum_id, textbook_medium, class_level, subject, chapter)
);
