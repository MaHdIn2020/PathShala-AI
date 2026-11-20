-- Migration 002: Postgres-backed Concept Rescue learning events & session mastery
-- Non-destructive & idempotent: adds new tables without altering textbooks/chunks.

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
