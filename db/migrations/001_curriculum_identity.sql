-- Migration 001: Separate curriculum identity, textbook medium, and page ranges
-- Non-destructive & idempotent: preserves all existing textbooks, chunks, queries, and feedback.

alter table textbooks add column if not exists curriculum_id text not null default 'nctb';
alter table textbooks add column if not exists textbook_medium text not null default 'bangla_version';
alter table textbooks add column if not exists edition_year int default 2024;
alter table textbooks add column if not exists source_license text default 'CC BY 4.0';

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'textbooks_medium_check'
  ) then
    alter table textbooks
      add constraint textbooks_medium_check
      check (textbook_medium in ('bangla_version', 'english_version', 'unknown'));
  end if;
end $$;

alter table textbooks drop constraint if exists textbooks_class_level_subject_key;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'textbooks_curriculum_medium_class_subject_key'
  ) then
    alter table textbooks
      add constraint textbooks_curriculum_medium_class_subject_key
      unique (curriculum_id, textbook_medium, class_level, subject);
  end if;
end $$;

alter table queries add column if not exists curriculum_id text default 'nctb';
alter table queries add column if not exists textbook_medium text default 'bangla_version';
alter table queries add column if not exists answer_language text default 'bn';

create index if not exists textbooks_identity_idx
  on textbooks (curriculum_id, textbook_medium, class_level, subject);
create index if not exists chunks_book_chapter_idx
  on chunks (textbook_id, chapter_no);
