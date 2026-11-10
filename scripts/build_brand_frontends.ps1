# Run from a clean, published release after its CI gates pass.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^v[0-9]+\.[0-9]+\.[0-9]+$')][string]$ReleaseTag,
    [string]$OutputDirectory = (Join-Path $env:TEMP 'pricememo-brand-release'),
    [ValidateSet('pricememo', 'aiprice', 'aisi', 'pricein', 'openprice')][string[]]$Sites = @('pricememo', 'aiprice', 'aisi', 'pricein', 'openprice')
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$webRoot = Join-Path $repoRoot 'apps\web'
$nextCli = Join-Path $webRoot 'node_modules\next\dist\bin\next'
$archives = @()
Push-Location $repoRoot
try {
    $status = & git status --porcelain
    if ($LASTEXITCODE -ne 0) { throw 'Could not read Git status' }
    if ($status) { throw 'Release builds require a clean worktree' }
    $head = & git rev-parse HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Could not resolve HEAD' }
    $tagCommit = & git rev-list -n 1 $ReleaseTag
    if ($LASTEXITCODE -ne 0 -or $head -ne $tagCommit) { throw 'Release tag must match HEAD' }
    $releaseJson = & gh release view $ReleaseTag --repo BeterXie/ai_price_radar --json tagName,isDraft
    if ($LASTEXITCODE -ne 0) { throw 'Release tag must be published' }
    if (($releaseJson | ConvertFrom-Json).isDraft) { throw 'Draft releases cannot be deployed' }
    $runsJson = & gh run list --repo BeterXie/ai_price_radar --commit $head --workflow CI --json status,conclusion --limit 5
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify CI' }
    $runs = $runsJson | ConvertFrom-Json
    $latestRun = $runs | Select-Object -First 1
    if (-not $latestRun -or $latestRun.status -ne 'completed' -or $latestRun.conclusion -ne 'success') { throw 'The latest CI run for this release must pass' }
    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $oldSite = $env:NEXT_PUBLIC_SITE_ID
    $oldApi = $env:INTERNAL_API_BASE_URL
    $oldPublicApi = $env:NEXT_PUBLIC_API_BASE_URL
    try {
        $env:INTERNAL_API_BASE_URL = 'http://api:8000'
        $env:NEXT_PUBLIC_API_BASE_URL = ''
        Push-Location $webRoot
        try {
            foreach ($site in $Sites) {
                $env:NEXT_PUBLIC_SITE_ID = $site
                & node $nextCli build
                if ($LASTEXITCODE -ne 0) { throw "Frontend build failed: $site" }
                $bundleMatches = & rg -a -l 'http://localhost:8000' (Join-Path $webRoot '.next\static')
                $searchExit = $LASTEXITCODE
                if ($searchExit -gt 1) { throw 'Could not inspect frontend bundle' }
                if ($searchExit -eq 0) { throw "Localhost API in $site bundle: $bundleMatches" }
                $archive = Join-Path $OutputDirectory "$ReleaseTag-web-$site.tar.gz"
                & tar -czf $archive --exclude=public/data -C $webRoot .next/standalone .next/static public Dockerfile.prebuilt
                if ($LASTEXITCODE -ne 0) { throw "Could not package $site" }
                $archives += $archive
            }
        } finally { Pop-Location }
    } finally {
        $env:NEXT_PUBLIC_SITE_ID = $oldSite
        $env:INTERNAL_API_BASE_URL = $oldApi
        $env:NEXT_PUBLIC_API_BASE_URL = $oldPublicApi
    }
    Get-FileHash -LiteralPath $archives -Algorithm SHA256
} finally { Pop-Location }
