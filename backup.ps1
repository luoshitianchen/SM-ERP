param(
    [string]$BackupDirectory = (Join-Path $PSScriptRoot 'backup')
)

$ErrorActionPreference = 'Stop'
$database = Join-Path $PSScriptRoot 'data\erp.db'
if (-not (Test-Path -LiteralPath $database)) { throw "数据库不存在: $database" }
New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$target = Join-Path $BackupDirectory "erp-$timestamp.db"

@'
import sqlite3
import sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
source.backup(target)
target.close()
source.close()
'@ | py -3.11 - $database $target

Write-Host "已创建一致性备份: $target"
