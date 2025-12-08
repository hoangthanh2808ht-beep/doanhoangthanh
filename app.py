import streamlit as st
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
import osmnx as ox
import folium
from folium.plugins import AntPath, Fullscreen
from streamlit_folium import st_folium
import warnings

# Tắt các cảnh báo hệ thống để màn hình sạch đẹp
warnings.filterwarnings("ignore")

# -----------------------------------------------------------------------------
# 1. CẤU HÌNH GIAO DIỆN 
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Hệ thống Dẫn đường Pleiku", layout="wide", page_icon="🗺️")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }

    /* Tiêu đề chính */
    h1 { color: #2C3E50; text-align: center; font-weight: 700; margin-bottom: 20px; text-transform: uppercase; }

    /* Trang trí các Tab */
    .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 20px; }
    .stTabs [data-baseweb="tab"] { background-color: #ECF0F1; border-radius: 10px; padding: 10px 20px; }
    .stTabs [aria-selected="true"] { background-color: #3498DB; color: white !important; font-weight: bold; }

    /* Khung hiển thị Lộ trình chi tiết */
    .khung-lo-trinh {
        background-color: #FFFFFF;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        padding: 20px;
        max-height: 600px;
        overflow-y: auto;
    }

    /* Các phần tử trong dòng thời gian (Timeline) */
    .dong-thoi-gian {
        display: flex;
        padding-bottom: 15px;
        position: relative;
    }
    .dong-thoi-gian::before {
        content: ''; position: absolute; left: 19px; top: 35px; bottom: 0; width: 2px; background-color: #E0E0E0;
    }
    .dong-thoi-gian:last-child::before { display: none; }

    .icon-moc {
        flex-shrink: 0; width: 40px; height: 40px; border-radius: 50%;
        background-color: #E8F6F3; color: #1ABC9C;
        display: flex; align-items: center; justify-content: center;
        font-weight: bold; margin-right: 15px; z-index: 1;
        border: 2px solid #1ABC9C;
    }

    .noi-dung-moc {
        flex-grow: 1; background-color: #F8F9F9; padding: 10px 15px;
        border-radius: 8px; border-left: 4px solid #BDC3C7;
    }
    .noi-dung-moc:hover { background-color: #F0F3F4; border-left-color: #3498DB; transition: 0.3s; }

    .ten-duong { font-weight: bold; color: #2C3E50; font-size: 1.05em; display: block; }
    .the-khoang-cach { float: right; font-size: 0.85em; color: #E74C3C; font-weight: bold; background: #FADBD8; padding: 2px 8px; border-radius: 10px; }

    /* Hộp thống kê */
    .hop-thong-ke {
        display: flex; justify-content: space-around;
        background: linear-gradient(135deg, #6DD5FA 0%, #2980B9 100%);
        color: white; padding: 15px; border-radius: 10px; margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(52, 152, 219, 0.3);
    }
    .muc-thong-ke { text-align: center; }
    .gia-tri-thong-ke { font-size: 1.5em; font-weight: bold; display: block; }
    </style>
    """, unsafe_allow_html=True)

# Khởi tạo Bộ nhớ đệm (Session State)
if 'do_thi' not in st.session_state: st.session_state['do_thi'] = nx.Graph()
if 'lo_trinh_tim_duoc' not in st.session_state: st.session_state['lo_trinh_tim_duoc'] = []
if 'chi_tiet_lo_trinh' not in st.session_state: st.session_state['chi_tiet_lo_trinh'] = []
if 'tam_ban_do' not in st.session_state: st.session_state['tam_ban_do'] = [13.9785, 108.0051]


# -----------------------------------------------------------------------------
# HÀM XỬ LÝ 1: TRÍCH XUẤT THÔNG TIN LỘ TRÌNH
# -----------------------------------------------------------------------------
def lay_du_lieu_canh_an_toan(G, u, v, khoa_trong_so='length'):
    """Lấy dữ liệu cạnh an toàn cho cả Graph thường và MultiGraph"""
    data = G.get_edge_data(u, v)
    if data is None: return {}
    # Nếu là MultiGraph (kết quả là dict của các cạnh {0: {}, 1: {}})
    if isinstance(data, dict) and any(isinstance(k, int) for k in data.keys()):
        best = None;
        min_w = float('inf')
        for key, attr in data.items():
            w = attr.get(khoa_trong_so, attr.get('weight', float('inf')))
            if w < min_w: min_w = w; best = attr
        return best or next(iter(data.values()))
    return data


def lay_thong_tin_lo_trinh(do_thi, danh_sach_nut):
    if not danh_sach_nut or len(danh_sach_nut) < 2: return []
    cac_buoc_di = []
    ten_duong_hien_tai = None;
    quang_duong_hien_tai = 0

    for u, v in zip(danh_sach_nut[:-1], danh_sach_nut[1:]):
        du_lieu_canh = lay_du_lieu_canh_an_toan(do_thi, u, v)
        do_dai = du_lieu_canh.get('length', 0)
        ten = du_lieu_canh.get('name', 'Đường nội bộ')
        if isinstance(ten, list): ten = ten[0]

        if ten == ten_duong_hien_tai:
            quang_duong_hien_tai += do_dai
        else:
            if ten_duong_hien_tai: cac_buoc_di.append({"ten": ten_duong_hien_tai, "do_dai": quang_duong_hien_tai})
            ten_duong_hien_tai = ten;
            quang_duong_hien_tai = do_dai

    if ten_duong_hien_tai: cac_buoc_di.append({"ten": ten_duong_hien_tai, "do_dai": quang_duong_hien_tai})
    return cac_buoc_di


# -----------------------------------------------------------------------------
# HÀM XỬ LÝ 2: VẼ ĐỒ THỊ LÝ THUYẾT (TAB 1)
# -----------------------------------------------------------------------------
def ve_do_thi_ly_thuyet(do_thi, duong_di=None, danh_sach_canh=None, tieu_de=""):
    is_directedđộng": (13.9788, 108.0042),
        "UBND Tỉnh Gia Lai": (13.9792, 108.0039),
        "Bưu điện Tỉnh": (13.9772, 108.0041), "Công an Tỉnh Gia Lai": (13.9778, 108.0025),
        "Bảo tàng Tỉnh Gia Lai": (13.9781, 108.0056),
        "Sở Giáo dục & Đào tạo": (13.9776, 108.0048), "Tỉnh ủy Gia Lai": (13.9805, 108.0045),
        "Sở Y Tế Gia Lai": (13.9765, 108.0035),
        "Quảng trường Đại Đoàn Kết": (13.9812, 108.0065), "Điện lực Gia Lai": (13.9755, 108.0040),
        "Trung tâm Văn hóa Thanh Thiếu Nhi": (13.9760, 108.0060),
        "--- GIAO THÔNG ---": (0, 0), "Sân bay Pleiku": (14.0050, 108.0180), "Bến xe Đức Long": (13.9556, 108.0264),
        "Ngã 3 Hoa Lư": (13.9855, 108.0052),
        "Ngã 4 Biển Hồ": (14.0010, 108.0005), "Ngã 3 Phù Đổng": (13.9705, 108.0055),
        "Vòng xoay HAGL": (13.9762, 108.0032), "Ngã 3 Diệp Kính": (13.9750, 108.0010),
        "Cầu Phan Đình Phùng": (13.9680, 107.9980), "Ngã 4 Lâm Nghiệp": (13.9650, 108.0200),
        "--- MUA SẮM ---": (0, 0), "Chợ Đêm Pleiku": (13.9745, 108.0068),
        "Trung tâm Thương mại Pleiku": (13.9752, 108.0082), "Chợ Thống Nhất": (13.9805, 108.0155),
        "Chợ Phù Đổng": (13.9705, 108.0105), "Chợ Hoa Lư": (13.9855, 108.0055), "Chợ Yên Thế": (13.9920, 108.0310),
        "Vincom Plaza Pleiku": (13.9804, 108.0053),
        "Coop Mart Pleiku": (13.9818, 108.0064), "Chợ Trà Bá": (13.9605, 108.0255),
        "Siêu thị Nguyễn Kim": (13.9720, 108.0060), "Thế Giới Di Động (Hùng Vương)": (13.9760, 108.0045),
        "--- DU LỊCH ---": (0, 0), "Biển Hồ (Tơ Nưng)": (14.0450, 108.0020), "Biển Hồ Chè": (14.0250, 108.0150),
        "Công viên Diên Hồng": (13.9715, 108.0022),
        "Công viên Đồng Xanh": (13.9805, 108.0550), "Sân vận động Pleiku": (13.9791, 108.0076),
        "Rạp Touch Cinema": (13.9702, 108.0102), "Học viện Bóng đá HAGL": (13.9450, 108.0520),
        "Làng Văn hóa Plei Ốp": (13.9825, 108.0085), "Quảng trường Sư đoàn 320": (13.9950, 108.0100),
        "Khu du lịch Về Nguồn": (13.9500, 108.0400),
        "--- TÔN GIÁO ---": (0, 0), "Chùa Minh Thành": (13.9685, 108.0105), "Chùa Bửu Minh": (14.0220, 108.0120),
        "Chùa Bửu Nghiêm": (13.9755, 108.0025),
        "Nhà thờ Đức An": (13.9752, 108.0052), "Nhà thờ Thăng Thiên": (13.9855, 108.0055),
        "Nhà thờ Plei Chuet": (13.9705, 108.0305), "Tòa Giám mục Kon Tum (VP Pleiku)": (13.9730, 108.0040),
        "Tịnh Xá Ngọc Phúc": (13.9650, 108.0150),
        "--- Y TẾ ---": (0, 0), "BV Đa khoa Tỉnh Gia Lai": (13.9822, 108.0019),
        "BV ĐH Y Dược HAGL": (13.9710, 108.0005), "BV Nhi Gia Lai": (13.9605, 108.0105),
        "BV Mắt Cao Nguyên": (13.9655, 108.0155), "BV Quân Y 211": (13.9880, 108.0050),
        "BV TP Pleiku": (13.9785, 108.0155), "Trung tâm Y tế Dự phòng": (13.9740, 108.0030),
        "--- GIÁO DỤC ---": (0, 0), "THPT Chuyên Hùng Vương": (13.9855, 108.0105), "THPT Pleiku": (13.9805, 108.0125),
        "THPT Phan Bội Châu": (13.9755, 108.0205),
        "THPT Lê Lợi": (13.9705, 108.0155), "THPT Hoàng Hoa Thám": (13.9905, 108.0105),
        "CĐ Sư phạm Gia Lai": (13.9605, 108.0205), "Phân hiệu ĐH Nông Lâm": (13.9555, 108.0305),
        "Trường Quốc tế UKA": (13.9855, 108.0205), "THCS Nguyễn Du": (13.9760, 108.0020),
        "THCS Phạm Hồng Thái": (13.9720, 108.0080),
        "--- KHÁCH SẠN ---": (0, 0), "KS Hoàng Anh Gia Lai": (13.9762, 108.0032), "KS Tre Xanh": (13.9790, 108.0060),
        "KS Khánh Linh": (13.9780, 108.0050),
        "KS Mê Kông": (13.9750, 108.0020), "KS Boston": (13.9720, 108.0050), "KS Pleiku & Em": (13.9770, 108.0080),
        "KS Elegant": (13.9740, 108.0035),
        "--- CÀ PHÊ & FOOD ---": (0, 0), "Cà phê Trung Nguyên (Hai Bà Trưng)": (13.9785, 108.0060),
        "Java Coffee": (13.9750, 108.0040), "Hani Kafe & Kitchen": (13.9680, 108.0120),
        "Phở Khô Ngọc Sơn": (13.9765, 108.0055), "Gà nướng Plei Tiêng": (13.9900, 107.9900),
        "Cơm lam Gà nướng (Hẻm 172)": (13.9850, 108.0200),
        "--- NGÂN HÀNG ---": (0, 0), "Vietcombank Gia Lai": (13.9765, 108.0035), "BIDV Nam Gia Lai": (13.9720, 108.0055),
        "Agribank Tỉnh": (13.9775, 108.0030), "MB Bank Gia Lai": (13.9780, 108.0070)
    }

    dia_diem_hop_le = {k: v for k, v in ds_dia_diem.items() if v != (0, 0)}

    # DÙNG FORM ĐỂ ỔN ĐỊNH
    with st.form("form_tim_duong"):
        c1, c2, c3 = st.columns([1.5, 1.5, 1])
        diem_bat_dau = c1.selectbox("📍 Điểm xuất phát:", list(dia_diem_hop_le.keys()), index=1)
        diem_ket_thuc = c2.selectbox("🏁 Điểm đến:", list(dia_diem_hop_le.keys()), index=8)
        thuat_toan_tim_duong = c3.selectbox("Thuật toán:", ["Dijkstra", "BFS", "DFS"])
        nut_tim_duong = st.form_submit_button("🚀 TÌM ĐƯỜNG NGAY", type="primary", use_container_width=True)

    if nut_tim_duong:
        try:
            u_coord, v_coord = dia_diem_hop_le[diem_bat_dau], dia_diem_hop_le[diem_ket_thuc]
            nut_goc = ox.distance.nearest_nodes(Do_thi_Pleiku, u_coord[1], u_coord[0])
            nut_dich = ox.distance.nearest_nodes(Do_thi_Pleiku, v_coord[1], v_coord[0])

            duong_di = []
            if "Dijkstra" in thuat_toan_tim_duong:
                duong_di = nx.shortest_path(Do_thi_Pleiku, nut_goc, nut_dich, weight='length')
            elif "BFS" in thuat_toan_tim_duong:
                duong_di = nx.shortest_path(Do_thi_Pleiku, nut_goc, nut_dich, weight=None)
            elif "DFS" in thuat_toan_tim_duong:
                try:
                    duong_di = next(nx.all_simple_paths(Do_thi_Pleiku, nut_goc, nut_dich, cutoff=30))
                except StopIteration:
                    st.warning("DFS không tìm thấy đường trong giới hạn độ sâu (cutoff=30). Đã chuyển sang BFS.")
                    duong_di = nx.shortest_path(Do_thi_Pleiku, nut_goc, nut_dich, weight=None)
                except Exception:
                    duong_di = []

            # Lưu vào session
            st.session_state['lo_trinh_tim_duoc'] = duong_di
            st.session_state['chi_tiet_lo_trinh'] = lay_thong_tin_lo_trinh(Do_thi_Pleiku, duong_di)
            st.session_state['tam_ban_do'] = [(u_coord[0] + v_coord[0]) / 2, (u_coord[1] + v_coord[1]) / 2]

        except Exception as e:
            st.error(f"Không tìm thấy đường đi: {e}")
            st.session_state['lo_trinh_tim_duoc'] = []

    if st.session_state['lo_trinh_tim_duoc']:
        duong_di = st.session_state['lo_trinh_tim_duoc']
        chi_tiet = st.session_state['chi_tiet_lo_trinh']
        tong_km = sum(d['do_dai'] for d in chi_tiet) / 1000

        st.markdown(f"""
        <div class="hop-thong-ke">
            <div class="muc-thong-ke"><div class="gia-tri-thong-ke">{tong_km:.2f} km</div><div class="nhan-thong-ke">Tổng quãng đường</div></div>
            <div class="muc-thong-ke"><div class="gia-tri-thong-ke">{len(chi_tiet)}</div><div class="nhan-thong-ke">Số đoạn đường</div></div>
            <div class="muc-thong-ke"><div class="gia-tri-thong-ke">{int(tong_km * 2)} phút</div><div class="nhan-thong-ke">Thời gian dự kiến</div></div>
        </div>
        """, unsafe_allow_html=True)

        cot_ban_do, cot_chi_tiet = st.columns([2, 1.2])

        with cot_chi_tiet:
            st.markdown("### 📋 Lộ trình chi tiết")
            with st.container():
                html_content = '<div class="khung-lo-trinh">'
                html_content += f'''
                <div class="dong-thoi-gian">
                    <div class="icon-moc" style="background:#D5F5E3; border-color:#2ECC71; color:#27AE60;">A</div>
                    <div class="noi-dung-moc"><span class="ten-duong">Bắt đầu: {dia_diem_hop_le.get(diem_bat_dau, diem_bat_dau)}</span></div>
                </div>'''

                for i, buoc in enumerate(chi_tiet):
                    html_content += f'''
                    <div class="dong-thoi-gian">
                        <div class="icon-moc">{i + 1}</div>
                        <div class="noi-dung-moc">
                            <span class="the-khoang-cach">{buoc['do_dai']:.0f} m</span>
                            <span class="ten-duong">{buoc['ten']}</span>
                        </div>
                    </div>'''

                html_content += f'''
                <div class="dong-thoi-gian">
                    <div class="icon-moc" style="background:#FADBD8; border-color:#E74C3C; color:#C0392B;">B</div>
                    <div class="noi-dung-moc"><span class="ten-duong">Đích đến: {dia_diem_hop_le.get(diem_ket_thuc, diem_ket_thuc)}</span></div>
                </div></div>'''
                st.markdown(html_content, unsafe_allow_html=True)

        with cot_ban_do:
            m = folium.Map(location=st.session_state['tam_ban_do'], zoom_start=14, tiles="OpenStreetMap") # Giao diện OpenStreetMap
            Fullscreen().add_to(m)

            # Marker A/B
            coord_start = dia_diem_hop_le.get(diem_bat_dau, (0, 0))
            coord_end = dia_diem_hop_le.get(diem_ket_thuc, (0, 0))
            if coord_start != (0, 0):
                folium.Marker(coord_start, icon=folium.Icon(color="green", icon="play", prefix='fa'),
                              popup="BẮT ĐẦU").add_to(m)
            if coord_end != (0, 0):
                folium.Marker(coord_end, icon=folium.Icon(color="red", icon="flag", prefix='fa'),
                              popup="KẾT THÚC").add_to(m)

            toa_do_duong_di = []
            nut_dau = Do_thi_Pleiku.nodes[duong_di[0]]
            toa_do_duong_di.append((nut_dau['y'], nut_dau['x']))

            for u, v in zip(duong_di[:-1], duong_di[1:]):
                canh = lay_du_lieu_canh_an_toan(Do_thi_Pleiku, u, v)
                if 'geometry' in canh:
                    xs, ys = canh['geometry'].xy
                    points = list(zip(ys, xs))
                    toa_do_duong_di.extend(points[1:])
                else:
                    nut_v = Do_thi_Pleiku.nodes[v]
                    toa_do_duong_di.append((nut_v['y'], nut_v['x']))

            mau_sac = "orange" if "DFS" in thuat_toan_tim_duong else (
                "purple" if "BFS" in thuat_toan_tim_duong else "#3498DB")
            # Hiệu ứng mờ mờ (AntPath)
            AntPath(toa_do_duong_di, color=mau_sac, weight=6, opacity=0.8, delay=1000).add_to(m)

            # Nét đứt nối vào
            if coord_start != (0, 0):
                folium.PolyLine([coord_start, toa_do_duong_di[0]], color="gray", weight=2, dash_array='5, 5').add_to(m)
            if coord_end != (0, 0):
                folium.PolyLine([coord_end, toa_do_duong_di[-1]], color="gray", weight=2, dash_array='5, 5').add_to(m)

            st_folium(m, width=900, height=600, returned_objects=[])

    # --- MẶC ĐỊNH KHI MỚI VÀO ---
    else:
        m = folium.Map(location=[13.9785, 108.0051], zoom_start=14, tiles="OpenStreetMap")
        st_folium(m, width=1200, height=600, returned_objects=[])
