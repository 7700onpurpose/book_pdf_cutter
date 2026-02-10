import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import zipfile

def split_cover_image(uploaded_file, front_w, height_mm, spine_w, flap_w):
    # 1. PDF 파일을 이미지로 변환 (고해상도 300DPI)
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    page = doc.load_page(0)  # 첫 번째 페이지만 사용
    pix = page.get_pixmap(dpi=300)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # 2. 전체 너비 계산 (날개+뒷표지+세네카+앞표지+날개)
    # 일반적인 펼침면 순서: [뒷날개] - [뒷표지] - [세네카] - [앞표지] - [앞날개]
    # 만약 날개가 없다면 0을 입력받음
    total_mm = (flap_w * 2) + (front_w * 2) + spine_w
    
    # 3. 픽셀 변환 비율 계산 (이미지 실제 크기 / 사용자가 입력한 총 mm)
    # 이렇게 하면 도련(여백)이 포함되어 있어도 비율대로 정확히 잘립니다.
    scale = img.width / total_mm
    
    # 각 파트의 픽셀 너비 계산
    p_flap = flap_w * scale
    p_cover = front_w * scale
    p_spine = spine_w * scale
    
    # 4. 이미지 자르기 (Left, Top, Right, Bottom)
    height_px = img.height
    
    # 순서: 뒷날개 -> 뒷표지 -> 세네카 -> 앞표지 -> 앞날개
    x = 0
    
    # (1) 뒷날개 (Back Flap)
    img_back_flap = None
    if flap_w > 0:
        img_back_flap = img.crop((x, 0, x + p_flap, height_px))
        x += p_flap
        
    # (2) 뒷표지 (Back Cover)
    img_back = img.crop((x, 0, x + p_cover, height_px))
    x += p_cover
    
    # (3) 세네카 (Spine)
    img_spine = img.crop((x, 0, x + p_spine, height_px))
    x += p_spine
    
    # (4) 앞표지 (Front Cover)
    img_front = img.crop((x, 0, x + p_cover, height_px))
    x += p_cover
    
    # (5) 앞날개 (Front Flap)
    img_front_flap = None
    if flap_w > 0:
        img_front_flap = img.crop((x, 0, img.width, height_px)) # 남은 끝까지
        
    return img_front, img_spine, img_back, img_front_flap, img_back_flap

# --- Streamlit UI ---
st.title("✂️ PDF 표지 자동 분리기")
st.markdown("펼침 표지 PDF를 올리면 **[앞표지, 뒷표지, 세네카, 날개]**로 조각내서 PNG로 저장해 줍니다.")

# 1. 사이드바 설정
st.sidebar.header("📏 도서 사이즈 입력 (mm)")
width_mm = st.sidebar.number_input("가로 (앞표지 1면)", value=152)
height_mm = st.sidebar.number_input("세로", value=225)
spine_mm = st.sidebar.number_input("세네카 (책등)", value=20)
flap_mm = st.sidebar.number_input("날개 폭 (없으면 0)", value=100)

uploaded_pdf = st.file_uploader("PDF 펼침 표지 파일 업로드", type=["pdf"])

if uploaded_pdf and st.button("이미지 자르기 실행"):
    with st.spinner("PDF를 고화질 이미지로 변환하고 자르는 중..."):
        try:
            # 함수 실행
            f, s, b, ff, bf = split_cover_image(uploaded_pdf, width_mm, height_mm, spine_mm, flap_mm)
            
            # 결과 보여주기
            st.success("자르기 완료! 아래에서 확인하고 다운로드하세요.")
            
            col1, col2, col3 = st.columns([1, 0.2, 1])
            with col1:
                st.image(b, caption="뒷표지", use_container_width=True)
            with col2:
                st.image(s, caption="세네카", use_container_width=True)
            with col3:
                st.image(f, caption="앞표지", use_container_width=True)
                
            if flap_mm > 0:
                st.write("---")
                c4, c5 = st.columns(2)
                with c4: st.image(bf, caption="뒷날개", width=150)
                with c5: st.image(ff, caption="앞날개", width=150)

            # ZIP 파일 생성 및 다운로드 버튼
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                # 앞표지 저장
                img_byte = io.BytesIO()
                f.save(img_byte, format="PNG")
                zf.writestr("front_cover.png", img_byte.getvalue())
                
                # 세네카 저장
                img_byte = io.BytesIO()
                s.save(img_byte, format="PNG")
                zf.writestr("spine.png", img_byte.getvalue())
                
                # 뒷표지 저장
                img_byte = io.BytesIO()
                b.save(img_byte, format="PNG")
                zf.writestr("back_cover.png", img_byte.getvalue())

                if flap_mm > 0:
                    img_byte = io.BytesIO()
                    bf.save(img_byte, format="PNG")
                    zf.writestr("back_flap.png", img_byte.getvalue())
                    
                    img_byte = io.BytesIO()
                    ff.save(img_byte, format="PNG")
                    zf.writestr("front_flap.png", img_byte.getvalue())

            st.download_button(
                label="📦 모든 조각 한번에 다운로드 (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="split_covers.zip",
                mime="application/zip"
            )
            
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
            st.warning("입력한 사이즈 합계가 PDF 비율과 너무 다르거나, 파일에 문제가 있을 수 있습니다.")