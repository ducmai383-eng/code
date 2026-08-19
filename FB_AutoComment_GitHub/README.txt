# FB Auto Comment Android

Đây là bản Android chuyển từ file Python desktop đã cung cấp.

## Chạy thử trên máy tính
Cài Python, Kivy và requests rồi:
    python main.py

## Build APK
Buildozer phù hợp nhất khi build trên Linux/WSL:
    pip install buildozer
    buildozer android debug

APK sau khi build thường nằm trong thư mục `bin/`.

## Lưu ý
- Bản Android thay CustomTkinter/Tkinter bằng Kivy.
- Token, log và config được lưu trong thư mục dữ liệu riêng của ứng dụng.
- API Facebook vẫn phụ thuộc quyền và chính sách/API hiện hành.
- Không nên chia sẻ access token cho người khác.
