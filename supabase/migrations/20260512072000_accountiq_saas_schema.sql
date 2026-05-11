-- AccountIQ SaaS data model.
-- Public tables are exposed through Supabase APIs, so RLS is enabled on all of them.

create extension if not exists pgcrypto;

create type public.lead_status as enum (
  'new',
  'upload_started',
  'preview_viewed',
  'qualified',
  'contacted',
  'paid',
  'closed',
  'lost'
);

create type public.upload_status as enum (
  'created',
  'uploaded',
  'extracting',
  'preview_ready',
  'failed',
  'paid',
  'archived'
);

create type public.payment_status as enum (
  'pending',
  'paid',
  'failed',
  'refunded',
  'cancelled'
);

create table public.leads (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  name text,
  company text,
  phone text,
  source text,
  campaign text,
  status public.lead_status not null default 'new',
  utm_source text,
  utm_medium text,
  utm_campaign text,
  utm_term text,
  utm_content text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.customers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique references auth.users(id) on delete cascade,
  lead_id uuid references public.leads(id) on delete set null,
  stripe_customer_id text unique,
  email text not null,
  name text,
  company text,
  is_admin boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.upload_sessions (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid references public.leads(id) on delete set null,
  customer_id uuid references public.customers(id) on delete set null,
  session_token uuid not null default gen_random_uuid(),
  status public.upload_status not null default 'created',
  source_url text,
  source text,
  campaign text,
  utm_source text,
  utm_medium text,
  utm_campaign text,
  utm_term text,
  utm_content text,
  expires_at timestamptz not null default now() + interval '14 days',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  upload_session_id uuid not null references public.upload_sessions(id) on delete cascade,
  lead_id uuid references public.leads(id) on delete set null,
  customer_id uuid references public.customers(id) on delete set null,
  storage_bucket text not null default 'accountiq-uploads',
  storage_path text not null,
  original_filename text not null,
  content_type text,
  file_size_bytes bigint,
  extraction_status public.upload_status not null default 'uploaded',
  extraction_job_id text,
  extraction_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (storage_bucket, storage_path)
);

create table public.reports (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null unique references public.documents(id) on delete cascade,
  upload_session_id uuid not null references public.upload_sessions(id) on delete cascade,
  lead_id uuid references public.leads(id) on delete set null,
  customer_id uuid references public.customers(id) on delete set null,
  preview_json jsonb not null default '{}'::jsonb,
  full_json jsonb not null default '{}'::jsonb,
  narrative text,
  confidence numeric(4, 3) check (confidence is null or (confidence >= 0 and confidence <= 1)),
  locked_sections jsonb not null default '[]'::jsonb,
  is_unlocked boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.payments (
  id uuid primary key default gen_random_uuid(),
  report_id uuid references public.reports(id) on delete set null,
  customer_id uuid references public.customers(id) on delete set null,
  lead_id uuid references public.leads(id) on delete set null,
  stripe_checkout_session_id text unique,
  stripe_payment_intent_id text unique,
  stripe_customer_id text,
  status public.payment_status not null default 'pending',
  amount_total integer,
  currency text not null default 'nzd',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index leads_email_idx on public.leads (lower(email));
create index leads_status_created_at_idx on public.leads (status, created_at desc);
create index upload_sessions_token_idx on public.upload_sessions (session_token);
create index upload_sessions_lead_idx on public.upload_sessions (lead_id);
create index documents_upload_session_idx on public.documents (upload_session_id);
create index reports_upload_session_idx on public.reports (upload_session_id);
create index payments_customer_idx on public.payments (customer_id);

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger leads_touch_updated_at
before update on public.leads
for each row execute function public.touch_updated_at();

create trigger customers_touch_updated_at
before update on public.customers
for each row execute function public.touch_updated_at();

create trigger upload_sessions_touch_updated_at
before update on public.upload_sessions
for each row execute function public.touch_updated_at();

create trigger documents_touch_updated_at
before update on public.documents
for each row execute function public.touch_updated_at();

create trigger reports_touch_updated_at
before update on public.reports
for each row execute function public.touch_updated_at();

create trigger payments_touch_updated_at
before update on public.payments
for each row execute function public.touch_updated_at();

create or replace function public.is_admin()
returns boolean
language sql
stable
as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', '') = 'admin'
$$;

create or replace function public.current_upload_session_token()
returns text
language sql
stable
as $$
  select nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'upload_session_token'
$$;

alter table public.leads enable row level security;
alter table public.customers enable row level security;
alter table public.upload_sessions enable row level security;
alter table public.documents enable row level security;
alter table public.reports enable row level security;
alter table public.payments enable row level security;

create policy "Admins can manage leads"
on public.leads
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

create policy "Customers can read their own profile"
on public.customers
for select
to authenticated
using (user_id = auth.uid());

create policy "Customers can update their own profile"
on public.customers
for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

create policy "Admins can manage customers"
on public.customers
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

create policy "Session token can read upload sessions"
on public.upload_sessions
for select
to anon, authenticated
using (session_token::text = public.current_upload_session_token());

create policy "Customers can read their upload sessions"
on public.upload_sessions
for select
to authenticated
using (customer_id in (select id from public.customers where user_id = auth.uid()));

create policy "Admins can manage upload sessions"
on public.upload_sessions
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

create policy "Session token can read documents"
on public.documents
for select
to anon, authenticated
using (
  upload_session_id in (
    select id from public.upload_sessions
    where session_token::text = public.current_upload_session_token()
  )
);

create policy "Customers can read their documents"
on public.documents
for select
to authenticated
using (customer_id in (select id from public.customers where user_id = auth.uid()));

create policy "Admins can manage documents"
on public.documents
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

create policy "Session token can read preview reports"
on public.reports
for select
to anon, authenticated
using (
  upload_session_id in (
    select id from public.upload_sessions
    where session_token::text = public.current_upload_session_token()
  )
);

create policy "Customers can read unlocked reports"
on public.reports
for select
to authenticated
using (
  is_unlocked
  and customer_id in (select id from public.customers where user_id = auth.uid())
);

create policy "Admins can manage reports"
on public.reports
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

create policy "Customers can read their payments"
on public.payments
for select
to authenticated
using (customer_id in (select id from public.customers where user_id = auth.uid()));

create policy "Admins can manage payments"
on public.payments
for all
to authenticated
using (public.is_admin())
with check (public.is_admin());

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'accountiq-uploads',
  'accountiq-uploads',
  false,
  15728640,
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel.sheet.macroEnabled.12'
  ]
)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create policy "Session scoped upload insert"
on storage.objects
for insert
to anon, authenticated
with check (
  bucket_id = 'accountiq-uploads'
  and (storage.foldername(name))[1] = public.current_upload_session_token()
);

create policy "Session scoped upload read"
on storage.objects
for select
to anon, authenticated
using (
  bucket_id = 'accountiq-uploads'
  and (storage.foldername(name))[1] = public.current_upload_session_token()
);

create policy "Customer upload read"
on storage.objects
for select
to authenticated
using (
  bucket_id = 'accountiq-uploads'
  and exists (
    select 1
    from public.documents d
    join public.customers c on c.id = d.customer_id
    where c.user_id = auth.uid()
      and d.storage_bucket = bucket_id
      and d.storage_path = name
  )
);

create policy "Admins can manage upload objects"
on storage.objects
for all
to authenticated
using (
  bucket_id = 'accountiq-uploads'
  and public.is_admin()
)
with check (
  bucket_id = 'accountiq-uploads'
  and public.is_admin()
);
