-- Book-Worm backend schema for Supabase (Postgres).
-- Run this once in the Supabase SQL editor (Project > SQL Editor > New query).
-- The FastAPI backend talks to Postgres exclusively through PostgREST using the
-- service_role key, which bypasses RLS -- RLS below is defense-in-depth so the
-- anon/publishable key can never read/write these tables directly.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- users (the app's own auth + profile record -- NOT Supabase Auth)
-- ---------------------------------------------------------------------------
create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  display_name text not null,
  name_hidden boolean not null default false,
  phone text,
  avatar_id text,
  avatar_url text,
  gender text check (gender in ('male', 'female', 'other', 'prefer_not_to_say')),
  dob date,
  reading_preferences text[] not null default '{}',
  points integer not null default 0,
  books_completed integer not null default 0,
  world_stage integer not null default 0,
  is_premium boolean not null default false,
  premium_until timestamptz,
  daily_goal_pages integer not null default 10,
  yearly_goal_books integer not null default 12,
  reminder_time text not null default '20:00',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_users_books_completed on public.users (books_completed desc, points desc, updated_at desc);

-- v1.1 monetization/growth columns (safe to re-run on an existing users table).
alter table public.users add column if not exists premium_until timestamptz;
alter table public.users add column if not exists daily_goal_pages integer not null default 10;
alter table public.users add column if not exists yearly_goal_books integer not null default 12;
alter table public.users add column if not exists reminder_time text not null default '20:00';

-- ---------------------------------------------------------------------------
-- processed_webhook_events -- idempotency ledger for RevenueCat webhooks
-- (dedupe by RevenueCat's event.id so a redelivered event is a no-op).
-- ---------------------------------------------------------------------------
create table if not exists public.processed_webhook_events (
  id text primary key,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- refresh_tokens -- rotation + reuse detection
-- ---------------------------------------------------------------------------
create table if not exists public.refresh_tokens (
  id uuid primary key,                          -- jti of the refresh JWT
  user_id uuid not null references public.users (id) on delete cascade,
  family_id uuid not null,
  revoked boolean not null default false,
  replaced_by uuid,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index if not exists idx_refresh_tokens_user on public.refresh_tokens (user_id);
create index if not exists idx_refresh_tokens_family on public.refresh_tokens (family_id);

-- ---------------------------------------------------------------------------
-- password_reset_tokens
-- ---------------------------------------------------------------------------
create table if not exists public.password_reset_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  token_hash text not null unique,
  used boolean not null default false,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index if not exists idx_password_reset_user on public.password_reset_tokens (user_id);

-- ---------------------------------------------------------------------------
-- books
-- ---------------------------------------------------------------------------
create table if not exists public.books (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  title text not null,
  author text not null,
  genre text check (genre in (
    'fiction', 'nonfiction', 'sci-fi', 'fantasy', 'mystery', 'thriller',
    'romance', 'poetry', 'biography', 'history', 'self-help', 'other'
  )),
  cover_url text,
  total_pages integer,
  current_page integer not null default 0,
  status text not null default 'currently_reading' check (status in ('currently_reading', 'already_read')),
  started_at timestamptz,
  finished_at timestamptz,
  rating integer check (rating between 1 and 5),
  summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_books_user on public.books (user_id, status);
create index if not exists idx_books_user_finished on public.books (user_id, finished_at desc) where status = 'already_read';

-- ---------------------------------------------------------------------------
-- reading_sessions -- one row per "log progress" call
-- ---------------------------------------------------------------------------
create table if not exists public.reading_sessions (
  id uuid primary key default gen_random_uuid(),
  book_id uuid not null references public.books (id) on delete cascade,
  user_id uuid not null references public.users (id) on delete cascade,
  pages_read integer not null check (pages_read > 0),
  minutes integer,
  date timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists idx_sessions_book on public.reading_sessions (book_id);
create index if not exists idx_sessions_user_date on public.reading_sessions (user_id, date desc);

-- ---------------------------------------------------------------------------
-- bookmarks -- caller (user_id) bookmarks another reader's finished book
-- ---------------------------------------------------------------------------
create table if not exists public.bookmarks (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  book_id uuid not null references public.books (id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, book_id)
);

create index if not exists idx_bookmarks_user on public.bookmarks (user_id);

-- ---------------------------------------------------------------------------
-- device_tokens -- FCM push registration
-- ---------------------------------------------------------------------------
create table if not exists public.device_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  token text not null unique,
  platform text check (platform in ('android', 'ios', 'web')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_device_tokens_user on public.device_tokens (user_id);

-- ---------------------------------------------------------------------------
-- notifications -- persisted history of pushes sent/queued for a user
-- ---------------------------------------------------------------------------
create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  title text not null,
  body text not null,
  image_url text,
  data jsonb not null default '{}'::jsonb,
  is_read boolean not null default false,
  received_at timestamptz not null default now()
);

create index if not exists idx_notifications_user on public.notifications (user_id, received_at desc);
create index if not exists idx_notifications_user_unread on public.notifications (user_id) where is_read = false;

-- ---------------------------------------------------------------------------
-- quotes -- admin-curated rotating quotes for the home carousel (public read)
-- ---------------------------------------------------------------------------
create table if not exists public.quotes (
  id text primary key default gen_random_uuid()::text,
  text text not null,
  author text,
  category text check (category in ('Motivation', 'Romance', 'Sci-Fi')),
  is_active boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_quotes_active on public.quotes (is_active, category);

-- ---------------------------------------------------------------------------
-- summaries -- admin-curated / reader-contributed book summaries (public read)
-- ---------------------------------------------------------------------------
create table if not exists public.summaries (
  id text primary key default gen_random_uuid()::text,
  title text not null,
  author text,
  cover text,                       -- optional emoji fallback
  description text not null,
  contributor text not null default 'Editor',
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_summaries_active on public.summaries (is_active, created_at desc);

-- ---------------------------------------------------------------------------
-- RLS: enabled with no permissive policies -- only service_role (used by the
-- backend) bypasses RLS. anon/authenticated (PostgREST direct access) get
-- nothing, since all access must go through the FastAPI backend.
-- ---------------------------------------------------------------------------
alter table public.users enable row level security;
alter table public.refresh_tokens enable row level security;
alter table public.password_reset_tokens enable row level security;
alter table public.books enable row level security;
alter table public.reading_sessions enable row level security;
alter table public.bookmarks enable row level security;
alter table public.device_tokens enable row level security;
alter table public.notifications enable row level security;
alter table public.processed_webhook_events enable row level security;
alter table public.quotes enable row level security;
alter table public.summaries enable row level security;

-- ---------------------------------------------------------------------------
-- Leaderboard views -- weekly finish counts + a users+weekly join used by the
-- leaderboard endpoint so `weekly_books` is always available regardless of
-- the requested period.
-- ---------------------------------------------------------------------------
create or replace view public.weekly_book_counts as
select user_id, count(*) as weekly_books
from public.books
where status = 'already_read' and finished_at >= now() - interval '7 days'
group by user_id;

create or replace view public.leaderboard_view as
select
  u.id as user_id,
  u.display_name,
  u.name_hidden,
  u.avatar_id,
  u.avatar_url,
  u.books_completed,
  u.points,
  u.world_stage,
  u.updated_at,
  coalesce(w.weekly_books, 0) as weekly_books
from public.users u
left join public.weekly_book_counts w on w.user_id = u.id;

-- ---------------------------------------------------------------------------
-- World-stage thresholds (single source of truth, mirrors api-doc.md)
-- ---------------------------------------------------------------------------
create or replace function public.fn_world_stage(p_books_completed integer)
returns integer
language sql
immutable
as $$
  select case
    when p_books_completed >= 100 then 5
    when p_books_completed >= 50 then 4
    when p_books_completed >= 30 then 3
    when p_books_completed >= 15 then 2
    when p_books_completed >= 5 then 1
    else 0
  end;
$$;

-- ---------------------------------------------------------------------------
-- fn_finish_book -- atomic finish + points + world-stage recompute
-- ---------------------------------------------------------------------------
create or replace function public.fn_finish_book(
  p_book_id uuid,
  p_user_id uuid,
  p_summary text,
  p_rating integer,
  p_finished_at timestamptz
)
returns jsonb
language plpgsql
as $$
declare
  v_book public.books%rowtype;
  v_prev_stage integer;
  v_points integer;
  v_books_completed integer;
  v_new_stage integer;
  v_finished_at timestamptz := coalesce(p_finished_at, now());
begin
  select * into v_book from public.books where id = p_book_id for update;

  if not found then
    raise exception 'BOOK_NOT_FOUND';
  end if;

  if v_book.user_id <> p_user_id then
    raise exception 'BOOK_FORBIDDEN';
  end if;

  if v_book.status = 'already_read' then
    raise exception 'BOOK_ALREADY_FINISHED';
  end if;

  update public.books
  set status = 'already_read',
      finished_at = v_finished_at,
      rating = p_rating,
      summary = p_summary,
      current_page = coalesce(v_book.total_pages, v_book.current_page),
      updated_at = now()
  where id = p_book_id
  returning * into v_book;

  select world_stage into v_prev_stage from public.users where id = p_user_id for update;

  update public.users
  set points = points + 10,
      books_completed = books_completed + 1,
      updated_at = now()
  where id = p_user_id
  returning points, books_completed into v_points, v_books_completed;

  v_new_stage := public.fn_world_stage(v_books_completed);

  update public.users set world_stage = v_new_stage where id = p_user_id;

  return jsonb_build_object(
    'book', jsonb_build_object(
      'id', v_book.id,
      'title', v_book.title,
      'status', v_book.status,
      'finished_at', v_book.finished_at,
      'rating', v_book.rating,
      'summary', v_book.summary,
      'current_page', v_book.current_page,
      'total_pages', v_book.total_pages
    ),
    'progression', jsonb_build_object(
      'books_completed', v_books_completed,
      'points_awarded', 10,
      'points_total', v_points,
      'previous_world_stage', v_prev_stage,
      'world_stage', v_new_stage,
      'stage_changed', v_new_stage <> v_prev_stage
    )
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- fn_log_progress -- atomic page increment + session insert
-- ---------------------------------------------------------------------------
create or replace function public.fn_log_progress(
  p_book_id uuid,
  p_user_id uuid,
  p_pages_read integer,
  p_minutes integer,
  p_date timestamptz
)
returns jsonb
language plpgsql
as $$
declare
  v_book public.books%rowtype;
  v_session_id uuid;
  v_date timestamptz := coalesce(p_date, now());
  v_new_page integer;
begin
  select * into v_book from public.books where id = p_book_id for update;

  if not found then
    raise exception 'BOOK_NOT_FOUND';
  end if;

  if v_book.user_id <> p_user_id then
    raise exception 'BOOK_FORBIDDEN';
  end if;

  if v_book.status = 'already_read' then
    raise exception 'BOOK_ALREADY_FINISHED';
  end if;

  v_new_page := v_book.current_page + p_pages_read;
  if v_book.total_pages is not null and v_new_page > v_book.total_pages then
    v_new_page := v_book.total_pages;
  end if;

  update public.books
  set current_page = v_new_page, updated_at = now()
  where id = p_book_id;

  insert into public.reading_sessions (book_id, user_id, pages_read, minutes, date)
  values (p_book_id, p_user_id, p_pages_read, p_minutes, v_date)
  returning id into v_session_id;

  return jsonb_build_object(
    'session', jsonb_build_object(
      'id', v_session_id,
      'book_id', p_book_id,
      'pages_read', p_pages_read,
      'minutes', p_minutes,
      'date', v_date
    ),
    'book', jsonb_build_object(
      'id', v_book.id,
      'current_page', v_new_page,
      'total_pages', v_book.total_pages,
      'status', v_book.status
    )
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- Seed content (idempotent) -- starter quotes + summaries so the home carousel
-- and Summary tab are populated on a fresh database. Safe to re-run.
-- ---------------------------------------------------------------------------
insert into public.quotes (id, text, author, category, sort_order) values
  ('q_001', 'A reader lives a thousand lives before he dies.', 'George R.R. Martin', 'Motivation', 1),
  ('q_002', 'We loved with a love that was more than love.', 'Edgar Allan Poe', 'Romance', 2),
  ('q_003', 'The universe is under no obligation to make sense to you.', 'Neil deGrasse Tyson', 'Sci-Fi', 3),
  ('q_004', 'Today a reader, tomorrow a leader.', 'Margaret Fuller', 'Motivation', 4)
on conflict (id) do nothing;

insert into public.summaries (id, title, author, cover, description, contributor) values
  ('s_001', 'Atomic Habits', 'James Clear', '⚛️', 'A practical framework for improving every day through tiny 1% changes that compound into remarkable results.', 'Editor'),
  ('s_002', 'Deep Work', 'Cal Newport', '🧠', 'Rules for focused success in a distracted world — how to cultivate the ability to concentrate without distraction.', 'Editor')
on conflict (id) do nothing;
