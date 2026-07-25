# Validates that every local (non-http, non-mailto) Markdown link in the repo
# resolves to an existing file or directory, and that in-file anchors resolve to a
# heading in the target file (GitHub-style slug matching). Prints one line per
# broken link and exits non-zero if any are found.

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$mdFiles = Get-ChildItem -Path $root -Recurse -Filter *.md -File |
    Where-Object {
        $_.FullName -notlike '*\.git\*' -and
        $_.FullName -notlike '*\.tools\*'
    }

function ConvertTo-Slug($heading) {
    $slug = $heading.ToLower()
    $slug = $slug -replace '[^a-z0-9\s\-_]', ''
    $slug = $slug -replace '\s+', '-'
    return $slug
}

$brokenLinks = @()
$linkPattern = '\[[^\]]*\]\(([^)]+)\)'

foreach ($file in $mdFiles) {
    $content = Get-Content -Path $file.FullName -Raw
    $matches = [regex]::Matches($content, $linkPattern)
    foreach ($m in $matches) {
        $target = $m.Groups[1].Value.Trim()

        if ($target -match '^(https?://|mailto:)') { continue }

        $anchor = $null
        $pathPart = $target
        if ($target -match '^(.*?)#(.*)$') {
            $pathPart = $Matches[1]
            $anchor = $Matches[2]
        }

        if ([string]::IsNullOrWhiteSpace($pathPart)) {
            $resolvedFile = $file.FullName
        } else {
            $resolvedFile = Join-Path $file.DirectoryName $pathPart
        }

        if (-not (Test-Path $resolvedFile)) {
            $brokenLinks += "$($file.FullName.Substring($root.Length + 1)): target not found -> $target"
            continue
        }

        if ($anchor -and (Test-Path $resolvedFile -PathType Leaf) -and $resolvedFile -match '\.md$') {
            $targetContent = Get-Content -Path $resolvedFile -Raw
            $headingMatches = [regex]::Matches($targetContent, '(?m)^#{1,6}\s+(.+?)\s*$')
            $slugs = @()
            $slugCounts = @{}
            foreach ($hm in $headingMatches) {
                $baseSlug = ConvertTo-Slug $hm.Groups[1].Value
                if ($slugCounts.ContainsKey($baseSlug)) {
                    $slugCounts[$baseSlug] += 1
                    $slugs += "$baseSlug-$($slugCounts[$baseSlug])"
                } else {
                    $slugCounts[$baseSlug] = 0
                    $slugs += $baseSlug
                }
            }
            if ($slugs -notcontains $anchor) {
                $brokenLinks += "$($file.FullName.Substring($root.Length + 1)): anchor '#$anchor' not found in -> $pathPart"
            }
        }
    }
}

if ($brokenLinks.Count -eq 0) {
    Write-Output "OK: all local markdown links resolved ($($mdFiles.Count) files scanned)."
    exit 0
} else {
    Write-Output "BROKEN LINKS ($($brokenLinks.Count)):"
    $brokenLinks | ForEach-Object { Write-Output "  $_" }
    exit 1
}
