#!/bin/bash
# =============================================================================
# 恢复脚本 - sm-erp
# -----------------------------------------------------------------------------
# 功能：从指定的 .sql.gz 备份文件恢复 PostgreSQL 数据库
#
# 使用：
#   chmod +x scripts/restore.sh
#   ./scripts/restore.sh /backup/sm-erp/20260916_020000.sql.gz
#   ./scripts/restore.sh -f /backup/sm-erp/20260916_020000.sql.gz   # 非交互，跳过确认
#
# 环境变量：
#   DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD
# =============================================================================
set -euo pipefail

SERVICE_NAME="sm-erp"
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-sm_erp_db}"
DB_USER="${DB_USER:-sm_user}"
DB_PASSWORD="${DB_PASSWORD:-}"

ASSUME_YES=0
if [ "${1:-}" = "-f" ] || [ "${1:-}" = "--force" ]; then
  ASSUME_YES=1
  shift
fi

BACKUP_FILE="${1:-}"
if [ -z "${BACKUP_FILE}" ]; then
  echo "用法: $0 [-f|--force] <backup-file.sql.gz>" >&2
  exit 2
fi
if [ ! -f "${BACKUP_FILE}" ]; then
  echo "[${SERVICE_NAME}][FAIL] 备份文件不存在：${BACKUP_FILE}" >&2
  exit 2
fi

echo "[${SERVICE_NAME}] 目标数据库: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "[${SERVICE_NAME}] 恢复来源  : ${BACKUP_FILE}"
echo "[${SERVICE_NAME}] ****************************************************************"
echo "[${SERVICE_NAME}] *** 警告：恢复将覆盖目标库当前所有数据！                   ***"
echo "[${SERVICE_NAME}] ****************************************************************"

if [ "${ASSUME_YES}" -ne 1 ]; then
  read -r -p "[${SERVICE_NAME}] 确认恢复？输入大写 YES 继续: " CONFIRM
  if [ "${CONFIRM}" != "YES" ]; then
    echo "[${SERVICE_NAME}] 已取消，未做任何改动。"
    exit 0
  fi
fi

export PGPASSWORD="${DB_PASSWORD}"
echo "[${SERVICE_NAME}] 开始恢复 ..."
if gunzip -c "${BACKUP_FILE}" \
    | psql -v ON_ERROR_STOP=1 \
          --host="${DB_HOST}" \
          --port="${DB_PORT}" \
          --username="${DB_USER}" \
          --dbname="${DB_NAME}"; then
  echo "[${SERVICE_NAME}] [OK] 数据库恢复完成。"
else
  echo "[${SERVICE_NAME}][FAIL] 恢复过程中发生错误，请检查上面的 psql 输出。" >&2
  unset PGPASSWORD
  exit 1
fi

# ── 恢复后连接验证 ──
echo "[${SERVICE_NAME}] 验证数据库连接 ..."
if pg_isready --host="${DB_HOST}" --port="${DB_PORT}" --username="${DB_USER}" --dbname="${DB_NAME}"; then
  echo "[${SERVICE_NAME}] [OK] 数据库连接正常，恢复流程结束。"
else
  echo "[${SERVICE_NAME}][WARN] pg_isready 未通过，请人工检查数据库状态。" >&2
  unset PGPASSWORD
  exit 1
fi
unset PGPASSWORD
exit 0
