create extension if not exists pgcrypto;

create table if not exists public.indicator_definitions (
  id text primary key,
  label text not null,
  description text not null default '',
  unit text not null,
  aliases jsonb not null default '[]'::jsonb,
  reference_ids jsonb not null default '[]'::jsonb,
  format text not null default 'integer_pt_br',
  precision integer not null default 0,
  category text not null default 'Geral',
  icon text not null default 'circle',
  allowed_operations jsonb not null default '["direct_value"]'::jsonb,
  semantic_status text not null default 'pendente',
  definition_version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.indicator_definitions
  add column if not exists reference_ids jsonb not null default '[]'::jsonb;

create table if not exists public.datasets (
  id text primary key,
  name text not null unique,
  description text not null default '',
  owner text not null default '',
  public_source text not null default '',
  active_version_id text,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.dataset_versions (
  id text primary key,
  dataset_id text not null references public.datasets(id) on delete cascade,
  sequence integer not null,
  checksum text not null,
  file_name text not null,
  storage_path text not null,
  schema jsonb not null default '{}'::jsonb,
  mapping jsonb not null default '{}'::jsonb,
  period text not null default '',
  public_source text not null default '',
  source_updated_at text not null default '',
  status text not null default 'pending',
  validation_errors jsonb not null default '[]'::jsonb,
  uploaded_by uuid references auth.users(id),
  uploaded_at timestamptz not null default now(),
  activated_at timestamptz,
  unique (dataset_id, sequence),
  unique (dataset_id, checksum, period, public_source, source_updated_at)
);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'datasets_active_version_fk') then
    alter table public.datasets
      add constraint datasets_active_version_fk
      foreign key (active_version_id) references public.dataset_versions(id)
      deferrable initially deferred;
  end if;
end $$;

create table if not exists public.base_images (
  id text primary key,
  name text not null unique,
  description text not null default '',
  kind text not null default 'production',
  active_version_id text,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (kind in ('production', 'reference'))
);

create table if not exists public.base_image_versions (
  id text primary key,
  base_image_id text not null references public.base_images(id) on delete cascade,
  sequence integer not null,
  checksum text not null,
  file_name text not null,
  storage_path text not null,
  width integer not null,
  height integer not null,
  format text not null default '',
  review_status text not null default 'pending',
  status text not null default 'pending',
  validation_errors jsonb not null default '[]'::jsonb,
  uploaded_by uuid references auth.users(id),
  uploaded_at timestamptz not null default now(),
  unique (base_image_id, sequence),
  unique (base_image_id, checksum, review_status)
);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'base_images_active_version_fk') then
    alter table public.base_images
      add constraint base_images_active_version_fk
      foreign key (active_version_id) references public.base_image_versions(id)
      deferrable initially deferred;
  end if;
end $$;

create table if not exists public.infographics (
  id text primary key,
  name text not null,
  mode text not null default 'imagem_base',
  base_image_id text references public.base_images(id),
  base_image_version_id text references public.base_image_versions(id),
  latest_revision_id text,
  owner text not null default '',
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.infographic_revisions (
  id text primary key,
  infographic_id text not null references public.infographics(id) on delete cascade,
  revision integer not null,
  layout_version integer not null default 1,
  base_image_version_id text references public.base_image_versions(id),
  data_versions jsonb not null default '[]'::jsonb,
  config jsonb not null default '{}'::jsonb,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  unique (infographic_id, revision)
);

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'infographics_latest_revision_fk') then
    alter table public.infographics
      add constraint infographics_latest_revision_fk
      foreign key (latest_revision_id) references public.infographic_revisions(id)
      deferrable initially deferred;
  end if;
end $$;

create table if not exists public.generations (
  id text primary key,
  infographic_id text not null references public.infographics(id) on delete cascade,
  revision_id text not null references public.infographic_revisions(id),
  renderer_version text not null,
  output_paths jsonb not null default '[]'::jsonb,
  validation jsonb not null default '{}'::jsonb,
  generated_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

create index if not exists dataset_versions_dataset_idx on public.dataset_versions(dataset_id, sequence desc);
create index if not exists base_versions_base_idx on public.base_image_versions(base_image_id, sequence desc);
create index if not exists revisions_infographic_idx on public.infographic_revisions(infographic_id, revision desc);
create index if not exists generations_revision_idx on public.generations(revision_id);

alter table public.indicator_definitions enable row level security;
alter table public.datasets enable row level security;
alter table public.dataset_versions enable row level security;
alter table public.base_images enable row level security;
alter table public.base_image_versions enable row level security;
alter table public.infographics enable row level security;
alter table public.infographic_revisions enable row level security;
alter table public.generations enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'indicator_definitions' and policyname = 'team read indicator definitions') then
    create policy "team read indicator definitions" on public.indicator_definitions for select using (auth.role() = 'authenticated');
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'indicator_definitions' and policyname = 'team write indicator definitions') then
    create policy "team write indicator definitions" on public.indicator_definitions for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
  end if;
end $$;

do $$
declare
  table_name text;
begin
  foreach table_name in array array['datasets','dataset_versions','base_images','base_image_versions','infographics','infographic_revisions','generations']
  loop
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = table_name and policyname = 'team read') then
      execute format('create policy "team read" on public.%I for select using (auth.role() = ''authenticated'')', table_name);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = table_name and policyname = 'team write') then
      execute format('create policy "team write" on public.%I for all using (auth.role() = ''authenticated'') with check (auth.role() = ''authenticated'')', table_name);
    end if;
  end loop;
end $$;

insert into storage.buckets (id, name, public)
values ('observatorio-infograficos', 'observatorio-infograficos', false)
on conflict (id) do nothing;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'team read infographic storage') then
    create policy "team read infographic storage" on storage.objects
      for select using (bucket_id = 'observatorio-infograficos' and auth.role() = 'authenticated');
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'team write infographic storage') then
    create policy "team write infographic storage" on storage.objects
      for all using (bucket_id = 'observatorio-infograficos' and auth.role() = 'authenticated')
      with check (bucket_id = 'observatorio-infograficos' and auth.role() = 'authenticated');
  end if;
end $$;
