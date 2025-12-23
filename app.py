import streamlit as st
import os
import zipfile
import io
from PIL import Image
import base64
import exifread
from fractions import Fraction
from pykml.factory import KML_ElementMaker as KML
from lxml import etree
import re

# 頁面設定
st.set_page_config(
    page_title="無人機照片轉KMZ",
    page_icon="📷",
    layout="centered"
)

# 自訂 CSS
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-size: 18px;
        font-weight: bold;
        padding: 0.75rem 2rem;
        border-radius: 10px;
        border: none;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
    .upload-text {
        text-align: center;
        padding: 2rem;
        border: 2px dashed #667eea;
        border-radius: 10px;
        background: #f8f9ff;
    }
</style>
""", unsafe_allow_html=True)

# 處理函數
def extract_exif_info(image_bytes):
    """提取 EXIF 資訊 - 使用 bytes 而非 file object"""
    try:
        # 從 bytes 建立 file-like object
        image_file = io.BytesIO(image_bytes)
        tags = exifread.process_file(image_file, details=False)
        
        if 'GPS GPSLatitude' not in tags or 'GPS GPSLongitude' not in tags:
            return None
        
        lat_ref = str(tags['GPS GPSLatitudeRef'])
        lon_ref = str(tags['GPS GPSLongitudeRef'])
        
        lat_components = [float(x.num) / float(x.den) for x in tags['GPS GPSLatitude'].values]
        lon_components = [float(x.num) / float(x.den) for x in tags['GPS GPSLongitude'].values]
        
        lat = lat_components[0] + lat_components[1] / 60 + lat_components[2] / 3600
        lon = lon_components[0] + lon_components[1] / 60 + lon_components[2] / 3600
        
        if lat_ref == 'S':
            lat = -lat
        if lon_ref == 'W':
            lon = -lon
        
        altitude = 0.0
        altitude_tag = tags.get('GPS GPSAltitude')
        if altitude_tag:
            altitude = float(altitude_tag.values[0].num) / float(altitude_tag.values[0].den)
        
        datetime_str = str(tags.get('Image DateTime', 'Unknown'))
        make = str(tags.get('Image Make', 'Unknown'))
        model = str(tags.get('Image Model', 'Unknown'))
        
        return {
            'datetime': datetime_str,
            'latitude': lat,
            'longitude': lon,
            'Altitude': altitude,
            'Make': make,
            'Model': model,
        }
    except Exception as e:
        st.error(f"讀取 EXIF 時發生錯誤: {str(e)}")
        return None

def extract_img_direction(image_bytes):
    """提取拍攝方向 - 從 XMP 或 EXIF"""
    try:
        # 方法 1: 從 XMP 讀取 GimbalYawDegree
        xmp_start = image_bytes.find(b'<x:xmpmeta')
        xmp_end = image_bytes.find(b'</x:xmpmeta>') + len(b'</x:xmpmeta>')
        
        if xmp_start != -1 and xmp_end != -1:
            xmp_content = image_bytes[xmp_start:xmp_end].decode('utf-8', errors='ignore')
            
            patterns = [
                r'drone-dji:GimbalYawDegree="([^"]+)"',
                r'GimbalYawDegree="([^"]+)"',
                r'<drone-dji:GimbalYawDegree>([^<]+)</drone-dji:GimbalYawDegree>',
                r'<GimbalYawDegree>([^<]+)</GimbalYawDegree>'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, xmp_content)
                if match:
                    value = float(match.group(1))
                    return round(value, 1)
    except Exception as e:
        pass
    
    # 方法 2: 從 EXIF 讀取 GPSImgDirection
    try:
        image_file = io.BytesIO(image_bytes)
        tags = exifread.process_file(image_file, details=False)
        
        if 'GPS GPSImgDirection' in tags:
            img_direction = tags['GPS GPSImgDirection'].values[0]
            img_direction_fraction = Fraction(img_direction)
            return round(float(img_direction_fraction), 1)
    except:
        pass
    
    return None

def create_kmz(photo_info_list):
    """建立 KMZ 檔案"""
    doc = KML.kml()
    kml_document = KML.Document()
    
    for info in photo_info_list:
        coordinates_str = f"{info['longitude']:.4f},{info['latitude']:.4f},{info['Altitude']:.1f}"
        img_direction = info.get('img_direction_decimal')
        
        if img_direction is None:
            heading_angle = 0.0
            icon_url = "http://maps.google.com/mapfiles/kml/shapes/camera.png"
        else:
            heading_angle = img_direction
            icon_url = "https://earth.google.com/images/kml-icons/track-directional/track-0.png"
        
        # 壓縮圖片
        img = Image.open(io.BytesIO(info['image_bytes']))
        img.thumbnail((1000, 1000))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG', quality=90)
        encoded_image = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        
        kml_placemark = KML.Placemark(
            KML.name(info['filename']),
            KML.Point(KML.coordinates(coordinates_str)),
            KML.Style(
                KML.IconStyle(
                    KML.Icon(KML.href(icon_url)),
                    KML.scale(1),
                    KML.heading(heading_angle),
                )
            ),
            KML.description(
                f"DateTime: {info['datetime']}<br>"
                f"經度 Longitude: {info['longitude']:.4f}<br>"
                f"緯度 Latitude: {info['latitude']:.4f}<br>"
                f"高度 Altitude: {info['Altitude']:.1f}m<br>"
                f"拍攝方向 Direction: {img_direction if img_direction else 'N/A'}°<br>"
                f"相機裝置: {info['Make']} {info['Model']}<br>"
                f"<img src='data:image/jpeg;base64,{encoded_image}' width='400'>"
            )
        )
        kml_document.append(kml_placemark)
    
    doc.append(kml_document)
    
    # 建立 KMZ
    kmz_buffer = io.BytesIO()
    with zipfile.ZipFile(kmz_buffer, 'w', zipfile.ZIP_DEFLATED) as kmz:
        kml_content = etree.tostring(doc, pretty_print=True)
        kmz.writestr('doc.kml', kml_content)
    
    kmz_buffer.seek(0)
    return kmz_buffer.getvalue()

# ==================== UI 介面 ====================

# 標題
st.markdown("<h1 style='text-align: center;'>📷 照片轉 KMZ 工具</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>上傳帶有 GPS 資訊的照片，自動產生 Google Earth KMZ 檔案</p>", unsafe_allow_html=True)
st.markdown("---")

# 使用說明（可摺疊）
with st.expander("📖 使用說明"):
    st.write("""
    1. 點擊下方按鈕上傳照片（支援多選）
    2. 照片必須包含 GPS 資訊（如手機或無人機拍攝的照片）
    3. 點擊「開始轉換」按鈕
    4. 下載產生的 KMZ 檔案
    5. 使用 Google Earth 開啟 KMZ 檔案查看照片位置
    
    **支援格式：** JPG, JPEG, PNG
    """)

# 檔案上傳
uploaded_files = st.file_uploader(
    "選擇照片（可多選）",
    type=['jpg', 'jpeg', 'png', 'JPG', 'JPEG', 'PNG'],
    accept_multiple_files=True,
    help="選擇一張或多張包含 GPS 資訊的照片"
)

if uploaded_files:
    st.success(f"✅ 已選擇 {len(uploaded_files)} 張照片")
    
    # 顯示照片縮圖（前3張）
    cols = st.columns(min(3, len(uploaded_files)))
    for i, (col, file) in enumerate(zip(cols, uploaded_files[:3])):
        with col:
            img = Image.open(file)
            st.image(img, caption=file.name, use_container_width=True)
            file.seek(0)  # 重設檔案指標
    
    if len(uploaded_files) > 3:
        st.info(f"還有 {len(uploaded_files) - 3} 張照片...")
    
    st.markdown("---")
    
    # 輸出檔名設定
    output_filename = st.text_input(
        "輸出檔名（不含副檔名）",
        value="photos",
        help="KMZ 檔案的名稱"
    )
    
    # 處理按鈕
    if st.button("🚀 開始轉換", type="primary", use_container_width=True):
        
        # 進度條
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        photo_info_list = []
        skipped_files = []
        
        # 處理每張照片
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"處理中... ({i+1}/{len(uploaded_files)}) - {uploaded_file.name}")
            progress_bar.progress((i + 1) / len(uploaded_files))
            
            # ========== 關鍵修改：先讀取所有 bytes ==========
            image_bytes = uploaded_file.read()
            
            # 提取 EXIF（使用 bytes）
            exif_info = extract_exif_info(image_bytes)
            
            if exif_info:
                # 提取拍攝方向（使用相同的 bytes）
                img_direction = extract_img_direction(image_bytes)
                
                # 除錯資訊（可選）
                if img_direction:
                    status_text.text(f"✓ {uploaded_file.name} - 方向: {img_direction}°")
                else:
                    status_text.text(f"⚠ {uploaded_file.name} - 無方向資訊")
                
                exif_info['filename'] = uploaded_file.name
                exif_info['img_direction_decimal'] = img_direction
                exif_info['image_bytes'] = image_bytes
                photo_info_list.append(exif_info)
            else:
                skipped_files.append(uploaded_file.name)
        
        # 顯示跳過的檔案
        if skipped_files:
            with st.expander(f"⚠️ {len(skipped_files)} 張照片沒有 GPS 資訊，已跳過"):
                for filename in skipped_files:
                    st.write(f"- {filename}")
        
        # 如果有有效照片，產生 KMZ
        if photo_info_list:
            status_text.text("正在產生 KMZ 檔案...")
            
            try:
                # 建立 KMZ
                kmz_data = create_kmz(photo_info_list)
                
                status_text.empty()
                progress_bar.empty()
                
                st.success(f"✅ 轉換完成！成功處理 {len(photo_info_list)} 張照片")
                
                # 統計有方向資訊的照片
                with_direction = sum(1 for info in photo_info_list if info.get('img_direction_decimal') is not None)
                if with_direction > 0:
                    st.info(f"📐 {with_direction} 張照片包含拍攝方向資訊")
                
                # 下載按鈕
                st.download_button(
                    label="📥 下載 KMZ 檔案",
                    data=kmz_data,
                    file_name=f"{output_filename}.kmz",
                    mime="application/vnd.google-earth.kmz",
                    type="primary",
                    use_container_width=True
                )
                
                # 顯示摘要
                with st.expander("📊 查看詳細資訊"):
                    for info in photo_info_list:
                        st.markdown(f"**{info['filename']}**")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"📍 經度: {info['longitude']:.6f}")
                            st.write(f"📍 緯度: {info['latitude']:.6f}")
                        with col2:
                            st.write(f"⬆️ 高度: {info['Altitude']:.1f}m")
                            direction = info.get('img_direction_decimal')
                            if direction:
                                st.write(f"🧭 方向: {direction}°")
                            else:
                                st.write(f"🧭 方向: N/A")
                        st.markdown("---")
                
            except Exception as e:
                st.error(f"❌ 產生 KMZ 時發生錯誤: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                status_text.empty()
                progress_bar.empty()
        else:
            status_text.empty()
            progress_bar.empty()
            st.error("❌ 沒有找到包含 GPS 資訊的照片，請確認照片是否由無人機或具有 GPS 功能的相機拍攝")

else:
    # 提示訊息
    st.info("👆 請上傳照片開始使用")

# 底部資訊
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #999; font-size: 12px;'>
    <p>開發者: cyLiu | 開發日期: 2025.01</p>
    <p>適用於 DJI 無人機照片及其他包含 GPS 資訊的影像</p>
</div>
""", unsafe_allow_html=True)