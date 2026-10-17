-- VLM 설명문 검색: 영상별 설명문 생성 상태 테이블 (2026-10-17)
-- 지금 쓰는 DB(새 프로젝트)의 SQL Editor에서 한 번 실행하세요. 여러 번 실행해도 됩니다.
-- 새로 만드는 프로젝트는 docs/supabase/schema.sql에 같은 내용이 들어 있습니다.
--
-- 설명문 자체와 임베딩은 DB가 아니라 서버 디스크(data/processed/captions/)에 저장하고,
-- 이 테이블에는 상태와 만든 모델만 기록합니다.
-- 기능이 꺼져 있으면(CAPTION_SEARCH_ENABLED=0) 이 테이블은 읽거나 쓰지 않습니다.

create table if not exists public.video_captions (
    video_id       uuid primary key references public.videos (video_id) on delete cascade,
    status         text not null default 'PENDING'
                   check (status in ('PENDING', 'PROCESSING', 'READY', 'FAILED')),
    caption_model  text,                -- 예: Qwen/Qwen3-VL-4B-Instruct
    embed_model    text,                -- 예: intfloat/multilingual-e5-large
    batch_size     integer,
    num_frames     integer,
    caption_path   text,                -- 서버의 설명문 파일 경로 (레포 기준 상대경로)
    error_message  text,
    started_at     timestamptz,
    finished_at    timestamptz,
    created_at     timestamptz default now(),
    updated_at     timestamptz default now()
);

-- updated_at 자동 갱신 (schema.sql에서 만든 함수를 같이 씀. 없으면 만듦)
create or replace function public.set_updated_at() returns trigger
language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists video_captions_set_updated_at on public.video_captions;
create trigger video_captions_set_updated_at
    before update on public.video_captions
    for each row execute function public.set_updated_at();

-- 대기·진행 중인 작업 찾기 (서버 재시작 후 오래 멈춘 PROCESSING 정리용)
create index if not exists video_captions_status_idx on public.video_captions (status, updated_at);

-- 다른 테이블과 같이 RLS만 켜고 정책은 두지 않음 (백엔드는 service 키로만 접근)
alter table public.video_captions enable row level security;

-- 확인용 (실행 후 결과가 나오면 정상)
-- select column_name, data_type from information_schema.columns where table_name = 'video_captions' order by ordinal_position;
-- select rowsecurity from pg_tables where tablename = 'video_captions';
-- select trigger_name from information_schema.triggers where event_object_table = 'video_captions';
