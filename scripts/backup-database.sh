#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

project_dir=/home/lucas/referee-system
backup_dir=/home/lucas/backups/referee-system

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

# 防止手动备份与定时备份同时运行。
exec 9>"$backup_dir/.backup.lock"
if ! flock -n 9; then
  echo "$(date -Is) 已有备份运行，本次跳过"
  exit 0
fi

cd "$project_dir"

backup_file="$backup_dir/database-$(date +%Y%m%d-%H%M%S)-$$.dump"
partial_file="$backup_file.partial"

cleanup() {
  result=$?
  trap - EXIT
  rm -f -- "$partial_file"
  if [ "$result" -ne 0 ]; then
    echo "$(date -Is) 备份失败，退出码：$result" >&2
  fi
  exit "$result"
}
trap cleanup EXIT

echo "$(date -Is) 开始备份"

docker compose exec -T db sh -c \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "$partial_file"

test -s "$partial_file"

# 检查归档目录可读取；完整恢复演练仍需定期进行。
docker compose exec -T db pg_restore --list \
  < "$partial_file" > /dev/null

mv -- "$partial_file" "$backup_file"
echo "$(date -Is) 备份成功：$backup_file"

# 仅在本次备份成功后，清理超过 14 天的正式备份。
find "$backup_dir" -maxdepth 1 -type f \
  -name 'database-*.dump' -mmin +20160 -print -delete

echo "$(date -Is) 备份及清理完成"
