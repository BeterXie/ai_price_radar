[CmdletBinding()]
param(
    [string] $SiteUrl = "https://ai.pricememo.cn",
    [string] $SitemapUrl = "",
    [string] $ApiKey = $env:BING_WEBMASTER_API_KEY
)

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "BING_WEBMASTER_API_KEY is required, or submit the sitemap from the authenticated Bing Webmaster Tools UI."
}
if ([string]::IsNullOrWhiteSpace($SitemapUrl)) {
    $SitemapUrl = "$($SiteUrl.TrimEnd("/"))/sitemap.xml"
}

$site = [Uri]$SiteUrl
$feed = [Uri]$SitemapUrl
if ($site.Scheme -ne "https" -or $feed.Scheme -ne "https") {
    throw "SiteUrl and SitemapUrl must be https URLs."
}

$query = "apikey=$([Uri]::EscapeDataString($ApiKey))&siteUrl=$([Uri]::EscapeDataString($site.AbsoluteUri.TrimEnd("/")))&feedUrl=$([Uri]::EscapeDataString($feed.AbsoluteUri))"
$endpoint = "https://ssl.bing.com/webmaster/api.svc/json/SubmitSitemap?$query"
try {
    $response = Invoke-RestMethod -Method Get -Uri $endpoint
    if ($null -eq $response) {
        Write-Output "Bing Webmaster sitemap submission completed."
    } else {
        Write-Output ($response | ConvertTo-Json -Depth 5)
    }
} catch {
    throw "Bing Webmaster sitemap submission failed: $($_.Exception.Message)"
}
