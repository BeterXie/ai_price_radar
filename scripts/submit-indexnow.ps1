[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string[]] $Url,
    [string] $SiteUrl = "https://ai.pricememo.cn",
    [string] $Key = $env:INDEXNOW_KEY,
    [string] $KeyLocation = ""
)

if ([string]::IsNullOrWhiteSpace($Key)) {
    throw "INDEXNOW_KEY is required. Provision the same key in the web runtime and pass it through the environment."
}

$site = [Uri]$SiteUrl
if ($site.Scheme -ne "https" -or [string]::IsNullOrWhiteSpace($site.Host)) {
    throw "SiteUrl must be an https URL."
}

$normalizedUrls = @($Url | ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Unique)
if ($normalizedUrls.Count -eq 0) { throw "At least one URL is required." }
if ($normalizedUrls.Count -gt 10000) { throw "IndexNow accepts at most 10,000 URLs per request." }
foreach ($candidate in $normalizedUrls) {
    $candidateUri = [Uri]$candidate
    if ($candidateUri.Scheme -ne "https" -or $candidateUri.Host -ne $site.Host) {
        throw "Every URL must be an https URL on $($site.Host): $candidate"
    }
}

if ([string]::IsNullOrWhiteSpace($KeyLocation)) {
    $KeyLocation = "$($site.AbsoluteUri.TrimEnd("/"))/indexnow-key.txt"
}

$payload = @{
    host = $site.Host
    key = $Key
    keyLocation = $KeyLocation
    urlList = $normalizedUrls
} | ConvertTo-Json -Depth 3

try {
    $response = Invoke-RestMethod -Method Post -Uri "https://api.indexnow.org/indexnow" -ContentType "application/json; charset=utf-8" -Body $payload
    if ($null -eq $response) {
        Write-Output "IndexNow notification submitted for $($normalizedUrls.Count) URL(s)."
    } else {
        Write-Output ($response | ConvertTo-Json -Depth 5)
    }
} catch {
    throw "IndexNow submission failed: $($_.Exception.Message)"
}
