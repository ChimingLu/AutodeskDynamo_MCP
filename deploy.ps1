$ErrorActionPreference = "Stop"

# Configuration
$ProjectFile = "DynamoViewExtension\DynamoMCPListener.csproj"
$PackageName = "MCP_Listener_Package"
$PackageSourceDir = Join-Path $PSScriptRoot $PackageName
$PackageBinDir = Join-Path $PackageSourceDir "bin"

# Determine Dynamo Packages Path (Trying standard locations)
$AppDataDynamo = "$env:AppData\Dynamo\Dynamo Revit"
# Filter for version numbers only (digit dot digit)
$PossibleVersions = Get-ChildItem $AppDataDynamo -Directory | Where-Object { $_.Name -match "^\d+\.\d+$" } | Sort-Object { [version]$_.Name } -Descending

if ($PossibleVersions.Count -eq 0) {
    Write-Error "Could not find any Dynamo Revit versions in $AppDataDynamo"
}

# Pick the latest version (e.g., 3.3)
$TargetVersion = $PossibleVersions[0].Name
$DynamoPackagesDir = Join-Path $AppDataDynamo "$TargetVersion\packages"
$TargetPackageDir = Join-Path $DynamoPackagesDir "MCP Listener"

Write-Host "Targeting Dynamo Version: $TargetVersion"
Write-Host "Deploying to: $TargetPackageDir"

# 1. Build project
Write-Host "`n[1/3] Building Project..."
dotnet build $ProjectFile -c Release
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

# 2. Copy Binaries to Package structure
Write-Host "`n[2/3] Updating Package Binaries..."
if (-not (Test-Path $PackageBinDir)) { New-Item -ItemType Directory -Path $PackageBinDir | Out-Null }

# Note: AppendTargetFrameworkToOutputPath is false in csproj, so output is directly in bin/Release
$BuildOutputDir = "DynamoViewExtension\bin\Release"
Copy-Item "$BuildOutputDir\*" -Destination $PackageBinDir -Force -Recurse

# 3. Deploy to Dynamo
Write-Host "`n[3/3] Deploying to Dynamo Packages..."
if (Test-Path $TargetPackageDir) {
    Remove-Item $TargetPackageDir -Recurse -Force
}
Copy-Item $PackageSourceDir -Destination $TargetPackageDir -Recurse -Force

# 4. Deploy Config
Write-Host "`n[Deploying Config] Copying mcp_config.json..."
Copy-Item "mcp_config.json" -Destination $TargetPackageDir -Force

Write-Host "`nSUCCESS: Package deployed successfully!"
Write-Host "You can now open Dynamo/Revit."
