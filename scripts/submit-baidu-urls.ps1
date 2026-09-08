[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string[]] $Url,
    [string] $SiteUrl = "https://ai.pricememo.cn",
    [string] $Token = $env:BAIDU_PUSH_TOKEN,
    [int] $TimeoutSec = 30
)

if ([string]::IsNullOrWhiteSpace($Token)) {
    throw "BAIDU_PUSH_TOKEN is required. Get the token from the verified Baidu Search Resource Platform property."
}

$site = [Uri]$SiteUrl
if ($site.Scheme -ne "https" -or [string]::IsNullOrWhiteSpace($site.Host)) {
    throw "SiteUrl must be an https URL."
}

$normalizedUrls = @(
    $Url |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ } |
        Select-Object -Unique
)
if ($normalizedUrls.Count -eq 0) { throw "At least one URL is required." }
if ($normalizedUrls.Count -gt 10000) { throw "Submit at most 10,000 URLs per request." }

foreach ($candidate in $normalizedUrls) {
    try {
        $candidateUri = [Uri]$candidate
    } catch {
        throw "Every URL must be a valid absolute URL: $candidate"
    }
    if ($candidateUri.Scheme -ne "https" -or $candidateUri.Host -ne $site.Host) {
        throw "Every URL must be an https URL on $($site.Host): $candidate"
    }
}

$query = "site=$([Uri]::EscapeDataString($site.AbsoluteUri.TrimEnd('/')))&token=$([Uri]::EscapeDataString($Token))"
$endpoint = "https://data.zz.baidu.com/urls?$query"
$body = $normalizedUrls -join "`n"

try {
    $response = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "text/plain; charset=utf-8" -Body $body -TimeoutSec $TimeoutSec
    if ($null -eq $response) {
        Write-Output "Baidu active-push submission completed for $($normalizedUrls.Count) URL(s)."
    } else {
        $response | ConvertTo-Json -Depth 5
    }
} catch {
    throw "Baidu active-push submission failed: $($_.Exception.Message)"
}
