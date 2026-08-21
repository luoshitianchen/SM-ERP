param(
  [switch]$SkipAudit
)
$ErrorActionPreference = "Stop"
python -m pytest tests -q
if (-not $SkipAudit) {
  python -m pip install --upgrade pip-audit bandit ruff
  python -m pip_audit -r requirements.txt
  python -m bandit -q -r app -x tests
  python -m ruff check app tests
}
