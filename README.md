# 📷 無人機照片轉 KMZ 工具

一個簡單的網頁工具，可將帶有 GPS 資訊的無人機照片轉換為 Google Earth KMZ 檔案。

## 功能特色

- ✅ 支援多檔案上傳
- ✅ 自動提取 GPS 座標
- ✅ 支援 DJI 無人機拍攝方向
- ✅ 即時預覽與進度顯示
- ✅ 手機友善介面

## 使用方式

1. 上傳照片
2. 點擊轉換
3. 下載 KMZ 檔案

## 線上使用

🌐 [點此使用](https://你的網址.streamlit.app)

## 技術架構

- Python 3.11+
- Streamlit
- ExifRead
- PyKML
- Pillow

## 開發者

cyLiu | 2025.01
```

### 5.2 建立 .gitignore

在專案資料夾建立 `.gitignore`：
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# 虛擬環境
venv/
venv_slim/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Streamlit
.streamlit/secrets.toml