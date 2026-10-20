-- Run this once in Supabase: SQL Editor -> New query -> paste -> Run
create table if not exists public.scores (
  id bigint generated always as identity primary key,
  name text not null check (char_length(name) between 1 and 12),
  score int not null check (score between 0 and 100000),
  mode text not null check (mode in ('classic', 'arcade', 'zen', 'sudden')),
  created_at timestamptz not null default now()
);

create index if not exists scores_mode_score_idx on public.scores (mode, score desc);

alter table public.scores enable row level security;

-- everyone can read the leaderboard and add scores; nobody can edit or delete
create policy "anyone can read scores" on public.scores for select using (true);
create policy "anyone can add scores" on public.scores for insert with check (true);
