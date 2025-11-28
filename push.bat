@echo off
chcp 65001 >nul
echo ========================================
echo     ĐƯA CODE LÊN GITHUB
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Đang kiểm tra trạng thái git...
git status
echo.

echo [2/3] Đang thêm các file vào staging...
git add .
echo.

echo [3/3] Nhập mô tả cho commit (hoặc Enter để dùng mặc định):
set /p commit_msg="Commit message: "
if "%commit_msg%"=="" set commit_msg=Update code

echo.
echo Đang commit với message: %commit_msg%
git commit -m "%commit_msg%"
echo.

echo Đang đẩy lên GitHub...
git push origin main
echo.

echo ========================================
echo Hoàn tất!
echo ========================================
pause

