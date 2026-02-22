$ErrorActionPreference = "Stop"

# ========================================
# Step 0: Convert Config
# ========================================
Write-Host "`n[0/4] Updating Config..." -ForegroundColor Cyan
$UpdateConfigScript = Join-Path $PSScriptRoot "scripts\update_config.py"
if (Test-Path $UpdateConfigScript) {
    python $UpdateConfigScript
    if ($LASTEXITCODE -ne 0) { 
        Write-Warning "Config conversion failed, using existing mcp_config.json"
    }
}
else {
    Write-Host "   WARNING: update_config.py not found, skipping config update" -ForegroundColor Yellow
}

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
Write-Host "`n[1/4] Building Project..."
dotnet build $ProjectFile -c Release
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

# 2. Copy Binaries to Package structure
Write-Host "`n[2/4] Updating Package Binaries..."
if (-not (Test-Path $PackageBinDir)) { New-Item -ItemType Directory -Path $PackageBinDir | Out-Null }

# Note: AppendTargetFrameworkToOutputPath is false in csproj, so output is directly in bin/Release
$BuildOutputDir = "DynamoViewExtension\bin\Release"
Copy-Item "$BuildOutputDir\*" -Destination $PackageBinDir -Force -Recurse

# RESTORE: Newtonsoft.Json (Just in case)
# REMOVE: .deps.json (CRITICAL fix for .NET Core plugins)
# If .deps.json exists, it enforces strict version matching which fails in Dynamo.
if (Test-Path "$PackageBinDir\DynamoMCPListener.deps.json") {
    Remove-Item "$PackageBinDir\DynamoMCPListener.deps.json" -Force
    Write-Host "   - Removed .deps.json to prevent AssemblyLoadContext strictness." -ForegroundColor Magenta
}

$ConflictDlls = @("DynamoServices.dll", "DynamoCore.dll", "DynamoInstallTask.dll") # Keeping Newtonsoft
foreach ($dll in $ConflictDlls) {
    # Remove conflicts...
    $dllPath = Join-Path $PackageBinDir $dll
    if (Test-Path $dllPath) {
        Remove-Item $dllPath -Force
        Write-Host "   - Removed conflicting DLL: $dll" -ForegroundColor DarkGray
    }
}

# 3. Deploy to Dynamo (Primary Location: Dynamo Revit 3.3 or whichever is set in $DynamoPackagesDir)
Write-Host "`n[3/4] Deploying to Dynamo Packages (Primary)..."

# 確保套件目錄存在 (Ensure packages directory exists)
if (-not (Test-Path $DynamoPackagesDir)) {
    New-Item -ItemType Directory -Path $DynamoPackagesDir -Force | Out-Null
    Write-Host "   - Created packages directory: $DynamoPackagesDir" -ForegroundColor Cyan
}
if (Test-Path $TargetPackageDir) {
    Remove-Item $TargetPackageDir -Recurse -Force
}
Copy-Item $PackageSourceDir -Destination $TargetPackageDir -Recurse -Force

# UNBLOCK FILES (Security Fix)
Write-Host "   - Unblocking files to prevent 'Mark of the Web' issues..."
Get-ChildItem -Path $TargetPackageDir -Recurse | Unblock-File

# 4. Deploy Config
Write-Host "`n[4/4] Deploying Config & Updating ViewExtension Paths..." -ForegroundColor Cyan

# Deploy mcp_config.json to package directory
$configSource = Join-Path $PSScriptRoot "mcp_config.json"
$configDest = Join-Path $TargetPackageDir "mcp_config.json"

if (Test-Path $configSource) {
    Copy-Item $configSource $configDest -Force
    Write-Host "   - Config file deployed: mcp_config.json" -ForegroundColor Green
}
else {
    Write-Warning "   - Config file not found: $configSource"
}

# --- CLEANUP STRATEGY: Remove Legacy XMLs and rely on valid pkg.json ---
# We previously broadcasted XMLs everywhere. This creates "Double Loading" risks if pkg.json also works.
# Since we fixed pkg.json path ("bin\dll"), we should CLEANUP the XMLs to be safe.

$XmlFileName = "DynamoMCPListener_ViewExtensionDefinition.xml"

Write-Host "`n[4.5/4] Cleaning up Legacy XML Registrations..."

# Scan for all Dynamo versions
$AppDataDynamo = "$env:AppData\Dynamo"
$Products = Get-ChildItem -Path $AppDataDynamo -Directory

foreach ($Product in $Products) {
    # Check for Versions starting with 3.
    $Versions = Get-ChildItem -Path $Product.FullName -Directory
    
    foreach ($Ver in $Versions) {
        $GlobalExtDir = Join-Path $Ver.FullName "viewExtensions"
        if (Test-Path $GlobalExtDir) {
            $TargetXml = Join-Path $GlobalExtDir $XmlFileName
            if (Test-Path $TargetXml) {
                Remove-Item $TargetXml -Force
                Write-Host "      [-] Removed legacy XML from: $($Product.Name) \$($Ver.Name)" -ForegroundColor Yellow
            }
        }
    }
}

# Note: We KEEP the Package-Level XML because it's required for some Dynamo versions.
# The previous broadcasted XMLs in global folders are still removed to prevent conflicts.

Write-Host "`nSUCCESS: Package deployed!"
Write-Host "You can now open Dynamo."
