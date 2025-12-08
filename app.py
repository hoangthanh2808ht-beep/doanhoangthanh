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
# 1. CẤU HÌNH GIAO DIỆN & TRANG TRÍ (CSS)
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
# HÀM XỬ LÝ 1: TRÍCH XUẤT THÔNG TIN LỘ TRÌNH (AN TOÀN HƠN)
# -----------------------------------------------------------------------------
def lay_du_lieu_canh_an_toan(G, u, v, khoa_trong_so='length'):
    """Lấy dữ liệu cạnh an toàn cho cả Graph thường và MultiGraph"""
    data = G.get_edge_data(u, v)
    if data is None: return {}
    # Nếu là MultiGraph (kết quả là dict của các cạnh {0: {}, 1: {}})
    if isinstance(data, dict) and any(isinstance(k, int) for k in data.keys()):
        best = None; min_w = float('inf')
        for key, attr in data.items():
            w = attr.get(khoa_trong_so, attr.get('weight', float('inf')))
            if w < min_w: min_w = w; best = attr
        return best or next(iter(data.values()))
    return data 

def lay_thong_tin_lo_trinh(do_thi, danh_sach_nut):
    if not danh_sach_nut or len(danh_sach_nut) < 2: return []
    cac_buoc_di = []
    ten_duong_hien_tai = None; quang_duong_hien_tai = 0

    for u, v in zip(danh_sach_nut[:-1], danh_sach_nut[1:]):
        du_lieu_canh = lay_du_lieu_canh_an_toan(do_thi, u, v)
        do_dai = du_lieu_canh.get('length', 0)
        ten = du_lieu_canh.get('name', 'Đường nội bộ')
        if isinstance(ten, list): ten = ten[0]

        if ten == ten_duong_hien_tai: quang_duong_hien_tai += do_dai
        else:
            if ten_duong_hien_tai: cac_buoc_di.append({"ten": ten_duong_hien_tai, "do_dai": quang_duong_hien_tai})
            ten_duong_hien_tai = ten; quang_duong_hien_tai = do_dai

    if ten_duong_hien_tai: cac_buoc_di.append({"ten": ten_duong_hien_tai, "do_dai": quang_duong_hien_tai})
    return cac_buoc_di


# -----------------------------------------------------------------------------
# HÀM XỬ LÝ 2: VẼ ĐỒ THỊ LÝ THUYẾT (TAB 1)
# -----------------------------------------------------------------------------
def ve_do_thi_ly_thuyet(do_thi, duong_di=None, danh_sach_canh=None, tieu_de=""):
    is_directed = do_thi.is_directed()
    
    hinh_ve, truc = plt.subplots(figsize=(8, 5))
    try:
        vi_tri = nx.spring_layout(do_thi, seed=42)
        # Thêm tham số arrows=is_directed
        nx.draw(do_thi, vi_tri, with_labels=True, node_color='#D6EAF8', edge_color='#BDC3C7', node_size=600,
                font_weight='bold', ax=truc, arrows=is_directed) 
        nhan_canh = nx.get_edge_attributes(do_thi, 'weight')
        nx.draw_networkx_edge_labels(do_thi, vi_tri, edge_labels=nhan_canh, font_size=9, ax=truc)

        if duong_di:
            canh_duong_di = list(zip(duong_di, duong_di[1:]))
            nx.draw_networkx_nodes(do_thi, vi_tri, nodelist=duong_di, node_color='#E74C3C', node_size=700, ax=truc)
            nx.draw_networkx_edges(do_thi, vi_tri, edgelist=canh_duong_di, width=3, edge_color='#E74C3C', ax=truc, arrows=is_directed)

        if danh_sach_canh:
            nx.draw_networkx_edges(do_thi, vi_tri, edgelist=danh_sach_canh, width=3, edge_color='#27AE60', ax=truc, arrows=is_directed)
    except Exception as e: st.error(f"Lỗi vẽ hình: {e}")

    truc.set_title(tieu_de, color="#2C3E50", fontsize=12)
    st.pyplot(hinh_ve)

# -----------------------------------------------------------------------------
# HÀM XỬ LÝ 3: THUẬT TOÁN FLEURY
# -----------------------------------------------------------------------------
def thuat_toan_fleury(G_input):
    """
    Cài đặt thuật toán Fleury (Fix lỗi Bridge Check bằng has_path):
    """
    G = G_input.copy()
    bac_le = [v for v, d in G.degree() if d % 2 == 1]
    if len(bac_le) not in [0, 2]:
        return None, "Đồ thị không có Đường đi/Chu trình Euler (Số đỉnh bậc lẻ phải là 0 hoặc 2)."
    
    u = bac_le[0] if len(bac_le) == 2 else list(G.nodes())[0]
    path = [u]
    edges_path = []
    
    while G.number_of_edges() > 0:
        neighbors = list(G.neighbors(u))
        if not neighbors: return None, "Lỗi: Đồ thị bị ngắt quãng."

        next_v = None
        for v in neighbors:
            if G.degree(u) == 1:
                next_v = v; break
            
            G.remove_edge(u, v)
            if nx.has_path(G, u, v): # Check đường đi thay vì check liên thông toàn cục
                next_v = v
                G.add_edge(u, v)
                break
            else:
                G.add_edge(u, v, weight=1)
        
        if next_v is None: next_v = neighbors[0]
        
        if G.has_edge(u, next_v):
            G.remove_edge(u, next_v)
            edges_path.append((u, next_v))
            path.append(next_v)
            u = next_v
        
    return edges_path, "Thành công"

# -----------------------------------------------------------------------------
# HÀM HỖ TRỢTRỢ
# -----------------------------------------------------------------------------
def them_cac_nut_len_ban_do(ban_do, do_thi):
    # Vẽ các chấm tròn màu xám (Nodes)
    for node, data in do_thi.nodes(data=True):
        folium.CircleMarker(
            location=[data['y'], data['x']],
            radius=1.5,          # Kích thước chấm nhỏ
            color="gray",        # Viền xám
            fill=True,
            fill_color="#555",   # Màu bên trong xám đậm
            fill_opacity=0.6,
            weight=0.5,
            popup=f"Node ID: {node}"
        ).add_to(ban_do)

# -----------------------------------------------------------------------------
# GIAO DIỆN CHÍNH CỦA ỨNG DỤNG
# -----------------------------------------------------------------------------
st.title("🏙️ ỨNG DỤNG THUẬT TOÁN CHO HỆ THỐNG DẪN ĐƯỜNG TP. PLEIKU")

tab_ly_thuyet, tab_ban_do = st.tabs(["📚 PHẦN 1: LÝ THUYẾT ĐỒ THỊ", "🚀 PHẦN 2: BẢN ĐỒ THỰC TẾ"])

# =============================================================================
# TAB 1: LÝ THUYẾT
# =============================================================================
with tab_ly_thuyet:
    cot_trai, cot_phai = st.columns([1, 1.5])

    with cot_trai:
        st.subheader("🛠️ Cấu hình Đồ thị")
        loai_do_thi = st.radio("Chọn loại:", ["Vô hướng", "Có hướng"], horizontal=True)
        co_huong = True if loai_do_thi == "Có hướng" else False
        
        # Dữ liệu mặc định cho đồ thị
        mac_dinh = "A B 4\nA C 2\nB C 5\nB D 10\nC E 3\nD F 11\nE D 4\nC D 1"
        du_lieu_nhap = st.text_area("Nhập danh sách cạnh (u v w):", mac_dinh, height=150)

        c_nut_tao, c_nut_luu = st.columns([1, 1])
        with c_nut_tao:
            if st.button("🚀 Khởi tạo", use_container_width=True):
                try:
                    G_moi = nx.DiGraph() if co_huong else nx.Graph()
                    for dong in du_lieu_nhap.split('\n'):
                        phan = dong.split()
                        if len(phan) >= 2: # Ít nhất phải có 2 đỉnh u, v
                            u, v = phan[0], phan[1]
                            trong_so = int(phan[2]) if len(phan) > 2 else 1 
                            G_moi.add_edge(u, v, weight=trong_so)
                    
                    st.session_state['do_thi'] = G_moi
                    st.success("Tạo thành công!")
                except ValueError: st.error("Lỗi: Trọng số phải là số nguyên!")
                except Exception as e: st.error(f"Lỗi dữ liệu: {e}")
        
        # --- NÚT LƯU ĐỒ THỊ ---
        with c_nut_luu:
            st.download_button(
                label="💾 Lưu đồ thị (.txt)",
                data=du_lieu_nhap,
                file_name="graph_data.txt",
                mime="text/plain",
                use_container_width=True
            )

    with cot_phai:
        if len(st.session_state['do_thi']) > 0:
            ve_do_thi_ly_thuyet(st.session_state['do_thi'], tieu_de="Hình ảnh trực quan")

    if len(st.session_state['do_thi']) > 0:
        st.divider()
        c1, c2, c3 = st.columns(3)

        # Cột 1: Biểu diễn (YC 5, 6)
        with c1:
            st.info("1. Biểu diễn dữ liệu ")
            dang_xem = st.selectbox("Chọn cách xem:", ["Danh sách kề", "Ma trận kề", "Danh sách cạnh"])
            if dang_xem == "Ma trận kề":
                df = pd.DataFrame(nx.adjacency_matrix(st.session_state['do_thi']).todense(),
                                  index=st.session_state['do_thi'].nodes(), columns=st.session_state['do_thi'].nodes())
                st.dataframe(df, height=150)
            elif dang_xem == "Danh sách kề": st.json(nx.to_dict_of_lists(st.session_state['do_thi']), expanded=False)
            else: st.write(list(st.session_state['do_thi'].edges(data=True)))

            if st.button("Kiểm tra 2 phía (Bipartite)"):
                kq = nx.is_bipartite(st.session_state['do_thi'])
                st.write(f"Kết quả: {'✅ Có' if kq else '❌ Không'}")

        # Cột 2: Thuật toán tìm kiếm (YC 3, 4)
        with c2:
            st.warning("2. Thuật toán Tìm kiếm ")
            nut_bat_dau = st.selectbox("Điểm bắt đầu:", list(st.session_state['do_thi'].nodes()))
            nut_ket_thuc = st.selectbox("Điểm kết thúc:", list(st.session_state['do_thi'].nodes()),
                                                  index=len(st.session_state['do_thi'].nodes()) - 1)
            
            c2a, c2b = st.columns(2)
            with c2a:
                if st.button("Chạy BFS"):
                    try: 
                        duong_bfs = list(nx.bfs_tree(st.session_state['do_thi'], nut_bat_dau).nodes())
                        ve_do_thi_ly_thuyet(st.session_state['do_thi'], duong_di=duong_bfs, tieu_de="Duyệt BFS")
                    except: st.error("Lỗi chạy BFS")
            with c2b:
                if st.button("Chạy DFS"):
                    duong_dfs = list(nx.dfs_preorder_nodes(st.session_state['do_thi'], nut_bat_dau))
                    ve_do_thi_ly_thuyet(st.session_state['do_thi'], duong_di=duong_dfs, tieu_de="Duyệt DFS")

            if st.button("Chạy Dijkstra (Ngắn nhất)"):
                try:
                    duong_ngan_nhat = nx.shortest_path(st.session_state['do_thi'], nut_bat_dau, nut_ket_thuc, weight='weight')
                    ve_do_thi_ly_thuyet(st.session_state['do_thi'], duong_di=duong_ngan_nhat, tieu_de="Đường đi ngắn nhất (Dijkstra)")
                except: st.error("Không tìm thấy đường đi!")

        # Cột 3: Nâng cao (YC 7.1 -> 7.5)
        with c3:
            st.success("3. Thuật toán Nâng cao ")
            cot_k1, cot_k2 = st.columns(2)

            # 7.1 & 7.2: Cây khung
            with cot_k1:
                if st.button(" Prim"):
                    if not co_huong and nx.is_connected(st.session_state['do_thi']):
                        cay = nx.minimum_spanning_tree(st.session_state['do_thi'], algorithm='prim')
                        ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=list(cay.edges()),
                                            tieu_de=f"Prim MST (W={cay.size(weight='weight')})")
                    else: st.error("Lỗi: Chỉ áp dụng cho đồ thị Vô hướng & Liên thông")
            with cot_k2:
                if st.button(" Kruskal"):
                    if not co_huong and nx.is_connected(st.session_state['do_thi']):
                        cay = nx.minimum_spanning_tree(st.session_state['do_thi'], algorithm='kruskal')
                        ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=list(cay.edges()),
                                            tieu_de=f"Kruskal MST (W={cay.size(weight='weight')})")
                    else: st.error("Lỗi: Chỉ áp dụng cho đồ thị Vô hướng & Liên thông")
            
            # 7.3: Ford-Fulkerson (Max Flow)
            if st.button("Ford-Fulkerson"):
                is_directed_actual = st.session_state['do_thi'].is_directed()
                if is_directed_actual:
                    try:
                        val, flow_dict = nx.maximum_flow(st.session_state['do_thi'], nut_bat_dau, nut_ket_thuc, capacity='weight')
                        canh_luong = []
                        for u in flow_dict:
                            for v, f in flow_dict[u].items():
                                if f > 0: canh_luong.append((u, v))
                        ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=canh_luong, tieu_de=f"Luồng cực đại: {val}")
                    except Exception as e: st.error(f"Lỗi: {e}")
                else:
                    st.error("Lỗi: Đồ thị hiện tại là VÔ HƯỚNG. Hãy chọn 'Có hướng' và bấm 'Khởi tạo Đồ thị' lại.")
            
            # --- TÁCH RIÊNG 7.4 VÀ 7.5 ---
            st.divider()
            col_fleury, col_hierholzer = st.columns(2)

            # 7.4 FLEURY
            with col_fleury:
                if st.button("Fleury"):
                    if st.session_state['do_thi'].is_directed():
                        st.error("Fleury cơ bản chỉ áp dụng cho VÔ HƯỚNG để minh họa rõ nhất việc 'né cầu'.")
                    elif not nx.is_connected(st.session_state['do_thi']):
                        st.error("Đồ thị phải liên thông!")
                    else:
                        with st.spinner("Đang chạy Fleury (Né cầu)..."):
                            ds_canh, msg = thuat_toan_fleury(st.session_state['do_thi'])
                            if ds_canh:
                                st.info(f"Kết quả Fleury: {ds_canh}")
                                ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=ds_canh, tieu_de="Fleury (Né Cầu)")
                            else: st.error(msg)
            
            # 7.5 HIERHOLZER
            with col_hierholzer:
                if st.button("Hierholzer"):
                    try:
                        if nx.is_eulerian(st.session_state['do_thi']):
                            ct = list(nx.eulerian_circuit(st.session_state['do_thi']))
                            ds_canh = [(u,v) for u,v in ct]
                            st.success(f"Chu trình Euler (Hierholzer): {ds_canh}")
                            ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=ds_canh, tieu_de="Hierholzer Circuit")
                        else:
                            st.warning("Hierholzer chỉ tìm CHU TRÌNH (Circuit). Đồ thị này không có chu trình Euler.")
                    except Exception as e: st.error(f"Lỗi: {e}")

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
# 1. CẤU HÌNH GIAO DIỆN & TRANG TRÍ (CSS)
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
# HÀM XỬ LÝ 1: TRÍCH XUẤT THÔNG TIN LỘ TRÌNH (AN TOÀN HƠN)
# -----------------------------------------------------------------------------
def lay_du_lieu_canh_an_toan(G, u, v, khoa_trong_so='length'):
    """Lấy dữ liệu cạnh an toàn cho cả Graph thường và MultiGraph"""
    data = G.get_edge_data(u, v)
    if data is None: return {}
    # Nếu là MultiGraph (kết quả là dict của các cạnh {0: {}, 1: {}})
    if isinstance(data, dict) and any(isinstance(k, int) for k in data.keys()):
        best = None; min_w = float('inf')
        for key, attr in data.items():
            w = attr.get(khoa_trong_so, attr.get('weight', float('inf')))
            if w < min_w: min_w = w; best = attr
        return best or next(iter(data.values()))
    return data 

def lay_thong_tin_lo_trinh(do_thi, danh_sach_nut):
    if not danh_sach_nut or len(danh_sach_nut) < 2: return []
    cac_buoc_di = []
    ten_duong_hien_tai = None; quang_duong_hien_tai = 0

    for u, v in zip(danh_sach_nut[:-1], danh_sach_nut[1:]):
        du_lieu_canh = lay_du_lieu_canh_an_toan(do_thi, u, v)
        do_dai = du_lieu_canh.get('length', 0)
        ten = du_lieu_canh.get('name', 'Đường nội bộ')
        if isinstance(ten, list): ten = ten[0]

        if ten == ten_duong_hien_tai: quang_duong_hien_tai += do_dai
        else:
            if ten_duong_hien_tai: cac_buoc_di.append({"ten": ten_duong_hien_tai, "do_dai": quang_duong_hien_tai})
            ten_duong_hien_tai = ten; quang_duong_hien_tai = do_dai

    if ten_duong_hien_tai: cac_buoc_di.append({"ten": ten_duong_hien_tai, "do_dai": quang_duong_hien_tai})
    return cac_buoc_di


# -----------------------------------------------------------------------------
# HÀM XỬ LÝ 2: VẼ ĐỒ THỊ LÝ THUYẾT (TAB 1)
# -----------------------------------------------------------------------------
def ve_do_thi_ly_thuyet(do_thi, duong_di=None, danh_sach_canh=None, tieu_de=""):
    is_directed = do_thi.is_directed()
    
    hinh_ve, truc = plt.subplots(figsize=(8, 5))
    try:
        vi_tri = nx.spring_layout(do_thi, seed=42)
        # Thêm tham số arrows=is_directed
        nx.draw(do_thi, vi_tri, with_labels=True, node_color='#D6EAF8', edge_color='#BDC3C7', node_size=600,
                font_weight='bold', ax=truc, arrows=is_directed) 
        nhan_canh = nx.get_edge_attributes(do_thi, 'weight')
        nx.draw_networkx_edge_labels(do_thi, vi_tri, edge_labels=nhan_canh, font_size=9, ax=truc)

        if duong_di:
            canh_duong_di = list(zip(duong_di, duong_di[1:]))
            nx.draw_networkx_nodes(do_thi, vi_tri, nodelist=duong_di, node_color='#E74C3C', node_size=700, ax=truc)
            nx.draw_networkx_edges(do_thi, vi_tri, edgelist=canh_duong_di, width=3, edge_color='#E74C3C', ax=truc, arrows=is_directed)

        if danh_sach_canh:
            nx.draw_networkx_edges(do_thi, vi_tri, edgelist=danh_sach_canh, width=3, edge_color='#27AE60', ax=truc, arrows=is_directed)
    except Exception as e: st.error(f"Lỗi vẽ hình: {e}")

    truc.set_title(tieu_de, color="#2C3E50", fontsize=12)
    st.pyplot(hinh_ve)

# -----------------------------------------------------------------------------
# HÀM XỬ LÝ 3: THUẬT TOÁN FLEURY
# -----------------------------------------------------------------------------
def thuat_toan_fleury(G_input):
    """
    Cài đặt thuật toán Fleury (Fix lỗi Bridge Check bằng has_path):
    """
    G = G_input.copy()
    bac_le = [v for v, d in G.degree() if d % 2 == 1]
    if len(bac_le) not in [0, 2]:
        return None, "Đồ thị không có Đường đi/Chu trình Euler (Số đỉnh bậc lẻ phải là 0 hoặc 2)."
    
    u = bac_le[0] if len(bac_le) == 2 else list(G.nodes())[0]
    path = [u]
    edges_path = []
    
    while G.number_of_edges() > 0:
        neighbors = list(G.neighbors(u))
        if not neighbors: return None, "Lỗi: Đồ thị bị ngắt quãng."

        next_v = None
        for v in neighbors:
            if G.degree(u) == 1:
                next_v = v; break
            
            G.remove_edge(u, v)
            if nx.has_path(G, u, v): # Check đường đi thay vì check liên thông toàn cục
                next_v = v
                G.add_edge(u, v)
                break
            else:
                G.add_edge(u, v, weight=1)
        
        if next_v is None: next_v = neighbors[0]
        
        if G.has_edge(u, next_v):
            G.remove_edge(u, next_v)
            edges_path.append((u, next_v))
            path.append(next_v)
            u = next_v
        
    return edges_path, "Thành công"

# -----------------------------------------------------------------------------
# HÀM HỖ TRỢTRỢ
# -----------------------------------------------------------------------------
def them_cac_nut_len_ban_do(ban_do, do_thi):
    # Vẽ các chấm tròn màu xám (Nodes)
    for node, data in do_thi.nodes(data=True):
        folium.CircleMarker(
            location=[data['y'], data['x']],
            radius=1.5,          # Kích thước chấm nhỏ
            color="gray",        # Viền xám
            fill=True,
            fill_color="#555",   # Màu bên trong xám đậm
            fill_opacity=0.6,
            weight=0.5,
            popup=f"Node ID: {node}"
        ).add_to(ban_do)

# -----------------------------------------------------------------------------
# GIAO DIỆN CHÍNH CỦA ỨNG DỤNG
# -----------------------------------------------------------------------------
st.title("🏙️ ỨNG DỤNG THUẬT TOÁN CHO HỆ THỐNG DẪN ĐƯỜNG TP. PLEIKU")

tab_ly_thuyet, tab_ban_do = st.tabs(["📚 PHẦN 1: LÝ THUYẾT ĐỒ THỊ", "🚀 PHẦN 2: BẢN ĐỒ THỰC TẾ"])

# =============================================================================
# TAB 1: LÝ THUYẾT
# =============================================================================
with tab_ly_thuyet:
    cot_trai, cot_phai = st.columns([1, 1.5])

    with cot_trai:
        st.subheader("🛠️ Cấu hình Đồ thị")
        loai_do_thi = st.radio("Chọn loại:", ["Vô hướng", "Có hướng"], horizontal=True)
        co_huong = True if loai_do_thi == "Có hướng" else False
        
        # Dữ liệu mặc định cho đồ thị
        mac_dinh = "A B 4\nA C 2\nB C 5\nB D 10\nC E 3\nD F 11\nE D 4\nC D 1"
        du_lieu_nhap = st.text_area("Nhập danh sách cạnh (u v w):", mac_dinh, height=150)

        c_nut_tao, c_nut_luu = st.columns([1, 1])
        with c_nut_tao:
            if st.button("🚀 Khởi tạo", use_container_width=True):
                try:
                    G_moi = nx.DiGraph() if co_huong else nx.Graph()
                    for dong in du_lieu_nhap.split('\n'):
                        phan = dong.split()
                        if len(phan) >= 2: # Ít nhất phải có 2 đỉnh u, v
                            u, v = phan[0], phan[1]
                            trong_so = int(phan[2]) if len(phan) > 2 else 1 
                            G_moi.add_edge(u, v, weight=trong_so)
                    
                    st.session_state['do_thi'] = G_moi
                    st.success("Tạo thành công!")
                except ValueError: st.error("Lỗi: Trọng số phải là số nguyên!")
                except Exception as e: st.error(f"Lỗi dữ liệu: {e}")
        
        # --- NÚT LƯU ĐỒ THỊ ---
        with c_nut_luu:
            st.download_button(
                label="💾 Lưu đồ thị (.txt)",
                data=du_lieu_nhap,
                file_name="graph_data.txt",
                mime="text/plain",
                use_container_width=True
            )

    with cot_phai:
        if len(st.session_state['do_thi']) > 0:
            ve_do_thi_ly_thuyet(st.session_state['do_thi'], tieu_de="Hình ảnh trực quan")

    if len(st.session_state['do_thi']) > 0:
        st.divider()
        c1, c2, c3 = st.columns(3)

        # Cột 1: Biểu diễn (YC 5, 6)
        with c1:
            st.info("1. Biểu diễn dữ liệu ")
            dang_xem = st.selectbox("Chọn cách xem:", ["Danh sách kề", "Ma trận kề", "Danh sách cạnh"])
            if dang_xem == "Ma trận kề":
                df = pd.DataFrame(nx.adjacency_matrix(st.session_state['do_thi']).todense(),
                                  index=st.session_state['do_thi'].nodes(), columns=st.session_state['do_thi'].nodes())
                st.dataframe(df, height=150)
            elif dang_xem == "Danh sách kề": st.json(nx.to_dict_of_lists(st.session_state['do_thi']), expanded=False)
            else: st.write(list(st.session_state['do_thi'].edges(data=True)))

            if st.button("Kiểm tra 2 phía (Bipartite)"):
                kq = nx.is_bipartite(st.session_state['do_thi'])
                st.write(f"Kết quả: {'✅ Có' if kq else '❌ Không'}")

        # Cột 2: Thuật toán tìm kiếm (YC 3, 4)
        with c2:
            st.warning("2. Thuật toán Tìm kiếm ")
            nut_bat_dau = st.selectbox("Điểm bắt đầu:", list(st.session_state['do_thi'].nodes()))
            nut_ket_thuc = st.selectbox("Điểm kết thúc:", list(st.session_state['do_thi'].nodes()),
                                                  index=len(st.session_state['do_thi'].nodes()) - 1)
            
            c2a, c2b = st.columns(2)
            with c2a:
                if st.button("Chạy BFS"):
                    try: 
                        duong_bfs = list(nx.bfs_tree(st.session_state['do_thi'], nut_bat_dau).nodes())
                        ve_do_thi_ly_thuyet(st.session_state['do_thi'], duong_di=duong_bfs, tieu_de="Duyệt BFS")
                    except: st.error("Lỗi chạy BFS")
            with c2b:
                if st.button("Chạy DFS"):
                    duong_dfs = list(nx.dfs_preorder_nodes(st.session_state['do_thi'], nut_bat_dau))
                    ve_do_thi_ly_thuyet(st.session_state['do_thi'], duong_di=duong_dfs, tieu_de="Duyệt DFS")

            if st.button("Chạy Dijkstra (Ngắn nhất)"):
                try:
                    duong_ngan_nhat = nx.shortest_path(st.session_state['do_thi'], nut_bat_dau, nut_ket_thuc, weight='weight')
                    ve_do_thi_ly_thuyet(st.session_state['do_thi'], duong_di=duong_ngan_nhat, tieu_de="Đường đi ngắn nhất (Dijkstra)")
                except: st.error("Không tìm thấy đường đi!")

        # Cột 3: Nâng cao (YC 7.1 -> 7.5)
        with c3:
            st.success("3. Thuật toán Nâng cao ")
            cot_k1, cot_k2 = st.columns(2)

            # 7.1 & 7.2: Cây khung
            with cot_k1:
                if st.button(" Prim"):
                    if not co_huong and nx.is_connected(st.session_state['do_thi']):
                        cay = nx.minimum_spanning_tree(st.session_state['do_thi'], algorithm='prim')
                        ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=list(cay.edges()),
                                            tieu_de=f"Prim MST (W={cay.size(weight='weight')})")
                    else: st.error("Lỗi: Chỉ áp dụng cho đồ thị Vô hướng & Liên thông")
            with cot_k2:
                if st.button(" Kruskal"):
                    if not co_huong and nx.is_connected(st.session_state['do_thi']):
                        cay = nx.minimum_spanning_tree(st.session_state['do_thi'], algorithm='kruskal')
                        ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=list(cay.edges()),
                                            tieu_de=f"Kruskal MST (W={cay.size(weight='weight')})")
                    else: st.error("Lỗi: Chỉ áp dụng cho đồ thị Vô hướng & Liên thông")
            
            # 7.3: Ford-Fulkerson (Max Flow)
            if st.button("Ford-Fulkerson"):
                is_directed_actual = st.session_state['do_thi'].is_directed()
                if is_directed_actual:
                    try:
                        val, flow_dict = nx.maximum_flow(st.session_state['do_thi'], nut_bat_dau, nut_ket_thuc, capacity='weight')
                        canh_luong = []
                        for u in flow_dict:
                            for v, f in flow_dict[u].items():
                                if f > 0: canh_luong.append((u, v))
                        ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=canh_luong, tieu_de=f"Luồng cực đại: {val}")
                    except Exception as e: st.error(f"Lỗi: {e}")
                else:
                    st.error("Lỗi: Đồ thị hiện tại là VÔ HƯỚNG. Hãy chọn 'Có hướng' và bấm 'Khởi tạo Đồ thị' lại.")
            
            # --- TÁCH RIÊNG 7.4 VÀ 7.5 ---
            st.divider()
            col_fleury, col_hierholzer = st.columns(2)

            # 7.4 FLEURY
            with col_fleury:
                if st.button("Fleury"):
                    if st.session_state['do_thi'].is_directed():
                        st.error("Fleury cơ bản chỉ áp dụng cho VÔ HƯỚNG để minh họa rõ nhất việc 'né cầu'.")
                    elif not nx.is_connected(st.session_state['do_thi']):
                        st.error("Đồ thị phải liên thông!")
                    else:
                        with st.spinner("Đang chạy Fleury (Né cầu)..."):
                            ds_canh, msg = thuat_toan_fleury(st.session_state['do_thi'])
                            if ds_canh:
                                st.info(f"Kết quả Fleury: {ds_canh}")
                                ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=ds_canh, tieu_de="Fleury (Né Cầu)")
                            else: st.error(msg)
            
            # 7.5 HIERHOLZER
            with col_hierholzer:
                if st.button("Hierholzer"):
                    try:
                        if nx.is_eulerian(st.session_state['do_thi']):
                            ct = list(nx.eulerian_circuit(st.session_state['do_thi']))
                            ds_canh = [(u,v) for u,v in ct]
                            st.success(f"Chu trình Euler (Hierholzer): {ds_canh}")
                            ve_do_thi_ly_thuyet(st.session_state['do_thi'], danh_sach_canh=ds_canh, tieu_de="Hierholzer Circuit")
                        else:
                            st.warning("Hierholzer chỉ tìm CHU TRÌNH (Circuit). Đồ thị này không có chu trình Euler.")
                    except Exception as e: st.error(f"Lỗi: {e}")

# =============================================================================
# TAB 2: BẢN ĐỒ PLEIKU (100 ĐỊA ĐIỂM)
# =============================================================================
with tab_ban_do:
    @st.cache_resource
    def tai_ban_do_pleiku():
        return ox.graph_from_point((13.9800, 108.0000), dist=6000, network_type='drive')
    
    with st.spinner("Đang tải dữ liệu bản đồ TP. Pleiku (Khoảng 45 giây)..."):
        try:
            Do_thi_Pleiku = tai_ban_do_pleiku()
            st.success("✅ Đã tải xong bản đồ!")
        except:
            st.error("Lỗi tải bản đồ, vui lòng thử lại!")
            st.stop()

    # DANH SÁCH ~100 ĐỊA ĐIỂM
    ds_dia_diem = {
        "--- HÀNH CHÍNH ---": (0, 0), "Quảng trường Đại Đoàn Kết": (11.98355, 108.0057), "UBND Tỉnh Gia Lai": (13.9939, 108.0016),
        "Bưu điện Tỉnh": (13.9772, 108.0041), "Công an Tỉnh Gia Lai": (13.9778, 108.0025), "Bảo tàng Tỉnh Gia Lai": (13.9781, 108.0056),
        "Sở Giáo dục & Đào tạo": (13.9776, 108.0048), "Tỉnh ủy Gia Lai": (13.9805, 108.0045), "Sở Y Tế Gia Lai": (13.9765, 108.0035),
        "Nhà Thi đấu Tỉnh": (13.9809, 108.0043), "Điện lực Gia Lai": (13.9755, 108.0040), "Trung tâm Văn hóa Thanh Thiếu Nhi": (13.9760, 108.0060),
        "--- GIAO THÔNG ---": (0, 0), "Sân bay Pleiku": (14.0050, 108.0180), "Bến xe Đức Long": (13.9556, 108.0264), "Ngã 3 Hoa Lư": (13.9855, 108.0052),
        "Ngã 4 Biển Hồ": (14.0010, 108.0005), "Ngã 3 Phù Đổng": (13.9705, 108.0055), "Vòng xoay HAGL": (13.9762, 108.0032), "Ngã 3 Diệp Kính": (13.9750, 108.0010),
        "Cầu Phan Đình Phùng": (13.9680, 107.9980), "Ngã 4 Lâm Nghiệp": (13.9650, 108.0200),
        "--- MUA SẮM ---": (0, 0), "Chợ Đêm Pleiku": (13.9745, 108.0068), "Trung tâm Thương mại Pleiku": (13.9752, 108.0082), "Chợ Thống Nhất": (13.9805, 108.0155),
        "Chợ Phù Đổng": (13.9705, 108.0105), "Chợ Hoa Lư": (13.9855, 108.0055), "Chợ Yên Thế": (13.9920, 108.0310), "Vincom Plaza Pleiku": (13.9804, 108.0053),
        "Coop Mart Pleiku": (13.9818, 108.0064), "Chợ Trà Bá": (13.9605, 108.0255), "Siêu thị Nguyễn Kim": (13.9720, 108.0060), "Thế Giới Di Động (Hùng Vương)": (13.9760, 108.0045),
        "--- DU LỊCH ---": (0, 0), "Biển Hồ (Tơ Nưng)": (14.0450, 108.0020), "Biển Hồ Chè": (14.0250, 108.0150), "Công viên Diên Hồng": (13.9715, 108.0022),
        "Công viên Đồng Xanh": (13.9805, 108.0550), "Sân vận động Pleiku": (13.9791, 108.0076), "Rạp Touch Cinema": (13.9702, 108.0102), "Học viện Bóng đá HAGL": (13.9450, 108.0520),
        "Làng Văn hóa Plei Ốp": (13.9825, 108.0085), "Quảng trường Sư đoàn 320": (13.9950, 108.0100), "Khu du lịch Về Nguồn": (13.9500, 108.0400),
        "--- TÔN GIÁO ---": (0, 0), "Chùa Minh Thành": (13.9685, 108.0105), "Chùa Bửu Minh": (14.0220, 108.0120), "Chùa Bửu Nghiêm": (13.9755, 108.0025),
        "Nhà thờ Đức An": (13.9752, 108.0052), "Nhà thờ Thăng Thiên": (13.9855, 108.0055), "Nhà thờ Plei Chuet": (13.9705, 108.0305), "Tòa Giám mục Kon Tum (VP Pleiku)": (13.9730, 108.0040),
        "Tịnh Xá Ngọc Phúc": (13.9650, 108.0150),
        "--- Y TẾ ---": (0, 0), "BV Đa khoa Tỉnh Gia Lai": (13.9822, 108.0019), "BV ĐH Y Dược HAGL": (13.9710, 108.0005), "BV Nhi Gia Lai": (13.9605, 108.0105),
        "BV Mắt Cao Nguyên": (13.9655, 108.0155), "BV Quân Y 211": (13.9880, 108.0050), "BV TP Pleiku": (13.9785, 108.0155), "Trung tâm Y tế Dự phòng": (13.9740, 108.0030),
        "--- GIÁO DỤC ---": (0, 0), "THPT Chuyên Hùng Vương": (13.9855, 108.0105), "THPT Pleiku": (13.9805, 108.0125), "THPT Phan Bội Châu": (13.9755, 108.0205),
        "THPT Lê Lợi": (13.9705, 108.0155), "THPT Hoàng Hoa Thám": (13.9905, 108.0105), "CĐ Sư phạm Gia Lai": (13.9605, 108.0205), "Phân hiệu ĐH Nông Lâm": (13.9555, 108.0305),
        "Trường Quốc tế UKA": (13.9855, 108.0205), "THCS Nguyễn Du": (13.9760, 108.0020), "THCS Phạm Hồng Thái": (13.9720, 108.0080),
        "--- KHÁCH SẠN ---": (0, 0), "KS Hoàng Anh Gia Lai": (13.9762, 108.0032), "KS Tre Xanh": (13.9790, 108.0060), "KS Khánh Linh": (13.9780, 108.0050),
        "KS Mê Kông": (13.9750, 108.0020), "KS Boston": (13.9720, 108.0050), "KS Pleiku & Em": (13.9770, 108.0080), "KS Elegant": (13.9740, 108.0035),
        "--- CÀ PHÊ & FOOD ---": (0, 0), "Cà phê Trung Nguyên (Hai Bà Trưng)": (13.9785, 108.0060), "Java Coffee": (13.9750, 108.0040), "Hani Kafe & Kitchen": (13.9680, 108.0120),
        "Phở Khô Ngọc Sơn": (13.9765, 108.0055), "Gà nướng Plei Tiêng": (13.9900, 107.9900), "Cơm lam Gà nướng (Hẻm 172)": (13.9850, 108.0200),
        "--- NGÂN HÀNG ---": (0, 0), "Vietcombank Gia Lai": (13.9765, 108.0035), "BIDV Nam Gia Lai": (13.9720, 108.0055), "Agribank Tỉnh": (13.9775, 108.0030), "MB Bank Gia Lai": (13.9780, 108.0070)
    }

    dia_diem_hop_le = {k: v for k, v in ds_dia_diem.items() if v != (0, 0)}

    c_di, c_den, c_thuat_toan = st.columns([1.5, 1.5, 1])
    diem_bat_dau = c_di.selectbox("📍 Điểm xuất phát:", list(dia_diem_hop_le.keys()), index=1)
    diem_ket_thuc = c_den.selectbox("🏁 Điểm đến:", list(dia_diem_hop_le.keys()), index=8)
    thuat_toan_tim_duong = c_thuat_toan.selectbox("Thuật toán:", ["Dijkstra", "BFS", "DFS"])

    st.divider()

    # --- CHỈ CÒN NÚT TÌM ĐƯỜNG (BỎ QUY HOẠCH) ---
    nut_tim_duong = st.button("🚀 TÌM ĐƯỜNG NGAY", type="primary", use_container_width=True)

    # --- LOGIC TÌM ĐƯỜNG (A->B) ---
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

            st.session_state['lo_trinh_tim_duoc'] = duong_di
            st.session_state['chi_tiet_lo_trinh'] = lay_thong_tin_lo_trinh(Do_thi_Pleiku, duong_di)
            st.session_state['tam_ban_do'] = [(u_coord[0] + v_coord[0]) / 2, (u_coord[1] + v_coord[1]) / 2]

        except Exception as e:
            st.error(f"Không tìm thấy đường đi: {e}")

    # --- HIỂN THỊ KẾT QUẢ RA MÀN HÌNH ---
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
                    <div class="noi-dung-moc"><span class="ten-duong">Bắt đầu: {diem_bat_dau}</span></div>
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
                    <div class="noi-dung-moc"><span class="ten-duong">Đích đến: {diem_ket_thuc}</span></div>
                </div></div>'''
                st.markdown(html_content, unsafe_allow_html=True)

        with cot_ban_do:
            m = folium.Map(location=st.session_state['tam_ban_do'], zoom_start=14, tiles="cartodbpositron")
            them_cac_nut_len_ban_do(m, Do_thi_Pleiku)
            Fullscreen().add_to(m)

            folium.Marker(dia_diem_hop_le[diem_bat_dau], icon=folium.Icon(color="green", icon="play", prefix='fa'), popup="BẮT ĐẦU").add_to(m)
            folium.Marker(dia_diem_hop_le[diem_ket_thuc], icon=folium.Icon(color="red", icon="flag", prefix='fa'), popup="KẾT THÚC").add_to(m)
            
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

            mau_sac = "orange" if "DFS" in thuat_toan_tim_duong else ("purple" if "BFS" in thuat_toan_tim_duong else "#3498DB")
            AntPath(toa_do_duong_di, color=mau_sac, weight=6, opacity=0.8, delay=1000).add_to(m)

            folium.PolyLine([dia_diem_hop_le[diem_bat_dau], toa_do_duong_di[0]], color="gray", weight=2, dash_array='5, 5').add_to(m)
            folium.PolyLine([dia_diem_hop_le[diem_ket_thuc], toa_do_duong_di[-1]], color="gray", weight=2, dash_array='5, 5').add_to(m)

            st_folium(m, width=900, height=600, returned_objects=[])

    # --- MẶC ĐỊNH KHI MỚI VÀO ---
    else:
        m = folium.Map(location=[13.9785, 108.0051], zoom_start=14, tiles="cartodbpositron")
        them_cac_nut_len_ban_do(m, Do_thi_Pleiku)
        st_folium(m, width=1200, height=600, returned_objects=[])



