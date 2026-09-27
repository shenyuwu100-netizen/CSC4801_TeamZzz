$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$composeFile = Join-Path $repoRoot 'deploy\demo\docker-compose.yml'
$envFile = Join-Path $repoRoot 'deploy\demo\.env'

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Missing deployment environment file: $envFile"
}

$dockerReady = $false
for ($attempt = 1; $attempt -le 18; $attempt++) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        break
    }
    Start-Sleep -Seconds 10
}
if (-not $dockerReady) {
    throw 'Docker did not become ready within 180 seconds.'
}

docker compose -f $composeFile --env-file $envFile up -d
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed with exit code $LASTEXITCODE"
}

for ($attempt = 1; $attempt -le 20; $attempt++) {
    try {
        $response = Invoke-WebRequest 'http://127.0.0.1:18084/healthz' -NoProxy -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            exit 0
        }
    } catch {
        # 容器刚启动时可能仍处于健康检查宽限期，等待后继续复查。
    }
    Start-Sleep -Seconds 2
}

throw 'TalentMatch demo did not become healthy.'
