$ErrorActionPreference = 'Stop'

$container = 'csc4801-teamzzz-demo'
$running = docker inspect -f '{{.State.Running}}' $container 2>$null

if ($LASTEXITCODE -ne 0 -or $running -ne 'true') {
    & (Join-Path $PSScriptRoot 'start-demo.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to start TalentMatch demo before reset.'
    }
}

docker exec $container flask --app recruiting reset-seed
if ($LASTEXITCODE -ne 0) {
    throw "Demo reset failed with exit code $LASTEXITCODE"
}

docker exec $container flask --app recruiting ensure-demo-user
if ($LASTEXITCODE -ne 0) {
    throw "Deployment demo user restore failed with exit code $LASTEXITCODE"
}

$response = Invoke-WebRequest 'http://127.0.0.1:18084/healthz' -NoProxy -TimeoutSec 5
if ($response.StatusCode -ne 200) {
    throw "Demo health check returned HTTP $($response.StatusCode)"
}
