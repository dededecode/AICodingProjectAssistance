# 打包初始数据：把当前数据库/向量库/上传文件放进 deploy/data_initial/，供 Docker 构建烧进镜像
# 在 Windows 上运行：powershell -ExecutionPolicy Bypass -File deploy\prepare_data.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot          # AICodingProjectAssistance/
$src  = Join-Path $root "backend"
$dst  = Join-Path $PSScriptRoot "data_initial"

New-Item -ItemType Directory -Force -Path $dst | Out-Null

foreach ($item in @("db.sqlite3", "chroma", "media")) {
    $s = Join-Path $src $item
    if (Test-Path $s) {
        $d = Join-Path $dst $item
        if (Test-Path $d) { Remove-Item $d -Recurse -Force }
        Write-Host "打包 $item -> $d"
        Copy-Item $s $d -Recurse
    } else {
        Write-Host "[跳过] 不存在: $s"
    }
}

Write-Host ""
Write-Host "完成。把整个 AICodingProjectAssistance/ 上传到服务器后执行:"
Write-Host "  cd AICodingProjectAssistance/deploy && docker compose up -d --build"
Write-Host ""
Write-Host "注意：打包包含数据库内的 LLM API Key，请勿公开该镜像/目录。"
