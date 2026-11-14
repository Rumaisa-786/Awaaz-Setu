create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  preferred_language text not null default 'en-IN',
  created_at timestamptz not null default now()
);

create table if not exists public.call_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  language_pair jsonb not null default '{}'::jsonb,
  summary jsonb,
  saved boolean not null default false
);

create table if not exists public.opt_in_transcripts (
  call_session_id uuid primary key references public.call_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  turns jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.call_sessions enable row level security;
alter table public.opt_in_transcripts enable row level security;

create policy "profiles_select_own" on public.profiles for select using (auth.uid() = id);
create policy "profiles_insert_own" on public.profiles for insert with check (auth.uid() = id);
create policy "profiles_update_own" on public.profiles for update using (auth.uid() = id) with check (auth.uid() = id);
create policy "calls_select_own" on public.call_sessions for select using (auth.uid() = user_id);
create policy "calls_insert_own" on public.call_sessions for insert with check (auth.uid() = user_id);
create policy "calls_update_own" on public.call_sessions for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "transcripts_select_own" on public.opt_in_transcripts for select using (
  auth.uid() = user_id and exists (select 1 from public.call_sessions c where c.id = call_session_id and c.user_id = auth.uid())
);
create policy "transcripts_insert_own" on public.opt_in_transcripts for insert with check (
  auth.uid() = user_id and exists (select 1 from public.call_sessions c where c.id = call_session_id and c.user_id = auth.uid())
);
create policy "transcripts_delete_own" on public.opt_in_transcripts for delete using (auth.uid() = user_id);
