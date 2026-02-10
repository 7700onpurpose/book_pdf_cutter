import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import zipfile

def split_cover_image(uploaded_file, front_w, height_mm, spine_w, flap_w, bleed_mm):
    # 1. PDF 로드
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=300)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # 2. 픽셀 비율(Scale) 계산 방식 변경 (핵심 수정!)
    # 높이(Height)를 기준으로 비율을 잡는 것이 가장 정확합니다.
    # 인쇄용 PDF 높이 = 실제 책 높이 + (위아래 도련 * 2)
    total_height_mm = height_mm + (bleed_mm * 2)
    scale = img.height / total_height_mm
    
    # 3. 각 파트의 픽셀 너비 계산
    p_flap = flap_w * scale
    p_cover = front_w * scale
    p_spine = spine_w * scale
    p_bleed = bleed_mm * scale  # 도련 픽셀 크기
    
    # 4. 자르기 시작 위치 (x 좌표) 보정
    # 도련이 있다면, 0이 아니라 '왼쪽 도련'만큼 띄우고 시작해야 함
    
    # 전체 이미지 너비에서 '실제 책 너비 합계'를 뺀 나머지가 좌우 여백임.
    # PDF가 중앙 정렬되어 있다고 가정하고 시작점을 잡음.
    actual_content_width_px = (p_flap * 2) + (p_cover * 2) + p_spine
    if flap_w == 0: # 날개 없는 경우
         actual_content_width_px = (p_cover * 2) + p_spine
         
    # 시작점 x = (전체 이미지 폭 - 실제 책 내용 폭) / 2
    x = (img.width - actual_content_width_px) / 2
    
    height_px = img.height
    
    # 상하 도련(여백) 잘라내기 위한 y 좌표 설정
    y_top = p_bleed
    y_bottom = height_px - p_bleed
    
    # --- 자르기 시작 ---
    
    # (1) 뒷날개
    img_back_flap = None
    if flap_w > 0:
        img_back_flap = img.crop((x, y_top, x + p_flap, y_bottom))
        x += p_flap
        
    # (2) 뒷표지
    img_back = img.crop((x, y_top, x + p_cover, y_bottom))
    x += p_cover
    
    # (3) 세네카
    img_spine = img.crop((x, y_top, x + p_spine, y_bottom))
    x += p_spine
    
    # (4) 앞표지
    img_front = img.crop((x, y_top, x + p_cover, y_bottom))
    x += p_cover
    
    # (5) 앞날개
    img_front_flap = None
    if flap_w > 0:
        img_front_flap = img.crop((x, y_top, x + p_flap, y_bottom))
        
    return img_front, img_spine, img_back, img_front_flap, img_back_flap

# --- Streamlit UI ---
st.set_page_config(page_title="PDF 표지 분리기", layout="wide")
st.title("✂️ 인쇄용 PDF 표지 자동 분리기")
st.markdown("""
인쇄용 PDF(펼침면)를 업로드하면 **앞표지, 뒷표지, 세네카, 날개**로 정확하게 잘라줍니다.
도련(여백)이 있어도 자동으로 계산해서 알맹이만 남겨드립니다.
""")

col_input, col_preview = st.columns([1, 2])

with col_input:
    st.header("1. 사이즈 입력 (mm)")
    st.info("💡 종이책 실제 판형을 입력하세요.")
    width_mm = st.number_input("가로 (표지 1면)", value=150)
    height_mm = st.number_input("세로 (높이)", value=210)
    spine_mm = st.number_input("세네카 (책등)", value=15)
    flap_mm = st.number_input("날개 폭 (없으면 0)", value=100)
    
    st.write("---")
    st.header("2. 여백 설정")
    bleed_mm = st.number_input("사방 여백 (도련)", value=3.0, step=0.5, help="보통 인쇄소 파일은 사방 3mm 여백이 있습니다.")
    
    uploaded_pdf = st.file_uploader("PDF 파일 업로드", type=["pdf"])

if uploaded_pdf and width_mm > 0:
    with col_preview:
        st.header("3. 결과 확인")
        try:
            f, s, b, ff, bf = split_cover_image(uploaded_pdf, width_mm, height_mm, spine_mm, flap_mm, bleed_mm)
            
            # 탭으로 보기 좋게 정리
            tab1, tab2, tab3 = st.tabs(["펼쳐보기", "상세보기", "다운로드"])
            
            with tab1:
                st.caption("잘라낸 이미지를 나열한 모습입니다.")
                cols = st.columns([1, 1, 0.2, 1, 1] if flap_mm > 0 else [1, 0.2, 1])
                
                if flap_mm > 0:
                    cols[0].image(bf, caption="뒷날개", use_container_width=True)
                    cols[1].image(b, caption="뒷표지", use_container_width=True)
                    cols[2].image(s, caption="책등", use_container_width=True)
                    cols[3].image(f, caption="앞표지", use_container_width=True)
                    cols[4].image(ff, caption="앞날개", use_container_width=True)
                else:
                    cols[0].image(b, caption="뒷표지", use_container_width=True)
                    cols[1].image(s, caption="책등", use_container_width=True)
                    cols[2].image(f, caption="앞표지", use_container_width=True)

            with tab2:
                c1, c2, c3 = st.columns(3)
                c1.image(f, caption="앞표지 (확대)")
                c2.image(s, caption="세네카 (확대)")
                c3.image(b, caption="뒷표지 (확대)")

            with tab3:
                # ZIP 파일 생성
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    def save_to_zip(image, name):
                        img_byte = io.BytesIO()
                        image.save(img_byte, format="PNG")
                        zf.writestr(f"{name}.png", img_byte.getvalue())

                    save_to_zip(f, "front_cover")
                    save_to_zip(s, "spine")
                    save_to_zip(b, "back_cover")
                    if flap_mm > 0:
                        save_to_zip(ff, "front_flap")
                        save_to_zip(bf, "back_flap")

                st.download_button(
                    label="📦 모든 조각 ZIP 다운로드",
                    data=zip_buffer.getvalue(),
                    file_name="split_covers.zip",
                    mime="application/zip",
                    type="primary"
                )
                
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
            st.warning("PDF 파일의 크기가 입력하신 사이즈와 비율이 맞지 않을 수 있습니다. 도련(여백) 수치를 조절해보세요.")

elif not uploaded_pdf:
    with col_preview:
        st.info("👈 왼쪽에서 PDF 파일을 업로드해주세요.")
