# Local quality gate. Run before every commit. No CI runs in the cloud.
$ErrorActionPreference = "Stop"

$steps = @(
    { ruff format --check . },
    { ruff check . },
    { mypy --strict src tests },
    { python -m pytest }
)
foreach ($step in $steps) {
    & $step
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
