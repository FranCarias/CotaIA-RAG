"""CotaIA | NexaTech: interface Streamlit para o assistente de cotações.

Rodar:  streamlit run app.py
Requer: cotaia_backend.py e humano.py na mesma pasta e a chave GROQ_API_KEY
        (variável de ambiente ou .streamlit/secrets.toml).
"""
import html
import os
import uuid
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="NexaTech | Cotações",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# Tema (claro / noturno). Fica na sessão e também na URL (?tema=escuro), assim
# sobrevive a um F5. Todas as cores do app saem das variáveis abaixo.
# --------------------------------------------------------------------------
if "tema" not in st.session_state:
    inicial = st.query_params.get("tema", "claro")
    st.session_state.tema = inicial if inicial in ("claro", "escuro") else "claro"
TEMA = st.session_state.tema

PALETAS = {
    "claro": {
        "scheme": "light",
        "paper": "#F3F6FB", "sheet": "rgba(255,255,255,.62)", "surface": "#FFFFFF", "surface2": "#EEF2F7",
        "line": "#E1E6EE", "text": "#14202F", "head": "#0F1B2D", "muted": "#5B6B7F",
        "blue": "#2457D6", "blue-d": "#1B44AE", "link": "#1B44AE", "ring": "rgba(36,87,214,.22)",
        "bubble": "#2457D6", "avatar": "#0F1B2D", "dot": "rgba(36,87,214,.13)",
        "glow1": "rgba(36,87,214,.13)", "glow2": "rgba(232,163,61,.10)", "shadow": "0 1px 2px rgba(15,27,45,.06)",
        "alert-bg": "#FDECEC", "alert-text": "#7A1F1F", "toggle-icon": "#2457D6", "side": "#0F1B2D",
        "fade": "rgba(243,246,251,0)",
    },
    "escuro": {
        "scheme": "dark",
        "paper": "#0A111F", "sheet": "rgba(10,17,31,.66)", "surface": "#141E31", "surface2": "#1D2A44",
        "line": "#27354F", "text": "#E4EAF4", "head": "#F3F6FB", "muted": "#9AAAC1",
        "blue": "#5B88F5", "blue-d": "#8BA9FA", "link": "#A9C1FF", "ring": "rgba(91,136,245,.30)",
        "bubble": "#2F5BD8", "avatar": "#2A4A8C", "dot": "rgba(140,170,255,.10)",
        "glow1": "rgba(60,100,230,.18)", "glow2": "rgba(232,163,61,.07)", "shadow": "none",
        "alert-bg": "rgba(235,87,87,.14)", "alert-text": "#FFD3D3", "toggle-icon": "#F5B748", "side": "#070C17",
        "fade": "rgba(10,17,31,0)",
    },
}


def variaveis(nome: str) -> str:
    p = PALETAS[nome]
    corpo = "".join(f"--{k}:{v};" for k, v in p.items() if k != "scheme")
    return f":root{{{corpo}color-scheme:{p['scheme']};}}"


CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

.stApp, .stApp p, .stApp li, .stApp td, .stApp th, .stApp h1, .stApp h2, .stApp h3,
.stApp button, .stApp textarea, .stApp input, .stApp label {
  font-family:'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
}

/* ---------- fundo: pontinhos + brilhos suaves (aparece nas laterais do chat) ---------- */
.stApp {
  color:var(--text); background-color:var(--paper);
  background-image:
    radial-gradient(var(--dot) 1px, transparent 1.2px),
    radial-gradient(900px 520px at 92% -8%, var(--glow1), transparent 62%),
    radial-gradient(760px 520px at -4% 104%, var(--glow2), transparent 60%);
  background-size:22px 22px, auto, auto;
  background-attachment:fixed;
}
.stApp, [data-testid="stChatMessage"], [data-testid="stChatInput"], [data-testid="stMainBlockContainer"],
.st-key-chips button, .st-key-toolbar button {
  transition:background-color .25s ease, color .25s ease, border-color .25s ease;
}
#MainMenu, footer, .stDeployButton { visibility:hidden; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stMainBlockContainer"], .block-container {
  max-width:980px; padding-top:1.1rem; padding-bottom:6rem;
  background:var(--sheet); border-left:1px solid var(--line); border-right:1px solid var(--line);
  backdrop-filter:blur(6px); padding-left:2rem; padding-right:2rem;
}

/* ícones/setas do cabeçalho: sempre legíveis, nos dois temas */
[data-testid="stHeader"] button, [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] button,
[data-testid="stHeader"] [data-testid="stIconMaterial"], [data-testid="stExpandSidebarButton"] *,
[data-testid="stSidebarCollapsedControl"] * { color:var(--text) !important; fill:currentColor; }
[data-testid="stSidebarCollapseButton"] *, [data-testid="stSidebarHeader"] button * { color:#C5D1E2 !important; fill:currentColor; }

/* ---------- textos ---------- */
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color:var(--head); }
.stApp a { color:var(--link); }
.stApp [data-testid="stMarkdownContainer"] :is(p, li, td, label, span) { color:var(--text); }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] * { color:var(--text) !important; -webkit-text-fill-color:var(--text) !important; }
[data-testid="stSpinner"], [data-testid="stSpinner"] * { color:var(--muted) !important; }
[data-testid="stAlert"] { background:var(--alert-bg); border-radius:12px; }
[data-testid="stAlert"] * { color:var(--alert-text) !important; }
[data-testid="stCode"] pre, [data-testid="stCode"] code { background:var(--surface2) !important; color:var(--text) !important; }
[data-testid="stToast"] { background:var(--surface); border:1px solid var(--line); border-radius:12px; }
[data-testid="stToast"] * { color:var(--text) !important; }

/* ---------- barra de ferramentas (tema + limpar) ---------- */
.st-key-toolbar button {
  transition:background-color .25s ease, color .25s ease, border-color .25s ease;
}
#MainMenu, footer, .stDeployButton { visibility:hidden; }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stMainBlockContainer"], .block-container {
  max-width:980px; padding-top:1.1rem; padding-bottom:6rem;
  background:var(--sheet); border-left:1px solid var(--line); border-right:1px solid var(--line);
  backdrop-filter:blur(6px); padding-left:2rem; padding-right:2rem;
}

/* ícones/setas do cabeçalho: sempre legíveis, nos dois temas */
[data-testid="stHeader"] button, [data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] button,
[data-testid="stHeader"] [data-testid="stIconMaterial"], [data-testid="stExpandSidebarButton"] *,
[data-testid="stSidebarCollapsedControl"] * { color:var(--text) !important; fill:currentColor; }
[data-testid="stSidebarCollapseButton"] *, [data-testid="stSidebarHeader"] button * { color:#C5D1E2 !important; fill:currentColor; }

/* ---------- textos ---------- */
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color:var(--head); }
.stApp a { color:var(--link); }
.stApp [data-testid="stMarkdownContainer"] :is(p, li, td, label, span) { color:var(--text); }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] * { color:var(--text) !important; -webkit-text-fill-color:var(--text) !important; }
[data-testid="stSpinner"], [data-testid="stSpinner"] * { color:var(--muted) !important; }
[data-testid="stAlert"] { background:var(--alert-bg); border-radius:12px; }
[data-testid="stAlert"] * { color:var(--alert-text) !important; }
[data-testid="stCode"] pre, [data-testid="stCode"] code { background:var(--surface2) !important; color:var(--text) !important; }
[data-testid="stToast"] { background:var(--surface); border:1px solid var(--line); border-radius:12px; }
[data-testid="stToast"] * { color:var(--text) !important; }

/* ---------- barra de ferramentas (tema + limpar) ---------- */
.st-key-toolbar button {
  border-radius:999px; border:1px solid var(--line); background:var(--surface); color:var(--text);
  min-height:36px; padding:2px 14px; font-size:13px; font-weight:500; box-shadow:var(--shadow);
}
.st-key-toolbar button p { color:inherit !important; font-size:13px; }
.st-key-toolbar button:hover { border-color:var(--blue); color:var(--blue); }
.st-key-toolbar button:focus-visible { outline:2px solid var(--blue); outline-offset:2px; }
.st-key-toolbar button:disabled { opacity:.8; color:var(--muted) !important; }
.st-key-toolbar button:disabled p { color:var(--muted) !important; -webkit-text-fill-color:var(--muted) !important; }
.st-key-toolbar button p { -webkit-text-fill-color:currentColor !important; }
.st-key-tema_btn [data-testid="stIconMaterial"] { color:var(--toggle-icon) !important; font-size:20px; }
.st-key-limpar_btn [data-testid="stIconMaterial"] { color:var(--muted) !important; }

/* ---------- cabeçalho ---------- */
.nx-head { display:flex; justify-content:space-between; align-items:flex-end; gap:24px; flex-wrap:wrap;
  padding-bottom:18px; margin-bottom:16px; border-bottom:1px solid var(--line); }
.nx-head h1 { font-size:28px !important; font-weight:600 !important; letter-spacing:-.015em;
  color:var(--head) !important; margin:0 !important; padding:0 !important; line-height:1.15 !important; }
.nx-head p { color:var(--muted) !important; font-size:15px; margin:6px 0 0; max-width:520px; line-height:1.5; }
.nx-facts { display:flex; }
.nx-facts div { padding:0 16px; border-left:1px solid var(--line); font-size:13px; color:var(--muted); line-height:1.4; }
.nx-facts div:first-child { border-left:0; padding-left:0; }
.nx-facts b { display:block; color:var(--head); font-weight:600; font-size:15px; }

/* ---------- atalhos ---------- */
.st-key-chips button { border-radius:999px; border:1px solid var(--line); background:var(--surface); color:var(--text);
  font-size:13px; font-weight:500; min-height:34px; padding:2px 12px; box-shadow:var(--shadow); }
.st-key-chips button p { color:inherit !important; font-size:13px; }
.st-key-chips button:hover { border-color:var(--blue); color:var(--blue); }
.st-key-chips button:focus-visible { outline:2px solid var(--blue); outline-offset:2px; }

/* ---------- conversa ---------- */
[data-testid="stChatMessage"] { background:var(--surface); border:1px solid var(--line); border-radius:14px;
  padding:14px 18px; margin-bottom:12px; gap:14px; box-shadow:var(--shadow); }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] :is(p, li) { font-size:15px; line-height:1.6; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] :is(strong, h1, h2, h3, h4, th) { color:var(--head) !important; -webkit-text-fill-color:var(--head) !important; }
[data-testid="stChatMessage"] hr { border-color:var(--line); }

[data-testid="stChatMessageAvatarAssistant"] { background:var(--avatar); }
[data-testid="stChatMessageAvatarAssistant"] * { color:#fff !important; fill:currentColor; }
[data-testid="stChatMessageAvatarUser"] { background:#fff; }
[data-testid="stChatMessageAvatarUser"] * { color:#2457D6 !important; fill:currentColor; }

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
  background:var(--bubble); border-color:var(--bubble); flex-direction:row-reverse; margin-left:auto; max-width:80%; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdownContainer"]  *,
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stMarkdownContainer"] * { color:#fff !important; -webkit-text-fill-color:#fff !important; }

[data-testid="stChatMessage"] table { width:100%; display:block; overflow-x:auto; border-collapse:collapse;
  font-size:13.5px; margin:8px 0; }
[data-testid="stChatMessage"] th { background:var(--surface2); color:var(--head) !important; font-weight:600; text-align:left;
  padding:8px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }
[data-testid="stChatMessage"] td { padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top;
  font-variant-numeric:tabular-nums; }
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] code { background:var(--surface2); color:var(--link) !important; -webkit-text-fill-color:var(--link) !important; border-radius:5px; padding:1px 6px; font-size:12.5px; }

/* ---------- campo de mensagem ---------- */
[data-testid="stBottom"], [data-testid="stBottom"] > div { background:transparent !important; }
[data-testid="stBottomBlockContainer"] { background:linear-gradient(to top, var(--paper) 62%, var(--fade)); }
[data-testid="stChatInput"], [data-testid="stChatInput"] > div { background:var(--surface) !important; }
[data-testid="stChatInput"] { border-radius:14px; border:1px solid var(--line); box-shadow:var(--shadow); }
[data-testid="stChatInput"]:focus-within { border-color:var(--blue); box-shadow:0 0 0 3px var(--ring); }
[data-testid="stChatInput"] textarea { color:var(--text) !important; background:transparent !important; }
[data-testid="stChatInput"] textarea::placeholder { color:var(--muted) !important; opacity:1; }
[data-testid="stChatInputSubmitButton"] { color:var(--blue) !important; background:transparent !important; }
[data-testid="stChatInputSubmitButton"] svg { fill:currentColor; }

/* ---------- barra lateral ---------- */
[data-testid="stSidebar"] { background:var(--side); border-right:1px solid rgba(255,255,255,.06); }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] :is(p, li, span) { color:#C5D1E2 !important; }

.nx-brandcard { position:relative; overflow:hidden; border-radius:16px; padding:16px 16px 14px; margin:2px 0 6px;
  background:linear-gradient(150deg, #23479C 0%, #15295A 52%, #0F1B2D 100%);
  border:1px solid rgba(255,255,255,.12); box-shadow:0 8px 24px rgba(0,0,0,.28); }
.nx-brandcard::before { content:""; position:absolute; right:-34px; top:-40px; width:130px; height:130px; border-radius:50%;
  background:radial-gradient(circle, rgba(120,160,255,.38), transparent 68%); }
.nx-brandcard::after { content:""; position:absolute; left:0; bottom:0; height:3px; width:100%;
  background:linear-gradient(90deg, #4C7DF0, #E8A33D 60%, transparent); opacity:.9; }
.nx-brand { position:relative; display:flex; align-items:center; gap:12px; }
.nx-mark { position:relative; flex:none; width:46px; height:46px; border-radius:13px; display:grid; place-items:center;
  background:linear-gradient(145deg, #5C8BFA, #2457D6 70%); color:#fff; font-weight:700; font-size:23px; letter-spacing:-.02em;
  box-shadow:0 6px 14px rgba(36,87,214,.5), inset 0 1px 0 rgba(255,255,255,.35); }
.nx-mark::after { content:""; position:absolute; top:-3px; right:-3px; width:11px; height:11px; border-radius:50%;
  background:#E8A33D; border:2px solid #15295A; }
.nx-word b { display:block; color:#fff; font-size:21px; font-weight:600; letter-spacing:-.015em; line-height:1.1; }
.nx-word b i { font-style:normal; font-weight:500; color:#9DBBFF; }
.nx-word span { display:block; margin-top:3px; color:#9FB0C6; font-size:10.5px; letter-spacing:.16em; text-transform:uppercase; }
.nx-badge { position:relative; display:inline-flex; align-items:center; gap:8px; margin-top:14px; padding:5px 11px;
  border-radius:999px; background:rgba(255,255,255,.09); border:1px solid rgba(255,255,255,.12);
  color:#DCE6F5; font-size:12px; font-weight:500; }
.nx-dot { width:8px; height:8px; border-radius:50%; background:#3DB07A; box-shadow:0 0 0 0 rgba(61,176,122,.6);
  animation:nxpulse 2.2s infinite; }
@keyframes nxpulse { 70% { box-shadow:0 0 0 7px rgba(61,176,122,0); } 100% { box-shadow:0 0 0 0 rgba(61,176,122,0); } }
@media (prefers-reduced-motion: reduce) { .nx-dot { animation:none; } }

.nx-sec { color:#fff; font-size:14px; font-weight:600; margin:18px 0 8px; display:flex;
  justify-content:space-between; align-items:baseline; }
.nx-sec small { color:#9FB0C6; font-weight:400; font-size:12px; }

.nx-quote { background:rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.08);
  border-left:3px solid #55657B; border-radius:10px; padding:10px 12px; margin-bottom:8px; }
.nx-quote.aberta { border-left-color:#E8A33D; }
.nx-quote.final { border-left-color:#3DB07A; }
.nx-quote.desc { opacity:.55; }
.nx-quote.edit { background:rgba(76,125,240,.22); border-color:rgba(120,160,255,.45); }
.nx-q-top { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.nx-q-top b { color:#fff; font-size:14px; font-weight:600; }
.nx-edit { font-size:11px; background:#2457D6; color:#fff; padding:1px 7px; border-radius:6px; margin-left:6px; font-weight:500; }
.nx-q-st { font-size:11.5px; color:#C5D1E2; }
.nx-q-items { color:#A9B8CC; font-size:12.5px; margin:5px 0 8px; line-height:1.4; }
.nx-q-foot { display:flex; justify-content:space-between; font-size:12.5px; color:#C5D1E2; font-variant-numeric:tabular-nums; }
.nx-q-foot b { color:#fff; font-size:14px; font-weight:600; }
.nx-note { color:#8EA0B7; font-size:12px; line-height:1.55; margin:6px 0 0; }
.nx-note code { background:rgba(255,255,255,.09); color:#DCE6F5; border-radius:4px; padding:0 4px; font-size:11.5px; }
.nx-foot { margin-top:22px; padding-top:12px; border-top:1px solid rgba(255,255,255,.08); color:#7F91A9; font-size:11.5px; line-height:1.6; }
.nx-foot b { color:#B7C5DA; font-weight:600; }

[data-testid="stSidebar"] .stButton button { background:#fff; color:#0F1B2D; border:0; border-radius:10px; font-weight:600; }
[data-testid="stSidebar"] .stButton button p { color:inherit !important; }
[data-testid="stSidebar"] .stButton button:hover { background:#E7EEFB; color:#0F1B2D; }
[data-testid="stSidebar"] .stButton button:disabled { background:rgba(255,255,255,.12); color:#8EA0B7; }
[data-testid="stSidebar"] .stDownloadButton button { background:#2457D6; color:#fff; border:0; border-radius:10px; font-weight:600; }
[data-testid="stSidebar"] .stDownloadButton button p { color:#fff !important; }
[data-testid="stSidebar"] .stDownloadButton button:hover { background:#1B44AE; color:#fff; }
[data-testid="stSidebar"] .stDownloadButton { margin-top:6px; }

@media (max-width:768px) {
  [data-testid="stMainBlockContainer"], .block-container { padding-left:1rem; padding-right:1rem; border-left:0; border-right:0; }
  .nx-head h1 { font-size:23px !important; }
  .nx-facts { flex-wrap:wrap; row-gap:8px; }
  [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { max-width:100%; }
}
"""
st.markdown(f"<style>{variaveis(TEMA)}{CSS}</style>", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Backend (carregado uma vez por processo)
# --------------------------------------------------------------------------
def garantir_chave() -> bool:
    if os.environ.get("GROQ_API_KEY"):
        return True
    try:
        chave = st.secrets["GROQ_API_KEY"]
    except Exception:
        chave = ""
    if chave:
        os.environ["GROQ_API_KEY"] = chave
        return True
    return False


if not garantir_chave():
    st.error("Falta a chave do Groq (GROQ_API_KEY). Crie uma em console.groq.com/keys e salve no arquivo "
             "`.streamlit/secrets.toml` ou na variável de ambiente GROQ_API_KEY.")
    st.code('GROQ_API_KEY = "gsk_..."', language="toml")
    st.stop()


@st.cache_resource(show_spinner="Carregando catálogo e modelos de busca. Na primeira vez isso leva alguns minutos.")
def carregar_backend():
    import cotaia_backend
    return cotaia_backend


bk = carregar_backend()

if "sid" not in st.session_state:
    st.session_state.sid = uuid.uuid4().hex
    st.session_state.msgs = [{"role": "assistant", "content": bk.BOAS_VINDAS}]
    st.session_state.pdf_sig = {}

sessao = bk.get_sessao(st.session_state.sid)
AVATAR = {"assistant": ":material/support_agent:", "user": ":material/person:"}


# --------------------------------------------------------------------------
# Ações dos botões (rodam antes do próximo desenho da tela)
# --------------------------------------------------------------------------
def alternar_tema():
    novo = "escuro" if st.session_state.tema == "claro" else "claro"
    st.session_state.tema = novo
    st.query_params["tema"] = novo


def limpar_conversa():
    """Apaga só o bate-papo. As cotações e os PDFs continuam salvos na barra lateral."""
    st.session_state.msgs = [{"role": "assistant", "content": bk.BOAS_VINDAS}]
    bk.get_sessao(st.session_state.sid).limpar_contexto()      # fecha listas de opções que sumiram da tela
    st.session_state.toast = ("Conversa limpa. Suas cotações continuam salvas.", "🧹")


# --------------------------------------------------------------------------
# Barra lateral: marca, cotações e PDF
# --------------------------------------------------------------------------
STATUS = {"vazia": "Vazia", "aberta": "Em andamento", "final": "Finalizada", "desc": "Descartada"}


def classe_status(c) -> str:
    if c.status == "finalizada":
        return "final"
    if c.status == "descartada":
        return "desc"
    return "aberta" if c.carrinho else "vazia"


def cartao(c) -> str:
    cls = classe_status(c)
    editando = c is sessao.ativa
    tag = '<span class="nx-edit">Em edição</span>' if editando else ""
    return (f'<div class="nx-quote {cls}{" edit" if editando else ""}">'
            f'<div class="nx-q-top"><span><b>Cotação {c.numero}</b>{tag}</span>'
            f'<span class="nx-q-st">{STATUS[cls]}</span></div>'
            f'<div class="nx-q-items">{html.escape(bk.resumo_itens(c))}</div>'
            f'<div class="nx-q-foot"><span>{c.unidades()} un.</span><b>{bk.brl(c.total())}</b></div></div>')


def assinatura(c):
    return tuple(sorted(c.carrinho.items()))


def pdf_valido(c) -> bool:
    if not (c.pdf and os.path.exists(c.pdf)):
        return False
    return c.status == "finalizada" or st.session_state.pdf_sig.get(c.numero) == assinatura(c)


with st.sidebar:
    st.markdown(
        '<div class="nx-brandcard">'
        '<div class="nx-brand"><div class="nx-mark">N</div>'
        '<div class="nx-word"><b>Nexa<i>Tech</i></b><span>Informática</span></div></div>'
        '<div class="nx-badge"><span class="nx-dot"></span>CotaIA · assistente de cotações</div>'
        '</div>',
        unsafe_allow_html=True)

    st.markdown(f'<div class="nx-sec">Suas cotações<small>{len(sessao.cotacoes)} no total</small></div>',
                unsafe_allow_html=True)
    st.markdown("".join(cartao(c) for c in sessao.cotacoes), unsafe_allow_html=True)
    st.markdown('<div class="nx-note">Os novos produtos entram na cotação marcada como em edição.</div>',
                unsafe_allow_html=True)

    st.markdown('<div class="nx-sec">Proposta em PDF</div>', unsafe_allow_html=True)
    ativa = sessao.ativa
    if st.button(f"Gerar PDF da cotação {ativa.numero}", use_container_width=True,
                 disabled=not ativa.carrinho, key="gerar_pdf"):
        try:
            bk.gerar_pdf_sessao(sessao)
            st.session_state.pdf_sig[ativa.numero] = assinatura(ativa)
        except Exception as e:
            st.error(f"Não foi possível gerar o PDF ({type(e).__name__}).")
    if not ativa.carrinho:
        st.markdown('<div class="nx-note">Adicione um produto para gerar o PDF.</div>', unsafe_allow_html=True)

    for c in sessao.cotacoes:
        if pdf_valido(c):
            st.download_button(f"Baixar cotação {c.numero} (PDF)", data=Path(c.pdf).read_bytes(),
                               file_name=Path(c.pdf).name, mime="application/pdf",
                               use_container_width=True, key=f"dl_{c.numero}")

    st.markdown('<div class="nx-sec">Comandos úteis</div>'
                '<div class="nx-note"><code>nova cotação</code> <code>cotações</code><br>'
                '<code>abrir cotação 1</code> <code>descartar cotação 2</code><br>'
                '<code>carrinho</code> <code>remover 1</code> <code>limpar</code> <code>finalizar</code></div>',
                unsafe_allow_html=True)

    st.markdown(f'<div class="nx-foot"><b>NexaTech Informática</b><br>CotaIA · atendimento virtual · v1.3<br>'
                f'{int(bk.DESCONTO_PIX * 100)}% no PIX · proposta válida por {bk.VALIDADE_DIAS} dias</div>',
                unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Área principal
# --------------------------------------------------------------------------
aviso = st.session_state.pop("toast", None)
if aviso:
    st.toast(aviso[0], icon=aviso[1])

with st.container(key="toolbar"):
    _, c_tema, c_limpar = st.columns([5, 2.2, 2.4])
    if TEMA == "claro":
        c_tema.button("Modo noturno", key="tema_btn", icon=":material/dark_mode:", on_click=alternar_tema,
                      help="Trocar para o tema noturno", use_container_width=True)
    else:
        c_tema.button("Modo claro", key="tema_btn", icon=":material/light_mode:", on_click=alternar_tema,
                      help="Trocar para o tema claro", use_container_width=True)
    c_limpar.button("Limpar conversa", key="limpar_btn", icon=":material/delete_sweep:", on_click=limpar_conversa,
                    disabled=len(st.session_state.msgs) <= 1, use_container_width=True,
                    help="Apaga o bate-papo. As cotações continuam salvas.")

st.markdown(
    f'<div class="nx-head"><div><h1>Cotações NexaTech</h1>'
    f'<p>Converse para montar a cotação: escolha os produtos, ajuste as quantidades e baixe a proposta em PDF.</p></div>'
    f'<div class="nx-facts">'
    f'<div><b>{len(bk.PRODUTOS)} modelos</b>{len(bk.CATEGORIAS)} categorias</div>'
    f'<div><b>{int(bk.DESCONTO_PIX * 100)}% no PIX</b>desconto à vista</div>'
    f'<div><b>{bk.VALIDADE_DIAS} dias</b>validade da proposta</div>'
    f'</div></div>',
    unsafe_allow_html=True,
)

ATALHOS = [
    ("Monitores", "monitor"),
    ("2 mouses baratos", "quero 2 unidades do mouse mais barato"),
    ("Nova cotação", "nova cotação"),
    ("Cotações", "cotações"),
    ("Carrinho", "carrinho"),
    ("Finalizar", "finalizar"),
    ("Garantia", "qual a garantia?"),
]


def enviar(texto: str):
    st.session_state.pendente = texto


with st.container(key="chips"):
    colunas = st.columns(len(ATALHOS))
    for col, (rotulo, texto) in zip(colunas, ATALHOS):
        col.button(rotulo, key=f"atalho_{rotulo}", on_click=enviar, args=(texto,), use_container_width=True)

st.write("")

for m in st.session_state.msgs:
    with st.chat_message(m["role"], avatar=AVATAR[m["role"]]):
        st.markdown(m["content"], unsafe_allow_html=(m["role"] == "assistant"))

digitado = st.chat_input("Escreva o que precisa. Exemplo: 2 unidades do mouse mais barato")
texto = st.session_state.pop("pendente", None) or digitado

if texto and texto.strip():
    finalizadas_antes = sum(c.status == "finalizada" for c in sessao.cotacoes)
    st.session_state.msgs.append({"role": "user", "content": texto})
    with st.chat_message("user", avatar=AVATAR["user"]):
        st.markdown(texto)
    with st.chat_message("assistant", avatar=AVATAR["assistant"]):
        with st.spinner("Um instante, já te respondo..."):
            try:
                resposta = bk.atender(texto, st.session_state.sid)
            except Exception as e:
                resposta = f"Não consegui processar essa mensagem agora ({type(e).__name__}). Tente de novo em instantes."
        st.markdown(resposta, unsafe_allow_html=True)
    st.session_state.msgs.append({"role": "assistant", "content": resposta})
    if sum(c.status == "finalizada" for c in sessao.cotacoes) > finalizadas_antes:
        st.session_state.toast = ("Cotação finalizada! O PDF está na barra lateral.", "🎉")
    st.rerun()   # atualiza a barra lateral com o estado novo das cotações
