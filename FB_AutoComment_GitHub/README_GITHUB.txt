# FB Auto Comment Android — GitHub Actions

## Build APK trên GitHub, không cần Linux/WSL trên PC

1. Tạo GitHub repository và để Private nếu muốn giữ source kín.
2. Upload toàn bộ các file/thư mục trong project này.
3. Vào tab **Actions**.
4. Chọn **Build Android APK** / **Build APK**.
5. Bấm **Run workflow**.
6. Khi chạy xong, mở workflow thành công và tải artifact **android-apk**.

Workflow tự dùng Ubuntu của GitHub để chạy Buildozer và tạo APK debug.

Lưu ý:
- Không đưa access token vào repository.
- Đây là APK debug để cài thử.
