#!/usr/bin/env bash
# backend/.env를 팀 DB용(.env.team)·내 DB용(.env.new) 중 하나로 바꿉니다. 값은 출력하지 않습니다.
#
#   bash tools/supabase/use_env.sh status   # 지금 backend/.env가 어느 쪽과 같은지
#   bash tools/supabase/use_env.sh init     # 처음 한 번: 지금 backend/.env를 backend/.env.team으로 복사(덮어쓰지 않음)
#   bash tools/supabase/use_env.sh new      # backend/.env ← backend/.env.new
#   bash tools/supabase/use_env.sh team     # backend/.env ← backend/.env.team
#
# 바꾼 뒤에는 백엔드를 다시 시작해야 적용됩니다. 바꾸기 전 backend/.env는 backend/.env.bak으로 남깁니다.
# .env.team·.env.new·.env.bak은 .gitignore의 .env.* 규칙으로 커밋되지 않습니다.
set -euo pipefail
cd "$(dirname "$0")/../../backend"

fingerprint() {  # Supabase 접속 값만 비교용 해시로 (값 자체는 출력하지 않음)
  [ -f "$1" ] || { echo "-"; return; }
  grep -E '^(SUPABASE_URL|SUPABASE_SERVICE_KEY)=' "$1" | sort | sha256sum | cut -c1-12
}

case "${1:-status}" in
  status)
    cur=$(fingerprint .env)
    for f in .env.team .env.new; do
      if [ -f "$f" ] && [ "$(fingerprint "$f")" = "$cur" ]; then echo "backend/.env = $f 의 Supabase 값"; exit 0; fi
    done
    echo "backend/.env의 Supabase 값이 .env.team·.env.new 어느 쪽과도 같지 않습니다 (init을 했는지 확인)"
    ;;
  init)
    if [ -e .env.team ]; then echo ".env.team이 이미 있어 덮어쓰지 않습니다"; exit 1; fi
    cp -p .env .env.team && chmod 600 .env.team && echo "backend/.env → backend/.env.team 복사 완료"
    ;;
  team|new)
    src=".env.$1"
    [ -f "$src" ] || { echo "backend/$src 파일이 없습니다"; exit 1; }
    for k in SUPABASE_URL SUPABASE_SERVICE_KEY; do
      grep -q "^$k=." "$src" || { echo "backend/$src에 $k 값이 없습니다"; exit 1; }
    done
    cp -p .env .env.bak && cp -p "$src" .env && chmod 600 .env
    echo "backend/.env ← backend/$src (이전 값은 backend/.env.bak). 백엔드를 다시 시작하세요."
    ;;
  *) echo "사용법: $0 status|init|team|new"; exit 1 ;;
esac
