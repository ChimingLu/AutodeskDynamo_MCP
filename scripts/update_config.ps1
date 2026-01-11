# ========================================
# MCP 配置檔案自動轉換工具
# ========================================
# 功能：將 mcp_config.template.jsonc (帶註解) 轉換為 mcp_config.json (無註解)
# 用途：允許使用者在模板中使用註解，同時生成程式可讀取的純 JSON

$ErrorActionPreference = "Stop"

# 定義路徑
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TemplateFile = Join-Path $ProjectRoot "mcp_config.template.jsonc"
$OutputFile = Join-Path $ProjectRoot "mcp_config.json"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "MCP 配置檔案轉換工具" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 檢查模板檔案是否存在
if (-not (Test-Path $TemplateFile)) {
    Write-Error "找不到模板檔案: $TemplateFile"
    exit 1
}

Write-Host "[1/3] 讀取配置模板..." -ForegroundColor Yellow
$Content = Get-Content $TemplateFile -Raw

Write-Host "[2/3] 移除註解..." -ForegroundColor Yellow
# 移除單行註解 (// ...)
$Content = $Content -replace '//.*', ''
# 移除多行註解 (/* ... */)
$Content = $Content -replace '/\*[\s\S]*?\*/', ''
# 移除尾隨逗號（JSON 不允許，但 JSONC 允許）
$Content = $Content -replace ',(\s*[}\]])', '$1'

Write-Host "[3/3] 驗證 JSON 格式..." -ForegroundColor Yellow
try {
    # 驗證 JSON 格式是否正確
    $JsonObject = $Content | ConvertFrom-Json
    
    # 格式化輸出（美化 JSON）
    $FormattedJson = $JsonObject | ConvertTo-Json -Depth 10
    
    # 寫入檔案
    $FormattedJson | Set-Content $OutputFile -Encoding UTF8
    
    Write-Host "`n✅ 成功生成: $OutputFile" -ForegroundColor Green
    Write-Host "   - 已移除所有註解" -ForegroundColor Gray
    Write-Host "   - JSON 格式驗證通過" -ForegroundColor Gray
    
}
catch {
    Write-Error "JSON 格式驗證失敗: $_"
    Write-Host "`n請檢查模板檔案的 JSON 語法是否正確" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "轉換完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
