# Autodesk Dynamo MCP & Skill 一鍵安裝腳本
# 定位：自動化組態、權限處理與 Skill 連結

$ErrorActionPreference = "Stop"

Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Dynamo MCP & Skill Setup Assistant" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan

# 1. 檢查 Python 環境
Write-Host "`n[1/4] Checking Python environment..." -ForegroundColor Yellow
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Please install Python 3.10+."
}
Write-Host "   - Installing dependencies (websockets)..."
pip install -r requirements.txt --quiet

# 2. 建置與部署 Dynamo 插件
Write-Host "`n[2/4] Deploying Dynamo ViewExtension..." -ForegroundColor Yellow
if (Test-Path "deploy.ps1") {
    powershell -File .\deploy.ps1
}
else {
    Write-Warning "   - deploy.ps1 not found, skipping plugin deployment."
}

# 3. 建立 Skill 符號連結 (解決權限問題)
Write-Host "`n[3/4] Linking Skill to AI Tool..." -ForegroundColor Yellow
$SkillSource = Join-Path $PSScriptRoot ".skills\dynamo-automation"
$AppData = [System.Environment]::GetFolderPath('ApplicationData')
$GeminiSkillPath = Join-Path $AppData "..\Local\antigravity\skills\dynamo-automation"

# 確保目錄存在 (Antigravity 可能在 Local 或 Roaming)
$LocalGemini = Join-Path $AppData "..\Local\antigravity\skills"
if (-not (Test-Path $LocalGemini)) {
    Write-Host "   - Target skill directory not found at $LocalGemini, skipping link." -ForegroundColor Gray
}
else {
    if (Test-Path $GeminiSkillPath) {
        Write-Host "   - Skill already linked or exists at target." -ForegroundColor Gray
    }
    else {
        Write-Host "   - Attempting to create Junction (No Admin required)..."
        # 使用 Junction 而非 SymbolicLink，通常不需要管理員權限
        cmd /c mklink /j "$GeminiSkillPath" "$SkillSource"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   - Skill linked successfully via Junction." -ForegroundColor Green
        }
        else {
            Write-Warning "   - Link failed. You may need to manually copy .skills\dynamo-automation to your AI tools skill folder."
        }
    }
}

# 4. 註冊 MCP 伺服器 (範例：Claude Desktop)
Write-Host "`n[4/4] Registering MCP Server (Claude Desktop)..." -ForegroundColor Yellow
$ClaudeConfig = Join-Path $AppData "Claude\claude_desktop_config.json"
if (Test-Path $ClaudeConfig) {
    $config = Get-Content $ClaudeConfig | ConvertFrom-Json
    if (-not $config.mcpServers) { $config | Add-Member -MemberType NoteProperty -Name mcpServers -Value @{} }
    
    $ServerPath = Join-Path $PSScriptRoot "bridge\python\server.py"
    $config.mcpServers | Add-Member -MemberType NoteProperty -Name "dynamo-mcp" -Value @{
        command = "python"
        args    = @($ServerPath)
    } -Force
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $ClaudeConfig
    Write-Host "   - Registered 'dynamo-mcp' in Claude Desktop config." -ForegroundColor Green
}
else {
    Write-Host "   - Claude Desktop config not found, skipping registration." -ForegroundColor Gray
}

Write-Host "`n[OK] Setup Complete!" -ForegroundColor Green
Write-Host "Next Steps:"
Write-Host "1. Restart your AI Agent / Claude Desktop."
Write-Host "2. Start Dynamo and ensure 'BIM Assistant -> Connected' status is visible in the menu."
Write-Host "3. Run 'analyze_workspace' to verify."
