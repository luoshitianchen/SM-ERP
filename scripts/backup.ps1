<#
.SYNOPSIS
    sm-erp Windows 备份脚本（PowerShell 版）

.DESCRIPTION
    与 Linux 版 scripts/backup.sh 对应：
      1. 备份 SQLite 数据库文件到 .\backup\<timestamp>.db
         （如使用 PostgreSQL，请在生产环境执行 scripts/backup.sh）
      2. 备份 .env 配置文件（如存在）
      3. 自动清理 RETENTION_DAYS 天前的旧备份

.ENV
    DB_PATH         SQLite 数据库文件路径（默认 <repo>\data.db）
    BACKUP_DIR      备份目录（默认 <repo>\backup）
    RETENTION_DAYS  备份保留天数（默认 7）

.EXAMPLE
    # 首次执行（允许本地脚本运行）
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\scripts\backup.ps1

    # 指定数据库路径
    $env:DB_PATH = "D:\data\app.db"; .\scripts\backup.ps1
#>
$ErrorActionPreference = 'Stop'

# ── 配置 ──
$ServiceName = 'sm-erp'
$RepoRoot    = Split-Path -Parent $PSScriptRoot
$DbPath      = if ($env:DB_PATH)      { $env:DB_PATH }      else { Join-Path $RepoRoot 'data.db' }
$BackupDir   = if ($env:BACKUP_DIR)   { $env:BACKUP_DIR }   else { Join-Path $RepoRoot 'backup' }
$RetentionDays = if ($env:RETENTION_DAYS) { [int]$env:RETENTION_DAYS } else { 7 }

$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$LogPrefix = "[$ServiceName][$Timestamp]"

# 创建备份目录
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

Write-Host "$LogPrefix 开始备份服务 $ServiceName ..."

# ── 1. SQLite 数据库备份 ──
if (Test-Path -Path $DbPath -PathType Leaf) {
    $BackupFile = Join-Path $BackupDir "$Timestamp.db"
    Copy-Item -Path $DbPath -Destination $BackupFile -Force
    $SizeBytes = (Get-Item $BackupFile).Length
    Write-Host ("{0} [OK] SQLite 备份完成：{1} ({2:N0} bytes)" -f $LogPrefix, $BackupFile, $SizeBytes)
} else {
    Write-Host "$LogPrefix [SKIP] 未找到 SQLite 数据库文件：$DbPath"
    Write-Host "$LogPrefix        （生产 PostgreSQL 环境请改用 scripts/backup.sh）"
}

# ── 2. .env 配置备份 ──
$EnvFile = Join-Path $RepoRoot '.env'
if (Test-Path -Path $EnvFile -PathType Leaf) {
    $EnvBackup = Join-Path $BackupDir "$Timestamp.env"
    Copy-Item -Path $EnvFile -Destination $EnvBackup -Force
    Write-Host "$LogPrefix [OK] 配置文件 .env 已备份：$EnvBackup"
} else {
    Write-Host "$LogPrefix [SKIP] 未发现 .env，跳过配置备份"
}

# ── 3. 清理过期备份 ──
$Cutoff = (Get-Date).AddDays(-$RetentionDays)
$Deleted = 0
Get-ChildItem -Path $BackupDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in '.db', '.env' -and $_.LastWriteTime -lt $Cutoff } |
    ForEach-Object {
        Write-Host "$LogPrefix [CLEAN] 删除过期备份：$($_.FullName)"
        Remove-Item $_.FullName -Force
        $Deleted++
    }
Write-Host "$LogPrefix [CLEAN] 共清理 $Deleted 个过期文件（保留 $RetentionDays 天）"

Write-Host "$LogPrefix 备份流程结束。"
exit 0
