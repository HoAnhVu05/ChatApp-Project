# Script PowerShell để đưa code lên GitHub
# Chạy bằng: powershell -ExecutionPolicy Bypass -File push.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     ĐƯA CODE LÊN GITHUB" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Chuyển đến thư mục script
Set-Location $PSScriptRoot

Write-Host "[1/4] Đang kiểm tra trạng thái git..." -ForegroundColor Yellow
git status
Write-Host ""

Write-Host "[2/4] Đang thêm các file vào staging..." -ForegroundColor Yellow
git add .
Write-Host ""

Write-Host "[3/4] Nhập mô tả cho commit:" -ForegroundColor Yellow
$commitMsg = Read-Host "Commit message (hoặc Enter để dùng mặc định)"
if ([string]::IsNullOrWhiteSpace($commitMsg)) {
    $commitMsg = "Update code"
}

Write-Host ""
Write-Host "Đang commit với message: $commitMsg" -ForegroundColor Yellow
git commit -m $commitMsg
Write-Host ""

Write-Host "[4/4] Đang đẩy lên GitHub..." -ForegroundColor Yellow
git push origin main
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "Hoàn tất!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Nhấn phím bất kỳ để thoát..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

