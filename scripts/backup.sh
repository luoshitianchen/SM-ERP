#!/bin/bash
# =============================================================================
# 备份脚本 - sm-erp
# -----------------------------------------------------------------------------
# 功能：
#   1. 使用 pg_dump 备份 PostgreSQL 数据库
#      -> ${BACKUP_DIR}/sm-erp/<timestamp>.sql.gz
#   2. 备份 .env 配置文件（如存在）
#   3. 自动清理 RETENTION_DAYS 天前的旧备份
#
# 环境变量：
#   DB_HOST         数据库主机（默认 postgres）
#   DB_PORT         数据库端口（默认 5432）
#   DB_NAME         数据库名（默认 sm_erp_db）
#   DB_USER         数据库用户（默认 sm_user）
#   DB_PASSWORD     数据库密码（建议通过环境变量注入，勿硬编码）
#   BACKUP_DIR      备份根目录（默认 /backup，与 docker-compose 卷挂载一致）
#   RETENTION_DAYS  备份保留天数（默认 7）
#
# 使用：
#   chmod +x scripts/backup.sh      # 首次需赋予可执行权限
#   DB_PASSWORD=******** ./scripts/backup.sh
# =============================================================================
set -euo pipefail

# ── 服务与连接配置 ──
SERVICE_NAME="sm-erp"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-sm_erp_db}"
DB_USER="${DB_USER:-sm_user}"
DB_PASSWORD="${DB_PASSWORD:-}"
BACKUP_DIR="${BACKUP_DIR:-/backup}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

DEST_DIR="${BACKUP_DIR}/${SERVICE_NAME}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_PREFIX="[${SERVICE_NAME}][${TIMESTAMP}]"
BACKUP_FILE="${DEST_DIR}/${TIMESTAMP}.sql.gz"
ENV_ARCHIVE="${DEST_DIR}/${TIMESTAMP}.env.gz"
DUMP_ERR_FILE="${DEST_DIR}/.dump_${TIMESTAMP}.err"

mkdir -p "${DEST_DIR}"

echo "${LOG_PREFIX} 开始备份服务 ${SERVICE_NAME} -> ${DEST_DIR}"

# ── 1. PostgreSQL 数据库备份 ──
if [ -z "${DB_PASSWORD}" ]; then
  echo "${LOG_PREFIX} [WARN] DB_PASSWORD 未设置，尝试无密码连接（请确认 pg_hba 策略）"
fi

export PGPASSWORD="${DB_PASSWORD}"
if ! pg_dump \
      --host="${DB_HOST}" \
      --port="${DB_PORT}" \
      --username="${DB_USER}" \
      --dbname="${DB_NAME}" \
      --no-owner --no-privileges --clean --if-exists \
      2>"${DUMP_ERR_FILE}" \
      | gzip -c > "${BACKUP_FILE}"; then
  echo "${LOG_PREFIX} [FAIL] pg_dump 失败，错误输出：" >&2
  cat "${DUMP_ERR_FILE}" >&2
  rm -f "${BACKUP_FILE}" "${DUMP_ERR_FILE}"
  unset PGPASSWORD
  exit 1
fi
unset PGPASSWORD
rm -f "${DUMP_ERR_FILE}"

SIZE="$(du -h "${BACKUP_FILE}" | awk '{print $1}')"
echo "${LOG_PREFIX} [OK] 数据库备份完成：${BACKUP_FILE} (${SIZE})"

# ── 2. 配置文件 .env 备份（如存在）──
if [ -f ".env" ]; then
  gzip -c ".env" > "${ENV_ARCHIVE}"
  echo "${LOG_PREFIX} [OK] 配置文件 .env 已备份到 ${ENV_ARCHIVE}"
else
  echo "${LOG_PREFIX} [SKIP] 当前目录未发现 .env，跳过配置备份"
fi

# ── 3. 清理过期备份 ──
DELETED=0
while IFS= read -r old; do
  echo "${LOG_PREFIX} [CLEAN] 删除过期备份：${old}"
  rm -f "${old}"
  DELETED=$((DELETED + 1))
done < <(find "${DEST_DIR}" -maxdepth 1 -type f \
            \( -name '*.sql.gz' -o -name '*.env.gz' \) -mtime "+${RETENTION_DAYS}")
echo "${LOG_PREFIX} [CLEAN] 共清理 ${DELETED} 个过期文件（保留 ${RETENTION_DAYS} 天）"

echo "${LOG_PREFIX} 备份流程结束。"
exit 0
