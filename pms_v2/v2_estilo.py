"""Estética de la suite v2: azul verdoso pastel (paleta de docs/maquetas/pms-suite-v2-pastel.html)."""
import streamlit as st

CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap");
:root{--bg:#dff1ee;--bg2:#ecf7f5;--panel:#ffffff;--line:#cfe6e1;--txt:#123733;--txt2:#3e615c;--accent:#2a9d8f;--accent2:#3aa6b9}
.stApp{background:linear-gradient(180deg,var(--bg2),var(--bg)) !important;color:var(--txt)}
header[data-testid="stHeader"]{background:transparent}
section[data-testid="stSidebar"]{background:#e8f5f2 !important;border-right:1px solid var(--line)}
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"]{color:#6f8f8a;text-transform:uppercase;letter-spacing:.08em;font-size:.72rem;font-weight:700}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]{border-radius:10px}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"][aria-current="page"]{background:#cdeae4}
div[data-testid="stMainBlockContainer"]{background:var(--panel);border:1px solid var(--line);border-radius:14px;
  box-shadow:0 8px 26px rgba(20,80,70,.10);margin-top:1rem;margin-bottom:4.5rem}
h1,h2,h3{color:var(--txt) !important}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:var(--accent);border-color:var(--accent)}
.stButton>button[kind="primary"]:hover{background:#238a7e;border-color:#238a7e}
div[data-testid="stMetric"]{background:#f5fbfa;border:1px solid var(--line);border-radius:12px;padding:.5rem .8rem}
.pms-pie{background:rgba(236,247,245,.97) !important;border-top-color:var(--line) !important}
.v2-fase{background:#f5fbfa;border:1px dashed #b9dbd4;border-radius:14px;padding:1rem 1.2rem;color:var(--txt2)}
.v2-badge{display:inline-block;background:#fdf1dc;color:#9a6408;border:1px solid #cf8a1655;border-radius:10px;padding:.05rem .6rem;font-size:.78rem;font-weight:700}
html,body,.stApp,.stApp *:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded){font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif}
h1{font-weight:800 !important;letter-spacing:-.02em;font-size:1.7rem !important}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]{padding:.45rem .7rem;margin-bottom:2px;color:var(--txt2);font-weight:500;font-size:13.5px;transition:.18s}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"]:hover{background:#dcefeb}
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"][aria-current="page"] span{color:#1f7a6f;font-weight:600}
.stButton>button,.stFormSubmitButton>button,.stDownloadButton>button{height:37px;border-radius:10px;font-size:13px;font-weight:600;border:1px solid var(--line);color:var(--txt2);background:var(--panel)}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{color:#fff;box-shadow:0 0 0 1px rgba(42,157,143,.22),0 8px 26px rgba(42,157,143,.14)}
div[data-testid="stMetric"]{border-radius:14px;padding:16px 17px;position:relative;overflow:hidden;box-shadow:0 1px 6px rgba(20,80,70,.08)}
div[data-testid="stMetric"]::before{content:"";position:absolute;left:0;top:0;right:0;height:3px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
div[data-testid="stExpander"],div[data-testid="stForm"]{border:1px solid var(--line) !important;border-radius:14px !important;background:var(--panel);box-shadow:0 1px 6px rgba(20,80,70,.08)}
div[data-baseweb="input"],div[data-baseweb="select"]>div{border-radius:9px !important;border-color:var(--line) !important}
.pms-room{border-radius:14px !important}
.pms-aviso{border-radius:12px}
</style>"""


def aplicar():
    st.markdown(CSS, unsafe_allow_html=True)
