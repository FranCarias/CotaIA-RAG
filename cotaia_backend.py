"""Backend do CotaIA (catálogo, busca, diálogo, cotações e PDF).

Extraído do notebook CotaIA_RAG_v4_layout.ipynb (células 4 a 22), sem a instalação
de pacotes e sem nenhum código de interface. A interface fica no app.py.
"""

# ===== célula [4] =====
import os
import re
import json
import time
import difflib
import unicodedata
from datetime import datetime, timedelta
from getpass import getpass
from xml.sax.saxutils import escape

import faiss
import pandas as pd
from openai import OpenAI
from sentence_transformers import SentenceTransformer

import humano     # [NOVO] conversa mais humana (saudação, agradecimento, despedida)

GROQ_URL = "https://api.groq.com/openai/v1"
MODELOS_PREFERIDOS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-20b"]


def obter_chave() -> str:
    """Tenta variável de ambiente, depois Secrets do Colab; se não achar, pede para colar."""
    chave = os.environ.get("GROQ_API_KEY", "")
    if not chave:
        try:
            from google.colab import userdata
            chave = userdata.get("GROQ_API_KEY")
        except Exception:
            chave = ""
    if not chave:
        chave = getpass("Cole sua chave do Groq (começa com gsk_) e aperte Enter: ").strip()
    return chave


API_KEY = obter_chave()
assert API_KEY, "Sem chave. Crie uma grátis em https://console.groq.com/keys"
client = OpenAI(api_key=API_KEY, base_url=GROQ_URL)


def escolher_modelo() -> str:
    ids = [m.id for m in client.models.list().data]
    for preferido in MODELOS_PREFERIDOS:
        if preferido in ids:
            return preferido
    excluir = ("whisper", "guard", "tts", "embed", "distil-whisper")
    chat = [i for i in ids if not any(x in i.lower() for x in excluir)]
    return chat[0] if chat else ids[0]


MODELO_LLM = escolher_modelo()
print("Modelo LLM em uso:", MODELO_LLM)


def chamar_llm(system: str, user: str, temperatura: float = 0.0) -> str:
    resp = client.chat.completions.create(
        model=MODELO_LLM,
        temperature=temperatura,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content

# ===== célula [6] =====
# (codigo, categoria, marca, modelo, preço, estoque, especificações, uso ideal)
_CATALOGO = [
    ("INF001", "Notebook", "Aurora", "Office 15", 3200.00, 12, "15,6 polegadas, Intel Core i5, 8 GB de RAM, SSD de 256 GB", "trabalho e estudo no dia a dia"),
    ("INF011", "Notebook", "Nimbus", "Slim 14", 3790.00, 8, "14 polegadas, AMD Ryzen 5, 16 GB de RAM, SSD de 512 GB, ultraleve 1,3 kg", "mobilidade e trabalho remoto"),
    ("INF012", "Notebook", "Aurora", "Office Pro 15", 4290.00, 5, "15,6 polegadas, Intel Core i7, 16 GB de RAM, SSD de 512 GB, teclado numérico", "trabalho pesado e multitarefa"),
    ("INF013", "Notebook", "Vektra", "Gamer X", 6890.00, 3, "15,6 polegadas Full HD 144 Hz, Intel Core i7, 16 GB de RAM, SSD de 1 TB, placa de vídeo dedicada, gamer", "jogos e edição de vídeo"),

    ("INF014", "Monitor", "Aurora", "View 22", 590.00, 15, "22 polegadas, Full HD, 60 Hz, HDMI e VGA", "uso básico e home office"),
    ("INF002", "Monitor", "Aurora", "View 24", 750.00, 20, "24 polegadas, Full HD, 75 Hz, painel IPS, HDMI", "escritório e uso doméstico"),
    ("INF015", "Monitor", "Nimbus", "Vision 27", 1190.00, 9, "27 polegadas, QHD, 75 Hz, painel IPS, HDMI e DisplayPort", "design e produtividade"),
    ("INF016", "Monitor", "Vektra", "Curve 32 Gamer", 1790.00, 3, "32 polegadas curvo, Full HD, 165 Hz, 1 ms, gamer", "jogos"),
    ("INF017", "Monitor", "Orion", "UltraWide 34", 2290.00, 0, "34 polegadas ultrawide, QHD, 100 Hz, painel IPS", "multitarefa e edição"),

    ("INF003", "Teclado", "Aurora", "Key ABNT2", 85.00, 40, "com fio USB, ABNT2, teclas de membrana", "uso geral"),
    ("INF018", "Teclado", "Nimbus", "Wireless K2", 149.00, 22, "sem fio 2,4 GHz, ABNT2, compacto", "escritório"),
    ("INF020", "Teclado", "Orion", "Slim Bluetooth", 219.00, 10, "sem fio Bluetooth, multidispositivo, recarregável, ABNT2", "uso com notebook e tablet"),
    ("INF019", "Teclado", "Vektra", "Mecânico RGB", 329.00, 7, "mecânico, switch azul, iluminação RGB, ABNT2, com fio, gamer", "jogos e digitação"),

    ("INF004", "Mouse", "Aurora", "M1", 45.00, 60, "óptico, com fio USB, 1200 DPI", "uso geral"),
    ("INF021", "Mouse", "Nimbus", "Wireless M3", 79.00, 30, "sem fio 2,4 GHz, 1600 DPI, pilha AA", "escritório"),
    ("INF022", "Mouse", "Vektra", "Gamer G5", 189.00, 14, "gamer, com fio, 12000 DPI, iluminação RGB, 6 botões", "jogos"),
    ("INF023", "Mouse", "Orion", "Ergo Bluetooth", 249.00, 6, "ergonômico vertical, sem fio Bluetooth, recarregável", "conforto em uso prolongado"),

    ("INF024", "SSD", "Aurora", "SATA 240", 260.00, 25, "240 GB, SATA, leitura de 500 MB/s", "atualizar um computador antigo"),
    ("INF005", "SSD", "Aurora", "SATA 480", 420.00, 30, "480 GB, SATA, leitura de 500 MB/s", "atualizar um computador antigo"),
    ("INF025", "SSD", "Nimbus", "NVMe 1TB", 640.00, 12, "1 TB, NVMe M.2, leitura de 3.500 MB/s", "desempenho e armazenamento amplo"),
    ("INF026", "SSD", "Vektra", "NVMe 2TB Gen4", 1190.00, 4, "2 TB, NVMe M.2 Gen4, leitura de 7.000 MB/s", "edição de vídeo e jogos"),

    ("INF006", "Memória RAM", "Aurora", "DDR4 8GB", 230.00, 35, "8 GB, DDR4, 3200 MHz, para desktop", "aumentar a memória de um desktop"),
    ("INF027", "Memória RAM", "Aurora", "DDR4 16GB", 420.00, 20, "16 GB, DDR4, 3200 MHz, para desktop", "multitarefa em desktop"),
    ("INF028", "Memória RAM", "Nimbus", "SODIMM 16GB", 460.00, 9, "16 GB, DDR4, 3200 MHz, para notebook (SODIMM)", "aumentar a memória de um notebook"),
    ("INF029", "Memória RAM", "Vektra", "DDR5 32GB Kit", 890.00, 5, "32 GB (2x16), DDR5, 5600 MHz, para desktop", "máquinas modernas de alto desempenho"),

    ("INF030", "Roteador", "Aurora", "N300", 159.00, 25, "Wi-Fi 4, N300, 4 portas Fast Ethernet", "casa pequena e internet básica"),
    ("INF007", "Roteador", "Aurora", "AC1200", 380.00, 18, "Wi-Fi 5 dual band, AC1200, 4 portas", "casa com vários dispositivos"),
    ("INF031", "Roteador", "Nimbus", "Wi-Fi 6 AX1800", 549.00, 10, "Wi-Fi 6, AX1800, 4 portas Gigabit", "internet rápida e streaming"),
    ("INF032", "Roteador", "Vektra", "Mesh AX3000 Kit 2", 1190.00, 4, "Wi-Fi 6 mesh, kit com 2 unidades, cobertura até 300 m²", "casas grandes sem pontos cegos de sinal"),

    ("INF008", "Headset", "Aurora", "H1", 160.00, 28, "com fio P2 e USB, microfone, estéreo", "uso geral e chamadas"),
    ("INF033", "Headset", "Nimbus", "Wireless H3", 289.00, 11, "sem fio Bluetooth, microfone, bateria de 30 horas", "reuniões e música sem fios"),
    ("INF034", "Headset", "Vektra", "Gamer 7.1", 349.00, 9, "gamer, USB, som surround 7.1, iluminação RGB, microfone", "jogos"),
    ("INF035", "Headset", "Orion", "Noise Cancel", 599.00, 6, "sem fio Bluetooth, cancelamento de ruído, bateria de 40 horas, microfone", "foco em ambientes barulhentos"),

    ("INF036", "Webcam", "Aurora", "Cam 720", 119.00, 20, "HD 720p, microfone embutido, USB", "videochamadas simples"),
    ("INF009", "Webcam", "Aurora", "Cam Full HD", 210.00, 16, "Full HD 1080p, microfone embutido, USB", "videochamadas e reuniões online"),
    ("INF037", "Webcam", "Nimbus", "Cam 2K", 349.00, 7, "2K QHD, autofoco, microfone duplo", "reuniões profissionais e aulas online"),
    ("INF038", "Webcam", "Vektra", "Stream 4K", 690.00, 3, "4K, autofoco, HDR, microfone, para streaming", "transmissões ao vivo e criação de conteúdo"),

    ("INF010", "Nobreak", "Aurora", "UPS 600", 680.00, 14, "600 VA, 6 tomadas, bivolt", "computador e roteador"),
    ("INF039", "Nobreak", "Aurora", "UPS 1200", 980.00, 8, "1200 VA, 8 tomadas, bivolt, proteção contra queda de energia", "computador e monitor"),
    ("INF040", "Nobreak", "Nimbus", "Senoidal 1500", 1790.00, 5, "1500 VA, onda senoidal pura, 8 tomadas", "equipamentos sensíveis"),
    ("INF041", "Nobreak", "Vektra", "Online 3000", 3490.00, 2, "3000 VA, online dupla conversão, torre ou rack", "servidores e pequenos escritórios"),
]

# categoria -> (ícone, singular, plural, sinônimos que o cliente pode usar)
CATEGORIAS = {
    "Notebook": ("💻", "Notebook", "Notebooks", ["notebook", "laptop", "note", "computador portátil", "pc portátil", "ultrabook"]),
    "Monitor": ("🖥️", "Monitor", "Monitores", ["monitor", "tela", "display", "tela de computador"]),
    "Teclado": ("⌨️", "Teclado", "Teclados", ["teclado", "keyboard"]),
    "Mouse": ("🖱️", "Mouse", "Mouses", ["mouse", "rato"]),
    "SSD": ("💾", "SSD", "SSDs", ["ssd", "hd", "disco", "disco sólido", "armazenamento", "nvme", "hd ssd"]),
    "Memória RAM": ("🧠", "Memória RAM", "Memórias RAM", ["ram", "memória ram", "memória", "pente de memória", "ddr4", "ddr5"]),
    "Roteador": ("📶", "Roteador", "Roteadores", ["roteador", "router", "wifi", "wi-fi", "repetidor", "mesh"]),
    "Headset": ("🎧", "Headset", "Headsets", ["headset", "fone", "fone de ouvido", "headphone", "fone com microfone", "auricular", "headfone"]),
    "Webcam": ("📷", "Webcam", "Webcams", ["webcam", "câmera", "camera web", "câmera de computador", "cam"]),
    "Nobreak": ("🔋", "Nobreak", "Nobreaks", ["nobreak", "no break", "ups"]),
}

PRODUTOS = [
    {"codigo": c, "categoria": cat, "marca": marca, "modelo": modelo,
     "nome": f"{CATEGORIAS[cat][1]} {marca} {modelo}", "preco": preco, "estoque": est,
     "specs": specs, "uso": uso}
    for (c, cat, marca, modelo, preco, est, specs, uso) in _CATALOGO
]
POR_CODIGO = {p["codigo"]: p for p in PRODUTOS}
MARCAS = sorted({p["marca"] for p in PRODUTOS})

FAQ_E_REGRAS = [
    {"fonte": "faq.md#garantia", "texto": "Garantia: todos os produtos da NexaTech têm garantia de 12 meses contra defeitos de fabricação."},
    {"fonte": "faq.md#pagamento", "texto": "Pagamento: aceitamos PIX com 5% de desconto, boleto e cartão de crédito em até 10 vezes sem juros."},
    {"fonte": "faq.md#entrega", "texto": "Entrega: o prazo de entrega é de 3 a 7 dias úteis. O frete depende da região e será informado por um atendente."},
    {"fonte": "faq.md#troca", "texto": "Troca e devolução: o cliente pode solicitar troca em até 7 dias após o recebimento, com o produto lacrado."},
    {"fonte": "regras_comerciais.json#validade", "texto": "Validade da cotação: toda cotação é válida por 7 dias corridos a partir da emissão."},
    {"fonte": "regras_comerciais.json#desconto", "texto": "Desconto por volume: pedidos acima de 10 unidades do mesmo item podem ter condição especial, sujeita a validação humana."},
    {"fonte": "regras_comerciais.json#ausencia", "texto": "Item ausente: quando um produto não consta no catálogo, o assistente informa que não encontrou e encaminha para um atendente."},
    {"fonte": "regras_comerciais.json#estoque", "texto": "Estoque: itens esgotados não entram na cotação; o atendente pode informar a previsão de reposição."},
]

DESCONTO_PIX = 0.05
VALIDADE_DIAS = 7
LIMITE_VOLUME = 10

print(f"Catálogo: {len(PRODUTOS)} produtos em {len(CATEGORIAS)} categorias")

# ===== célula [8] =====
def normalizar(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower()
    txt = txt.replace("-", " ")
    txt = re.sub(r"[^a-z0-9.,\s]", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def tokens(txt: str):
    return re.findall(r"[a-z]+|\d+(?:[.,]\d+)*", normalizar(txt))


def singular(tok: str) -> str:
    if tok.isdigit() or len(tok) <= 3 or not tok.isalpha():
        return tok
    if tok.endswith("res") and len(tok) > 5:      # monitores -> monitor
        return tok[:-2]
    if tok.endswith("oes"):                        # opcoes -> opcao
        return tok[:-3] + "ao"
    if tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def brl(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def extrair_json(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


modelo_emb = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


def criar_indice(textos):
    emb = modelo_emb.encode(textos, normalize_embeddings=True).astype("float32")
    indice = faiss.IndexFlatIP(emb.shape[1])
    indice.add(emb)
    return indice


def texto_produto(p) -> str:
    sinonimos = ", ".join(CATEGORIAS[p["categoria"]][3])
    return f"{p['categoria']} ({sinonimos}). {p['nome']}. {p['specs']}. Ideal para {p['uso']}."


IDX_PRODUTOS = criar_indice([texto_produto(p) for p in PRODUTOS])

DOCS_CONHECIMENTO = FAQ_E_REGRAS + [
    {"fonte": f"produtos.json#{p['codigo']}",
     "texto": f"{p['codigo']} - {p['nome']}: {p['specs']}. Ideal para {p['uso']}. Preço: {brl(p['preco'])}. Estoque: {p['estoque']} unidades."}
    for p in PRODUTOS
]
IDX_CONHECIMENTO = criar_indice([d["texto"] for d in DOCS_CONHECIMENTO])

LIMIAR_SEMANTICO = 0.38   # abaixo disso o sistema se abstém
LIMIAR_DUVIDA = 0.35


def buscar_semantico(consulta: str, k: int = 6):
    q = modelo_emb.encode([consulta], normalize_embeddings=True).astype("float32")
    scores, ids = IDX_PRODUTOS.search(q, min(k, len(PRODUTOS)))
    res = [(PRODUTOS[i], float(s)) for s, i in zip(scores[0], ids[0]) if i != -1]
    if not res or res[0][1] < LIMIAR_SEMANTICO:
        return []
    topo = res[0][1]
    return [(p, s) for p, s in res if s >= LIMIAR_SEMANTICO and s >= topo - 0.12]


def categoria_dominante(res):
    if not res:
        return None
    cats = [p["categoria"] for p, _ in res[:3]]
    return max(set(cats), key=lambda c: (cats.count(c), c == cats[0]))

# ===== célula [10] =====
def _chave(frase: str) -> str:
    return " ".join(singular(t) for t in tokens(frase))


ALIAS_BASE = {}
for _cat, (_ic, _s, _p, _aliases) in CATEGORIAS.items():
    for _a in _aliases + [_cat]:
        ALIAS_BASE[_chave(_a)] = _cat

ARQ_MEMORIA = "/content/memoria_aliases.json" if os.path.isdir("/content") else "memoria_aliases.json"


def carregar_memoria() -> dict:
    try:
        with open(ARQ_MEMORIA, encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if v in CATEGORIAS}
    except Exception:
        return {}


def salvar_memoria():
    try:
        with open(ARQ_MEMORIA, "w", encoding="utf-8") as f:
            json.dump(ALIAS_APRENDIDOS, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


ALIAS_APRENDIDOS = carregar_memoria()


def alias_lookup(chave: str):
    return ALIAS_APRENDIDOS.get(chave) or ALIAS_BASE.get(chave)


def unigramas():
    return [k for k in list(ALIAS_BASE) + list(ALIAS_APRENDIDOS) if " " not in k]


def aprender(termo: str, categoria: str) -> bool:
    chave = _chave(termo)
    if not chave or len(chave.split()) > 3 or alias_lookup(chave):
        return False
    ALIAS_APRENDIDOS[chave] = categoria
    salvar_memoria()
    return True


LOG = []


def resumo_logs() -> pd.DataFrame:
    return pd.DataFrame(LOG)

# ===== célula [12] =====
STOP = set("""quero queria queremos gostaria preciso precisamos precisava procuro buscando comprar cotar cotacao cotacoes
ver veja mostrar mostre mostra exibir lista listar me um uma uns umas o a os as de do da dos das para pra pro por favor
x tem voces vcs ai ae qual quais algum alguns alguma algo coisa opcao opcoes modelo modelos que e em no na mais barato
baratos economico bom boa ate menos maximo abaixo acima minimo r reais real saber se tipo assim vende vendem existe
tenho pode poderia todos todas ola oi marca fabricante da""".split())

# [NOVO] palavras de enchimento / gírias que não devem virar "característica"
STOP |= set("""unidade unidades peca pecas estou precisando querendo procurando pegar pega levar leva
manda mande separa separe bota bote coloca coloque poe adiciona adicione traz arruma arrume ve dar
mano cara meu brother bro vei parceiro chefe beleza fechado entao dai bora vamos ser essa esse isso
voce voces tambem obrigado""".split())

NUM_PALAVRA = {"dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10}
UNIDADES = {"polegada", "pol", "gb", "tb", "mb", "hz", "mhz", "ghz", "va", "k", "w", "h", "ms", "dpi", "mah", "kg", "m"}
CUES_DUVIDA = {"garantia", "pagamento", "pagar", "pix", "boleto", "cartao", "parcela", "parcelar", "entrega", "frete",
               "prazo", "troca", "devolucao", "validade", "desconto", "diferenca", "funciona", "como", "porque",
               "horario", "endereco", "suporte", "assistencia", "explique", "explica"}
MARCAS_NORM = {normalizar(m): m for m in MARCAS}


# ---------- [NOVO] gírias, abreviações e erros comuns (aplicado na mensagem inteira) ----------
GIRIAS = {
    # verbos / abreviações
    "kero": "quero", "qro": "quero", "qero": "quero", "quer": "quero", "queru": "quero", "qria": "queria",
    "presiso": "preciso", "precizo": "preciso", "presizo": "preciso",
    "vc": "voce", "vcs": "voces", "pq": "porque", "tb": "tambem", "tbm": "tambem",
    "blz": "beleza", "vlw": "valeu", "pfv": "por favor", "pf": "por favor", "plz": "por favor",
    "q": "que", "to": "estou", "tou": "estou", "du": "do",
    # "unidade" escrito de várias formas
    "und": "unidade", "unid": "unidade", "unds": "unidade", "unids": "unidade", "unidad": "unidade",
    "unidadi": "unidade", "un": "unidade", "pcs": "unidade",
    # números
    "doiz": "dois", "trez": "tres", "qatro": "quatro", "cinko": "cinco", "par": "2", "duzia": "12",
    # produtos escritos errado ou em gíria
    "mous": "mouse", "maus": "mouse", "mause": "mouse", "mouzi": "mouse", "mausi": "mouse",
    "tecladu": "teclado", "moniter": "monitor", "monitr": "monitor", "telinha": "tela", "telona": "tela",
    "notbook": "notebook", "notebok": "notebook", "noutbuque": "notebook", "notinho": "notebook",
    "hedset": "headset", "hedfone": "headfone", "nobrek": "nobreak", "nobreque": "nobreak",
    "rotiador": "roteador", "roteadol": "roteador",
}


def limpar_msg(msg: str) -> str:
    """Normaliza a mensagem e corrige gírias/erros simples antes de qualquer interpretação."""
    n = normalizar(msg)
    n = re.sub(r"\b([a-z]{3,}?)zinh[oa]s?\b", r"\1", n)          # monitorzinho -> monitor
    return re.sub(r"[a-z]+", lambda m: GIRIAS.get(m.group(0), m.group(0)), n)


# ---------- [NOVO] "o mais barato" / "o mais caro" (com tolerância a erro de digitação) ----------
PAL_BARATO = ["barato", "barata", "baratinho", "baratinha", "economico", "simples"]
PAL_CARO = ["caro", "cara", "carissimo", "top", "premium", "topo"]


def _sim(w: str, lista) -> float:
    return max(difflib.SequenceMatcher(None, w, x).ratio() for x in lista)


def detectar_ordem(t: str):
    """Recebe texto normalizado. Retorna ('barato'|'caro'|None, texto sem a expressão)."""
    m = re.search(r"\b(?:menor|maior)\s+(?:preco|valor)\b", t)
    if m:
        return ("barato" if m.group(0).startswith("menor") else "caro"), t.replace(m.group(0), " ")
    m = re.search(r"\bmais\s+em\s+conta\b", t)
    if m:
        return "barato", t.replace(m.group(0), " ")
    m = re.search(r"\b(?:top|topo)\s+de\s+linha\b", t)
    if m:
        return "caro", t.replace(m.group(0), " ")
    m = re.search(r"\bmais\s+([a-z]{3,})\b", t)
    if m:
        sb, sc = _sim(m.group(1), PAL_BARATO), _sim(m.group(1), PAL_CARO)
        if max(sb, sc) >= 0.72:
            return ("barato" if sb >= sc else "caro"), t.replace(m.group(0), " ")
    return None, t


def _numero(s: str, mil: bool = False):
    s = s.strip(".,")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    else:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v * 1000 if mil else v


def achar_categoria(toks):
    """Retorna (categoria, método, (início, fim)). Ordem: alias exato -> fuzzy (erros de digitação)."""
    sing = [singular(t) for t in toks]
    n = len(sing)
    for tam in range(min(4, n), 0, -1):
        for i in range(n - tam + 1):
            cat = alias_lookup(" ".join(sing[i:i + tam]))
            if cat:
                return cat, "alias", (i, i + tam)
    candidatos = unigramas()
    for i, t in enumerate(sing):
        if len(t) >= 5 and t.isalpha() and toks[i] not in STOP:
            m = difflib.get_close_matches(t, candidatos, n=1, cutoff=0.78)
            if m:
                return alias_lookup(m[0]), "fuzzy", (i, i + 1)
    return None, None, None


def parse_item(trecho: str) -> dict:
    """Extrai categoria, quantidade, ordem (mais barato/caro), faixa de preço, marca e características de um trecho."""
    t = normalizar(trecho)
    pmax = pmin = None
    m = re.search(r"\b(?:ate|abaixo de|menos de|no maximo|maximo|max)\s+(?:de\s+)?(?:r\s*)?(\d[\d.,]*)(\s*mil)?", t)
    if m:
        pmax = _numero(m.group(1), bool(m.group(2)))
        t = t.replace(m.group(0), " ")
    m = re.search(r"\b(?:acima de|a partir de|minimo de|minimo|mais de)\s+(?:r\s*)?(\d[\d.,]*)(\s*mil)?", t)
    if m:
        pmin = _numero(m.group(1), bool(m.group(2)))
        t = t.replace(m.group(0), " ")

    ordem, t = detectar_ordem(t)          # [NOVO] "mais barato" / "mais caro"

    toks = tokens(t)
    cat, metodo, span = achar_categoria(toks)
    usados = set(range(*span)) if span else set()

    qtd = None
    for i, tk in enumerate(toks):
        if i in usados:
            continue
        if tk in NUM_PALAVRA:
            qtd = NUM_PALAVRA[tk]; usados.add(i); break
        if tk.isdigit() and int(tk) <= 99:
            prox = singular(toks[i + 1]) if i + 1 < len(toks) else ""
            antes_da_categoria = span is None or i < span[0]
            # [ALTERADO] "mouse 2 unidades" também conta como quantidade
            if prox in UNIDADES or (not antes_da_categoria and prox != "unidade"):
                continue
            qtd = int(tk); usados.add(i)
            if prox == "x":
                usados.add(i + 1)
            break

    marca = None
    for i, tk in enumerate(toks):
        if tk in MARCAS_NORM and i not in usados:
            marca = MARCAS_NORM[tk]; usados.add(i)

    atributos = [tk for i, tk in enumerate(toks) if i not in usados and tk not in STOP and tk != "x"]
    termo = " ".join(toks[span[0]:span[1]]) if span else " ".join(atributos)
    return {"termo": termo, "quantidade": qtd, "preco_max": pmax, "preco_min": pmin, "marca": marca,
            "atributos": atributos if cat else [], "categoria": cat, "metodo": metodo, "ordem": ordem}


def heuristica_pedido(msg: str):
    """Tenta entender o pedido sem LLM. Só aceita se todo trecho tiver categoria clara (alias ou erro de digitação)."""
    n = normalizar(msg)
    n = re.sub(r"^(?:oi|ola|bom dia|boa tarde|boa noite)[,\s]+", "", n)
    toks = tokens(n)
    if not toks or any(t in CUES_DUVIDA or t.startswith("compar") for t in toks):
        return None
    partes = [p for p in re.split(r"\s+e\s+|;|,\s+|\s+alem de\s+", n) if p.strip()]
    itens = []
    for p in partes:
        it = parse_item(p)
        if not it["categoria"]:
            return None
        itens.append(it)
    return itens or None


def resolver_item(item: dict) -> dict:
    """Garante que o item tenha categoria (alias/fuzzy) ou lista semântica. Usado nos itens vindos do LLM."""
    if item.get("categoria"):
        return item
    base = parse_item(" ".join([str(item.get("termo") or "")] + [str(a) for a in item.get("atributos") or []]))
    for campo in ("quantidade", "preco_max", "preco_min", "marca", "ordem"):      # [ALTERADO] + "ordem"
        if item.get(campo) in (None, "", 0):
            item[campo] = base.get(campo)
    if base["categoria"]:
        item.update(categoria=base["categoria"], metodo=base["metodo"])
        item["atributos"] = list({*base["atributos"], *[a for a in tokens(" ".join(item.get("atributos") or []))
                                                       if a not in STOP]})
        return item
    consulta = " ".join([str(item.get("termo") or "")] + [str(a) for a in item.get("atributos") or []]).strip()
    res = buscar_semantico(consulta) if consulta else []
    item["categoria"] = None
    item["semantico"] = [p for p, _ in res]
    item["categoria_dominante"] = categoria_dominante(res)
    item["metodo"] = "semantico" if res else "nenhum"
    return item

# ===== célula [14] =====
def estoque_txt(p) -> str:
    if p["estoque"] <= 0:
        return "❌ esgotado"
    if p["estoque"] <= 3:
        return f"⚠️ {p['estoque']} un."
    return f"✅ {p['estoque']} un."


def tabela_md(produtos) -> str:
    linhas = ["| # | Produto | Especificações | Preço | Estoque |", "|:-:|---|---|--:|:-:|"]
    for i, p in enumerate(produtos, 1):
        linhas.append(f"| {i} | **{p['nome']}**<br>`{p['codigo']}` | {p['specs']} | {brl(p['preco'])} | {estoque_txt(p)} |")
    return "\n".join(linhas)


def score_atributos(p, attrs) -> int:
    texto = [singular(t) for t in tokens(" ".join([p["nome"], p["marca"], p["specs"], p["uso"]]))]
    conj, pares = set(texto), set(zip(texto, texto[1:]))
    q = [singular(t) for t in tokens(" ".join(attrs))]
    sc = 0
    for i, t in enumerate(q):
        if t not in ("com", "sem") and t in conj:
            sc += 1
        if i + 1 < len(q) and (t, q[i + 1]) in pares:
            sc += 1
    return sc


def filtrar_e_ordenar(cat: str, item: dict):
    todos = sorted([p for p in PRODUTOS if p["categoria"] == cat], key=lambda p: p["preco"])
    lista, notas = list(todos), []

    if item.get("marca"):
        f = [p for p in lista if normalizar(p["marca"]) == normalizar(item["marca"])]
        if f:
            lista = f; notas.append(f"marca {f[0]['marca']}")
        else:
            notas.append(f"não temos {CATEGORIAS[cat][1]} da marca {item['marca']}, mostrando todas as marcas")
    if item.get("preco_max"):
        f = [p for p in lista if p["preco"] <= item["preco_max"]]
        if f:
            lista = f; notas.append(f"até {brl(item['preco_max'])}")
        else:
            lista = lista[:3]; notas.append(f"nenhum modelo até {brl(item['preco_max'])}; estes são os mais em conta")
    if item.get("preco_min"):
        f = [p for p in lista if p["preco"] >= item["preco_min"]]
        if f:
            lista = f; notas.append(f"a partir de {brl(item['preco_min'])}")
    attrs = [a for a in (item.get("atributos") or []) if a]
    if attrs:
        sc = {p["codigo"]: score_atributos(p, attrs) for p in lista}
        mx = max(sc.values())
        if mx >= 1:
            f = [p for p in lista if sc[p["codigo"]] == mx]
            if len(f) < len(lista):
                notas.append("características: " + " ".join(attrs))
            lista = f
        else:
            notas.append(f"não achei exatamente “{' '.join(attrs)}”, mostrando todos os modelos")
    return lista, todos, notas

# ===== célula [16] =====
PROMPT_NLU = """Você interpreta mensagens de clientes de uma loja de informática (NexaTech) e responde SOMENTE com um JSON válido.

Formato:
{"intencao": "...", "itens": [...], "referencias": [...]}

Intenções possíveis:
- "buscar": o cliente quer ver, pedir ou cotar produtos (inclui "vocês têm monitor?", "preciso de algo para videochamada"). Preencha "itens". NUNCA escolha um modelo específico por conta própria.
- "escolher": o cliente escolhe entre as OPÇÕES EXIBIDAS ("a segunda", "quero a 3", "o mais barato", "o da Vektra"). Preencha "referencias" usando o número da opção.
- "comparar": quer comparar opções exibidas ou códigos. "referencias" com 2 ou mais.
- "remover": tirar item do carrinho. Preencha "referencias".
- "ver_carrinho", "limpar", "finalizar", "catalogo_geral", "saudacao"
- "gerenciar_cotacoes": o cliente quer listar o histórico, abrir uma cotação nova, voltar para uma cotação anterior, ver uma cotação, descartar ou finalizar uma COTAÇÃO inteira (não confunda com escolher ou remover produtos). Preencha "acoes": lista de {"acao": "listar" ou "nova" ou "abrir" ou "ver" ou "descartar" ou "finalizar", "numeros": [números das cotações citadas; ordinais viram número; [] se não citar]}. "itens" e "referencias" ficam vazios.
- "duvida": pergunta sobre garantia, pagamento, entrega, troca, validade, desconto, ou sobre como/por que/qual a diferença.
- "fora_escopo": assunto sem relação com a loja.

O cliente pode escrever com gírias, abreviações e erros de português (ex.: "kero", "mause", "me ve", "fonezinho"). Interprete a intenção mesmo assim.

Campos de "itens": {"termo": "produto como o cliente disse, no singular, sem quantidade", "quantidade": inteiro ou null, "preco_max": número ou null, "preco_min": número ou null, "marca": texto ou null, "atributos": ["características pedidas, ex.: sem fio, 27 polegadas, gamer"], "ordem": "barato" ou "caro" ou null}
Use "ordem" somente quando o cliente pedir explicitamente "o mais barato"/"o mais em conta" ("barato") ou "o mais caro"/"o top de linha" ("caro").
Campos de "referencias": {"opcao": número ou null, "codigo": "INFxxx" ou null, "quantidade": inteiro ou null}

Exemplos:
Mensagem: quero um fone sem fio até 300 reais
{"intencao":"buscar","itens":[{"termo":"fone","quantidade":null,"preco_max":300,"preco_min":null,"marca":null,"atributos":["sem fio"],"ordem":null}],"referencias":[]}
Mensagem: preciso de algo pra fazer videochamada e de 2 nobreaks
{"intencao":"buscar","itens":[{"termo":"algo para videochamada","quantidade":null,"preco_max":null,"preco_min":null,"marca":null,"atributos":[],"ordem":null},{"termo":"nobreak","quantidade":2,"preco_max":null,"preco_min":null,"marca":null,"atributos":[],"ordem":null}],"referencias":[]}
Mensagem: me ve 2 mause mais em conta
{"intencao":"buscar","itens":[{"termo":"mouse","quantidade":2,"preco_max":null,"preco_min":null,"marca":null,"atributos":[],"ordem":"barato"}],"referencias":[]}
Mensagem: o segundo, quero 3
{"intencao":"escolher","itens":[],"referencias":[{"opcao":2,"codigo":null,"quantidade":3}]}
Mensagem: pode ser o mais barato (opções: 1 por R$ 590, 2 por R$ 750)
{"intencao":"escolher","itens":[],"referencias":[{"opcao":1,"codigo":null,"quantidade":null}]}
Mensagem: desisti da terceira e da segunda, volta pra primeira
{"intencao":"gerenciar_cotacoes","itens":[],"referencias":[],"acoes":[{"acao":"descartar","numeros":[3,2]},{"acao":"abrir","numeros":[1]}]}
Mensagem: quero ver o que eu já cotei
{"intencao":"gerenciar_cotacoes","itens":[],"referencias":[],"acoes":[{"acao":"listar","numeros":[]}]}
Mensagem: qual a diferença entre garantia e troca?
{"intencao":"duvida","itens":[],"referencias":[]}
Mensagem: qual a capital da França?
{"intencao":"fora_escopo","itens":[],"referencias":[]}"""


def interpretar_llm(msg: str, s) -> dict:
    if s.opcoes:
        ctx = "\n".join(f"{i}) {POR_CODIGO[c]['codigo']} - {POR_CODIGO[c]['nome']} - {brl(POR_CODIGO[c]['preco'])}"
                        for i, c in enumerate(s.opcoes, 1))
    else:
        ctx = "(nenhuma)"
    saida = chamar_llm(PROMPT_NLU, f"OPÇÕES EXIBIDAS AGORA:\n{ctx}\n\nMensagem: {msg}")
    dados = extrair_json(saida)
    dados.setdefault("intencao", "duvida")
    dados["itens"] = [i for i in (dados.get("itens") or []) if isinstance(i, dict)]
    dados["referencias"] = [r for r in (dados.get("referencias") or []) if isinstance(r, dict)]
    return dados

# ===== célula [18] =====
class Cotacao:
    """Uma cotação do histórico: número próprio, carrinho próprio e status."""

    def __init__(self, numero: int):
        self.numero = numero
        self.carrinho = {}              # código -> quantidade
        self.status = "aberta"          # aberta | finalizada | descartada
        self.criada_em = datetime.now()
        self.atualizada_em = self.criada_em
        self.finalizada_em = None
        self.pdf = None

    def total(self) -> float:
        return sum(POR_CODIGO[cod]["preco"] * q for cod, q in self.carrinho.items())

    def unidades(self) -> int:
        return sum(self.carrinho.values())

    def tocar(self):
        self.atualizada_em = datetime.now()


class Sessao:
    def __init__(self):
        self.cotacoes = []        # histórico: todas as cotações desta conversa
        self.ativa = None         # cotação que está sendo editada agora
        self.fila = []            # itens ainda sem modelo escolhido
        self.item_atual = None
        self.opcoes = []          # códigos exibidos na última tabela
        self.completos = []       # todos os códigos da categoria (comando "todos")
        self.ultima_proposta = None
        self.nome = getattr(self, "nome", None)      # [NOVO] primeiro nome do cliente (se ele disser)
        self.nova_cotacao()

    @property
    def carrinho(self) -> dict:   # o resto do código continua usando s.carrinho (= carrinho da cotação ativa)
        return self.ativa.carrinho

    def nova_cotacao(self) -> Cotacao:
        numero = max((c.numero for c in self.cotacoes), default=0) + 1
        self.ativa = Cotacao(numero)
        self.cotacoes.append(self.ativa)
        return self.ativa

    def buscar(self, numero: int):
        return next((c for c in self.cotacoes if c.numero == numero), None)

    def limpar_contexto(self) -> bool:
        """Fecha opções/fila da conversa. Retorna True se havia itens esperando escolha."""
        havia_fila = bool(self.fila)
        self.fila, self.opcoes, self.completos, self.item_atual = [], [], [], None
        return havia_fila


SESSOES = {}


def get_sessao(sid: str) -> Sessao:
    if sid not in SESSOES:
        SESSOES[sid] = Sessao()
    return SESSOES[sid]


def _int_ou_none(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def mostrar_opcoes(s: Sessao, item: dict) -> str:
    """Monta a tabela de opções do item. NUNCA escolhe um modelo pelo cliente."""
    s.item_atual = item
    qtd = item.get("quantidade")
    pedido = f" (você pediu **{qtd} un.**)" if qtd and qtd > 1 else ""

    if item.get("categoria"):
        cat = item["categoria"]
        lista, todos, notas = filtrar_e_ordenar(cat, item)
        s.completos = [p["codigo"] for p in todos]
        icone, _, plural, _ = CATEGORIAS[cat]
        titulo = f"{icone} **{plural}**{pedido}: encontrei {len(lista)} modelo(s)"
        if notas:
            titulo += " · _" + " · ".join(notas) + "_"
        extra = ""
        if len(lista) < len(todos):
            extra = f"\n\nTenho mais {len(todos) - len(lista)} modelo(s) de {CATEGORIAS[cat][1]}; digite **todos** para ver."
    elif item.get("semantico"):
        lista = item["semantico"][:5]
        s.completos = []
        titulo = f"🔎 Não tenho exatamente “{item.get('termo')}”, mas estas opções combinam com o que você descreveu{pedido}:"
        extra = ""
    else:
        s.opcoes = []
        cats = ", ".join(c[2] for c in CATEGORIAS.values())
        return (f"Não encontrei “{item.get('termo') or 'esse item'}” no catálogo da NexaTech. "
                f"Trabalho com: {cats}. Digite **catálogo** para ver tudo ou posso encaminhar para um atendente.")

    s.opcoes = [p["codigo"] for p in lista]
    return (f"{titulo}\n\n{tabela_md(lista)}{extra}\n\n"
            "👉 Digite o **número** da opção (ex.: `2`). Para outra quantidade: `2 x 5` (opção 2, cinco unidades). "
            "Também aceito “o mais barato”, “comparar 1 e 3” ou o código.")


# [NOVO] cliente pediu explicitamente "o mais barato/caro": adiciona direto
def adicionar_por_ordem(s: Sessao, item: dict) -> str:
    """Cliente pediu explicitamente 'o mais barato/caro': adiciona direto (ignora esgotados)."""
    cat = item["categoria"]
    lista, todos, notas = filtrar_e_ordenar(cat, item)
    s.item_atual = item
    s.completos = [p["codigo"] for p in todos]
    s.opcoes = [p["codigo"] for p in lista]
    disponiveis = [p for p in lista if p["estoque"] > 0]
    if not disponiveis:
        return mostrar_opcoes(s, item)
    pick = min if item["ordem"] == "barato" else max
    alvo = pick(disponiveis, key=lambda p: p["preco"])
    ideal = pick(lista, key=lambda p: p["preco"])
    rotulo = "mais barato" if item["ordem"] == "barato" else "mais caro"
    intro = f"🎯 Entendi: o **{rotulo}** de {CATEGORIAS[cat][1]}."
    if ideal["codigo"] != alvo["codigo"]:
        intro += f" O {ideal['nome']} está esgotado, então peguei o {rotulo} disponível."
    return intro + "\n\n" + adicionar(s, alvo, item.get("quantidade"))


# [ALTERADO] agora também trata itens com "ordem"
def avancar_fila(s: Sessao) -> str:
    """Mostra as opções do próximo item da fila (ou adiciona direto se pediu 'mais barato/caro')."""
    avisos = []
    while s.fila:
        item = resolver_item(s.fila.pop(0))
        if item.get("ordem") in ("barato", "caro") and item.get("categoria"):
            return "\n\n".join(avisos + [adicionar_por_ordem(s, item)])
        texto = mostrar_opcoes(s, item)
        if s.opcoes:
            return "\n\n".join(avisos + [texto])
        avisos.append(texto)
    return "\n\n".join(avisos)


def iniciar_busca(s: Sessao, itens) -> str:
    s.fila = list(itens)
    s.opcoes, s.item_atual = [], None
    texto = avancar_fila(s)
    if len(itens) > 1 and s.opcoes:
        texto = f"Vamos item por item ({len(itens)} produtos no pedido).\n\n" + texto
    return texto


def linhas_carrinho(s: Sessao, c: Cotacao = None):
    c = c or s.ativa
    total = 0.0
    linhas = ["| # | Produto | Qtd | Unitário | Subtotal |", "|:-:|---|:-:|--:|--:|"]
    for i, (cod, q) in enumerate(c.carrinho.items(), 1):
        p = POR_CODIGO[cod]
        sub = p["preco"] * q          # cálculo determinístico: o LLM nunca calcula
        total += sub
        linhas.append(f"| {i} | {p['nome']} (`{cod}`) | {q} | {brl(p['preco'])} | {brl(sub)} |")
    return linhas, total


STATUS_TXT = {"aberta": "🟡 Em andamento", "finalizada": "✅ Finalizada", "descartada": "🗑️ Descartada"}


def status_txt(c: Cotacao) -> str:
    if c.status == "aberta" and not c.carrinho:
        return "⚪ Vazia"
    return STATUS_TXT[c.status]


def resumo_itens(c: Cotacao, maximo: int = 2) -> str:
    if not c.carrinho:
        return "—"
    partes = [f"{q}× {POR_CODIGO[cod]['nome']}" for cod, q in c.carrinho.items()]
    txt = ", ".join(partes[:maximo])
    return txt + (f" +{len(partes) - maximo} item(ns)" if len(partes) > maximo else "")


def historico_md(s: Sessao) -> str:
    """Tabela com todas as cotações da conversa."""
    linhas = ["| # | Status | Itens | Total | Atualizada |", "|:-:|---|---|--:|:-:|"]
    for c in s.cotacoes:
        atual = " ◀ atual" if c is s.ativa else ""
        linhas.append(f"| **{c.numero}**{atual} | {status_txt(c)} | {resumo_itens(c)} | {brl(c.total())} | {c.atualizada_em:%H:%M} |")
    return ("🗂️ **Histórico de cotações**\n\n" + "\n".join(linhas) +
            "\n\nAtalhos: `abrir cotação 1` · `descartar cotação 2` · `nova cotação` · `finalizar cotação 1`")


def painel_md(s: Sessao) -> str:
    """Resumo curto para o painel lateral do chat."""
    linhas = []
    for c in s.cotacoes:
        seta = "▶ " if c is s.ativa else ""
        linhas.append(f"- {seta}**#{c.numero}** · {status_txt(c)} · {c.unidades()} un. · {brl(c.total())}")
    return "\n".join(linhas)


def ver_carrinho(s: Sessao, c: Cotacao = None) -> str:
    """Mostra os itens de uma cotação (por padrão, a ativa)."""
    so_olhando = c is not None and c is not s.ativa
    c = c or s.ativa
    if not c.carrinho:
        return f"🛒 A **cotação #{c.numero}** está vazia. Digite o que procura (ex.: `monitor`, `fone sem fio`, `mouse até 100`)."
    linhas, total = linhas_carrinho(s, c)
    if so_olhando:
        rodape = f"Você está só olhando. Digite **abrir cotação {c.numero}** para continuar nela."
    elif c.status == "finalizada":
        rodape = "Esta cotação já foi finalizada. Digite **nova cotação** para começar outra."
    else:
        rodape = ("Digite **finalizar** para gerar a cotação, **remover 1** para tirar um item, "
                  "**nova cotação** para começar outra sem perder esta ou continue buscando.")
    return (f"🛒 **Cotação #{c.numero}** · {status_txt(c)}\n\n" + "\n".join(linhas) +
            f"\n\n**Total: {brl(total)}** · no PIX: {brl(total * (1 - DESCONTO_PIX))}\n\n" + rodape)


def adicionar(s: Sessao, p: dict, qtd) -> str:
    if p["estoque"] <= 0:
        return f"❌ O **{p['nome']}** está esgotado. Escolha outra opção da lista."
    aviso_nova = ""
    if s.ativa.status == "finalizada":          # cotação fechada não recebe mais itens: abre outra
        anterior = s.ativa
        s.nova_cotacao()
        aviso_nova = f"ℹ️ A cotação #{anterior.numero} já estava finalizada, então abri a **cotação #{s.ativa.numero}** para este item.\n\n"
    qtd = qtd or (s.item_atual or {}).get("quantidade") or 1
    qtd = max(int(qtd), 1)
    aviso = ""
    ja = s.carrinho.get(p["codigo"], 0)
    if ja + qtd > p["estoque"]:
        qtd = max(p["estoque"] - ja, 0)
        aviso = f"\n\n⚠️ Só temos {p['estoque']} un. em estoque; ajustei a quantidade."
        if qtd == 0:
            return f"⚠️ Você já tem todo o estoque disponível de **{p['nome']}** no carrinho."
    s.carrinho[p["codigo"]] = ja + qtd
    s.ativa.tocar()

    aprendeu = ""
    it = s.item_atual or {}
    if it.get("metodo") == "fuzzy" or (it.get("metodo") == "semantico" and it.get("categoria_dominante") == p["categoria"]):
        if aprender(it.get("termo", ""), p["categoria"]):
            aprendeu = f"\n\n🧠 Aprendi que “{it['termo']}” se refere a **{p['categoria']}**. Da próxima vez entendo direto."

    msg = aviso_nova + f"✅ Adicionado na **cotação #{s.ativa.numero}**: **{qtd} × {p['nome']}** = {brl(p['preco'] * qtd)}{aviso}{aprendeu}"
    if s.fila:
        return msg + "\n\n---\n\n" + avancar_fila(s)
    _, total = linhas_carrinho(s)
    un = s.ativa.unidades()
    return (msg + f"\n\n🛒 Total da cotação #{s.ativa.numero}: **{brl(total)}** ({un} {'unidade' if un == 1 else 'unidades'}). "
            "Quer outro produto? É só dizer. Digite **carrinho** para ver, **finalizar** para gerar a cotação "
            "ou **nova cotação** para começar outra sem perder esta.")


def resolver_ref(s: Sessao, ref: dict):
    cod = str(ref.get("codigo") or "").upper().strip()
    if cod in POR_CODIGO:
        return POR_CODIGO[cod]
    op = _int_ou_none(ref.get("opcao"))
    if op and 1 <= op <= len(s.opcoes):
        return POR_CODIGO[s.opcoes[op - 1]]
    return None


def escolher(s: Sessao, refs) -> str:
    if not refs:
        return "Não entendi qual opção você quer. Digite o número da tabela (ex.: `2`)."
    if not s.opcoes and not any(str(r.get("codigo") or "").upper() in POR_CODIGO for r in refs):
        return "Ainda não mostrei opções. Diga o que procura (ex.: `monitor`)."
    saida = []
    for r in refs:
        p = resolver_ref(s, r)
        if not p:
            saida.append("Essa opção não existe na lista. Digite um número da tabela.")
            continue
        saida.append(adicionar(s, p, _int_ou_none(r.get("quantidade"))))
    return "\n\n".join(saida)


def comparar(s: Sessao, refs) -> str:
    prods = [p for p in (resolver_ref(s, r) for r in refs) if p]
    prods = list({p["codigo"]: p for p in prods}.values())
    if len(prods) < 2:
        return "Para comparar, mostre uma lista e diga, por exemplo, `comparar 1 e 3` (ou use os códigos)."
    cab = "| | " + " | ".join(f"**{p['nome']}**" for p in prods) + " |"
    sep = "|---|" + "---|" * len(prods)
    linhas = [cab, sep,
              "| Código | " + " | ".join(f"`{p['codigo']}`" for p in prods) + " |",
              "| Preço | " + " | ".join(brl(p["preco"]) for p in prods) + " |",
              "| Especificações | " + " | ".join(p["specs"] for p in prods) + " |",
              "| Ideal para | " + " | ".join(p["uso"] for p in prods) + " |",
              "| Estoque | " + " | ".join(estoque_txt(p) for p in prods) + " |"]
    barato = min(prods, key=lambda p: p["preco"])
    return "⚖️ **Comparação**\n\n" + "\n".join(linhas) + f"\n\nMais em conta: **{barato['nome']}**. Digite o número da opção para adicionar ao carrinho."


def remover(s: Sessao, ref: str) -> str:
    if s.ativa.status == "finalizada":
        return f"A cotação #{s.ativa.numero} já foi finalizada e não pode ser alterada. Digite **nova cotação** para começar outra."
    cods = list(s.carrinho)
    cod = ref.upper() if ref.upper() in s.carrinho else (cods[int(ref) - 1] if ref.isdigit() and 1 <= int(ref) <= len(cods) else None)
    if not cod:
        return "Não achei esse item no carrinho. Digite **carrinho** para ver a numeração."
    s.carrinho.pop(cod)
    s.ativa.tocar()
    return f"🗑️ Removido: {POR_CODIGO[cod]['nome']}.\n\n" + ver_carrinho(s)


def gerar_pdf(s: Sessao, numero: str, emissao: datetime, validade: datetime, total: float) -> str:
    """Gera uma cotação comercial NexaTech com layout profissional."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        KeepTogether, HRFlowable
    )
    from reportlab.pdfbase.pdfmetrics import stringWidth

    pasta = "/content/propostas" if os.path.isdir("/content") else "propostas"
    os.makedirs(pasta, exist_ok=True)
    caminho = f"{pasta}/NexaTech_Cotacao_{numero}.pdf"

    NAVY = colors.HexColor("#14243A")
    BLUE = colors.HexColor("#2563EB")
    CYAN = colors.HexColor("#16B8A6")
    INK = colors.HexColor("#263449")
    MUTED = colors.HexColor("#718096")
    LIGHT = colors.HexColor("#F2F6FA")
    LINE = colors.HexColor("#DCE5EF")
    WHITE = colors.white

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Brand", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=23, leading=27, textColor=WHITE, alignment=TA_LEFT, spaceAfter=2))
    styles.add(ParagraphStyle(name="BrandSub", parent=styles["Normal"], fontSize=9,
        leading=12, textColor=colors.HexColor("#C8D6E8")))
    styles.add(ParagraphStyle(name="DocTitle", parent=styles["Heading1"], fontSize=19,
        leading=23, textColor=NAVY, spaceAfter=4))
    styles.add(ParagraphStyle(name="MutedSmall", parent=styles["Normal"], fontSize=8,
        leading=11, textColor=MUTED))
    styles.add(ParagraphStyle(name="BodyCustom", parent=styles["BodyText"], fontSize=8.5,
        leading=12, textColor=INK))
    styles.add(ParagraphStyle(name="Product", parent=styles["BodyText"], fontSize=8.2,
        leading=11, textColor=INK))
    styles.add(ParagraphStyle(name="TableHead", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8, leading=10, textColor=WHITE))
    styles.add(ParagraphStyle(name="TotalLabel", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9, leading=12, textColor=NAVY))
    styles.add(ParagraphStyle(name="TotalValue", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=BLUE, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="PixValue", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=10, leading=13, textColor=CYAN, alignment=TA_RIGHT))

    def rodape(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(18*mm, 16*mm, w-18*mm, 16*mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18*mm, 10.5*mm, "NexaTech  |  Tecnologia que conecta resultados")
        canvas.drawRightString(w-18*mm, 10.5*mm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(caminho, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                            topMargin=15*mm, bottomMargin=23*mm,
                            title=f"Cotação NexaTech {numero}", author="NexaTech")
    elementos = []

    cabecalho = Table([
        [Paragraph("NexaTech", styles["Brand"]),
         Paragraph("<b>PROPOSTA COMERCIAL</b><br/><font size='8' color='#C8D6E8'>COTAÇÃO DE PRODUTOS</font>", styles["BrandSub"])]
    ], colWidths=[100*mm, 72*mm], rowHeights=[25*mm])
    cabecalho.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 7*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 6*mm),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
        ("BOX", (0,0), (-1,-1), 0, NAVY),
    ]))
    elementos += [cabecalho, Spacer(1, 9*mm),
        Paragraph("Sua cotação está pronta.", styles["DocTitle"]),
        Paragraph("Confira os itens, quantidades e valores apresentados nesta proposta.", styles["MutedSmall"]),
        Spacer(1, 6*mm)]

    info = Table([
        [Paragraph("<font color='#718096' size='7'>NÚMERO DA COTAÇÃO</font><br/><b>%s</b>" % numero, styles["BodyCustom"]),
         Paragraph("<font color='#718096' size='7'>DATA DE EMISSÃO</font><br/><b>%s</b>" % emissao.strftime("%d/%m/%Y"), styles["BodyCustom"]),
         Paragraph("<font color='#718096' size='7'>VÁLIDA ATÉ</font><br/><b>%s</b>" % validade.strftime("%d/%m/%Y"), styles["BodyCustom"])]
    ], colWidths=[64*mm, 54*mm, 54*mm])
    info.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),LIGHT), ("BOX",(0,0),(-1,-1),0.6,LINE),
        ("INNERGRID",(0,0),(-1,-1),0.4,LINE), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("TOPPADDING",(0,0),(-1,-1),4*mm), ("BOTTOMPADDING",(0,0),(-1,-1),4*mm),
        ("LEFTPADDING",(0,0),(-1,-1),4*mm)
    ]))
    elementos += [info, Spacer(1, 8*mm)]

    dados = [[Paragraph("CÓDIGO", styles["TableHead"]),
              Paragraph("PRODUTO / DESCRIÇÃO", styles["TableHead"]),
              Paragraph("QTD.", styles["TableHead"]),
              Paragraph("VALOR UNIT.", styles["TableHead"]),
              Paragraph("SUBTOTAL", styles["TableHead"])]]
    for cod, q in s.carrinho.items():
        p = POR_CODIGO[cod]
        descricao = f"<b>{escape(p['nome'])}</b><br/><font size='7' color='#718096'>{escape(p['specs'])}</font>"
        dados.append([Paragraph(escape(cod), styles["Product"]),
                      Paragraph(descricao, styles["Product"]),
                      Paragraph(str(q), styles["Product"]),
                      Paragraph(brl(p["preco"]), styles["Product"]),
                      Paragraph(f"<b>{brl(p['preco'] * q)}</b>", styles["Product"])])

    tabela = Table(dados, colWidths=[22*mm, 78*mm, 13*mm, 29*mm, 30*mm], repeatRows=1, hAlign="LEFT")
    tabela.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),BLUE), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),3*mm), ("RIGHTPADDING",(0,0),(-1,-1),3*mm),
        ("TOPPADDING",(0,0),(-1,0),3.2*mm), ("BOTTOMPADDING",(0,0),(-1,0),3.2*mm),
        ("TOPPADDING",(0,1),(-1,-1),3*mm), ("BOTTOMPADDING",(0,1),(-1,-1),3*mm),
        ("LINEBELOW",(0,1),(-1,-1),0.45,LINE),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,LIGHT]),
        ("ALIGN",(2,0),(-1,-1),"RIGHT"),
    ]))
    elementos += [tabela, Spacer(1, 6*mm)]

    pix = total * (1 - DESCONTO_PIX)
    resumo = Table([
        [Paragraph("TOTAL DA COTAÇÃO", styles["TotalLabel"]), Paragraph(brl(total), styles["TotalValue"])],
        [Paragraph(f"Condição especial no PIX ({int(DESCONTO_PIX*100)}% de desconto)", styles["BodyCustom"]),
         Paragraph(brl(pix), styles["PixValue"])]
    ], colWidths=[105*mm, 67*mm])
    resumo.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),LIGHT), ("BOX",(0,0),(-1,-1),0.7,LINE),
        ("LINEBELOW",(0,0),(-1,0),0.5,LINE), ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),5*mm), ("RIGHTPADDING",(0,0),(-1,-1),5*mm),
        ("TOPPADDING",(0,0),(-1,-1),4*mm), ("BOTTOMPADDING",(0,0),(-1,-1),4*mm)
    ]))
    elementos += [resumo, Spacer(1, 8*mm)]

    condicoes = [
        Paragraph("CONDIÇÕES COMERCIAIS", styles["TableHead"]),
        Paragraph(f"• Validade desta cotação: {VALIDADE_DIAS} dias, até {validade:%d/%m/%Y}.<br/>"
                  "• Valores e disponibilidade sujeitos à confirmação no momento do fechamento.<br/>"
                  "• Condições de pagamento, entrega e frete devem ser confirmadas com o atendimento NexaTech.<br/>"
                  "• Este documento é uma cotação comercial e não substitui nota fiscal.", styles["BodyCustom"])
    ]
    bloco = Table([[condicoes]], colWidths=[172*mm])
    bloco.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),WHITE), ("BOX",(0,0),(-1,-1),0.7,LINE),
        ("LEFTPADDING",(0,0),(-1,-1),5*mm), ("RIGHTPADDING",(0,0),(-1,-1),5*mm),
        ("TOPPADDING",(0,0),(-1,-1),4*mm), ("BOTTOMPADDING",(0,0),(-1,-1),4*mm)
    ]))
    elementos += [KeepTogether(bloco), Spacer(1, 5*mm),
        Paragraph("Obrigado por escolher a NexaTech. Será um prazer atender você.", styles["MutedSmall"])]

    doc.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    return caminho


def gerar_pdf_sessao(s: Sessao) -> str:
    c = s.ativa
    if not c.carrinho:
        raise ValueError("O carrinho está vazio.")
    agora = datetime.now()
    numero = f"{agora:%Y%m%d-%H%M%S}-C{c.numero}"
    validade = agora + timedelta(days=VALIDADE_DIAS)
    c.pdf = s.ultima_proposta = gerar_pdf(s, numero, agora, validade, c.total())
    return c.pdf


def finalizar(s: Sessao) -> str:
    """Finaliza a cotação ativa: gera o PDF e trava a cotação (itens novos vão para outra)."""
    c = s.ativa
    if not c.carrinho:
        return f"A cotação #{c.numero} está vazia. Busque produtos antes de finalizar."
    agora = datetime.now()
    validade = agora + timedelta(days=VALIDADE_DIAS)
    linhas, total = linhas_carrinho(s)
    c.status = "finalizada"
    c.finalizada_em = c.finalizada_em or agora
    c.tocar()
    txt = (f"📄 **Cotação NexaTech #{c.numero}** · ✅ finalizada\n\n" + "\n".join(linhas) +
           f"\n\n**Total: {brl(total)}**\n\n💳 No PIX ({int(DESCONTO_PIX * 100)}% off): **{brl(total * (1 - DESCONTO_PIX))}**"
           f"\n\n🗓️ Válida até **{validade:%d/%m/%Y}** ({VALIDADE_DIAS} dias)")
    try:
        caminho = gerar_pdf_sessao(s)
        txt += f"\n\n📎 PDF gerado: `{os.path.basename(caminho)}`. Para baixar, use o botão **Baixar cotação {c.numero} (PDF)** na barra lateral."
    except Exception as e:
        txt += f"\n\nNão consegui gerar o PDF ({type(e).__name__})."
    outras = [x for x in s.cotacoes if x is not c and x.status == "aberta" and x.carrinho]
    if outras:
        txt += ("\n\n📌 Você ainda tem cotações em andamento: " +
                ", ".join(f"**#{x.numero}** ({brl(x.total())})" for x in outras) +
                ". Digite **cotações** para ver o histórico ou **abrir cotação N** para continuar.")
    else:
        txt += "\n\nPara uma nova compra, digite **nova cotação**."
    return txt + "\n\n" + humano.despedida_finalizacao(s, c)      # [NOVO] despedida


# ---------- [NOVO v4] histórico: ações sobre cotações inteiras ----------
def limpar_cotacao(s: Sessao) -> str:
    """Esvazia só a cotação ativa; as outras continuam no histórico."""
    c = s.ativa
    if c.status == "finalizada":
        return f"A cotação #{c.numero} já foi finalizada e não pode ser esvaziada. Digite **nova cotação** para começar outra."
    c.carrinho.clear()
    c.tocar()
    s.limpar_contexto()
    outras = len(s.cotacoes) > 1
    return (f"🧹 Esvaziei a **cotação #{c.numero}**." +
            (" As outras cotações continuam salvas (digite **cotações** para ver)." if outras else " O que você procura?"))


def reiniciar_tudo(s: Sessao) -> str:
    s.__init__()
    return "🧼 Apaguei todas as cotações e comecei do zero. Você está na **cotação #1**. O que você procura?"


def cot_listar(s: Sessao) -> str:
    return historico_md(s)


def cot_nova(s: Sessao) -> str:
    anterior = s.ativa
    if not anterior.carrinho and anterior.status == "aberta":
        return f"Você já está na **cotação #{anterior.numero}**, que ainda está vazia. Pode começar a adicionar produtos."
    s.limpar_contexto()
    nova = s.nova_cotacao()
    txt = f"🆕 Abri a **cotação #{nova.numero}**. "
    if anterior.status == "aberta":
        txt += (f"A cotação #{anterior.numero} ficou salva ({anterior.unidades()} un., {brl(anterior.total())}); "
                f"para voltar a ela, digite **abrir cotação {anterior.numero}**. ")
    else:
        txt += f"A cotação #{anterior.numero} ({status_txt(anterior)}) continua no histórico. "
    return txt + "O que você procura?"


def cot_abrir(s: Sessao, numero: int) -> str:
    c = s.buscar(numero)
    if not c:
        return f"Não existe a cotação #{numero}. Digite **cotações** para ver o histórico."
    if c is s.ativa:
        return f"Você já está na **cotação #{numero}**.\n\n" + ver_carrinho(s)
    anterior = s.ativa
    havia_fila = s.limpar_contexto()
    if not anterior.carrinho and anterior.status == "aberta" and anterior.numero == max(x.numero for x in s.cotacoes):
        s.cotacoes.remove(anterior)             # não deixa uma cotação vazia sobrando no histórico
    reaberta = c.status == "descartada"
    if reaberta:
        c.status = "aberta"
    s.ativa = c
    txt = f"📂 Voltei para a **cotação #{numero}**" + (" (estava descartada, então reabri)." if reaberta else ".")
    if havia_fila:
        txt += " Os itens que ainda estavam esperando escolha foram descartados."
    if c.status == "finalizada":
        txt += " Ela já foi finalizada; para fazer outra compra, digite **nova cotação**."
    return txt + "\n\n" + ver_carrinho(s)


def cot_ver(s: Sessao, numero: int) -> str:
    c = s.buscar(numero)
    return ver_carrinho(s, c) if c else f"Não existe a cotação #{numero}. Digite **cotações** para ver o histórico."


def cot_descartar(s: Sessao, numeros) -> str:
    alvo = list(dict.fromkeys(numeros)) or [s.ativa.numero]
    saida = []
    for n in alvo:
        c = s.buscar(n)
        if not c:
            saida.append(f"A cotação #{n} não existe.")
        elif c.status == "finalizada":
            saida.append(f"A cotação #{n} já foi finalizada e não pode ser descartada.")
        elif c.status == "descartada":
            saida.append(f"A cotação #{n} já estava descartada.")
        else:
            c.status = "descartada"
            c.tocar()
            saida.append(f"🗑️ Cotação #{n} descartada ({c.unidades()} un., {brl(c.total())}).")
    if s.ativa.status == "descartada":          # a cotação em uso foi descartada: vai para a mais recente em andamento
        s.limpar_contexto()
        abertas = [c for c in s.cotacoes if c.status == "aberta"]
        if abertas:
            s.ativa = max(abertas, key=lambda c: c.numero)
            saida.append(f"📂 Voltei para a **cotação #{s.ativa.numero}**.")
        else:
            nova = s.nova_cotacao()
            saida.append(f"🆕 Não havia outra cotação em andamento, então abri a **cotação #{nova.numero}**.")
    return "\n\n".join(saida)


def cot_finalizar(s: Sessao, numero: int) -> str:
    c = s.buscar(numero)
    if not c:
        return f"Não existe a cotação #{numero}. Digite **cotações** para ver o histórico."
    prefixo = ""
    if c is not s.ativa:
        cot_abrir(s, numero)
        prefixo = f"📂 Abri a cotação #{numero} para finalizar.\n\n"
    return prefixo + finalizar(s)


def executar_acoes(s: Sessao, acoes):
    """acoes = [(nome, [números])]. Usada pelos atalhos de texto e pela intenção `gerenciar_cotacoes` do LLM."""
    saida, ultima = [], None
    for nome, nums in acoes:
        if nome == "listar":
            saida.append(cot_listar(s))
        elif nome == "nova":
            saida.append(cot_nova(s))
        elif nome == "abrir":
            if not nums:
                saida.append("Qual cotação? Digite, por exemplo, **abrir cotação 1** (os números aparecem em **cotações**).")
            elif saida and s.buscar(nums[0]) is s.ativa:      # já voltou para ela numa ação anterior (ex.: após descartar)
                saida.append(ver_carrinho(s))
            else:
                saida.append(cot_abrir(s, nums[0]))
        elif nome == "ver":
            saida.append("\n\n".join(cot_ver(s, k) for k in nums) if nums else ver_carrinho(s))
        elif nome == "descartar":
            saida.append(cot_descartar(s, nums))
        elif nome == "finalizar":
            saida.append(cot_finalizar(s, nums[0]) if nums else finalizar(s))
        else:
            continue
        ultima = nome
    if not saida:
        return None
    texto = "\n\n".join(saida)
    if ultima == "descartar":
        texto += "\n\n" + historico_md(s)
    return texto


def catalogo_geral() -> str:
    linhas = ["| Categoria | Modelos | Faixa de preço | Você pode pedir como |", "|---|:-:|---|---|"]
    for cat, (ic, sing, plural, aliases) in CATEGORIAS.items():
        ps = [p for p in PRODUTOS if p["categoria"] == cat]
        linhas.append(f"| {ic} **{plural}** | {len(ps)} | {brl(min(p['preco'] for p in ps))} a {brl(max(p['preco'] for p in ps))} | {', '.join(aliases[:4])} |")
    return "📚 **Catálogo NexaTech**\n\n" + "\n".join(linhas) + "\n\nDigite o nome de uma categoria para ver todos os modelos."


BOAS_VINDAS = """Olá! Eu sou o **CotaIA**, assistente de cotações da NexaTech 👋 Que bom ter você por aqui!

Eu ajudo você a montar cotações: mostro os modelos do catálogo, controlo o carrinho e gero o PDF. Pode escrever do seu jeito (entendo gírias e erros de digitação, tipo `kero 2 mouzes`). Estes são os atalhos:

| O que você quer | Digite |
|---|---|
| 🔎 Ver modelos | `monitor` · `fone sem fio até 300` · `notebook 16gb` |
| ⚡ Adicionar direto | `1 unidade do monitor mais caro` · `2 mouses mais baratos` |
| 📦 Pedido com vários itens | `2 monitores e 3 teclados` |
| 👉 Escolher na lista | `2` · `2 x 5` (opção 2, cinco unidades) · `o mais barato` |
| ⚖️ Comparar | `comparar 1 e 3` |
| 🛒 Carrinho | `carrinho` · `remover 1` · `limpar` |
| 🗂️ Várias cotações | `nova cotação` · `cotações` · `abrir cotação 1` · `descartar cotação 2` |
| 📄 Fechar | `finalizar` (gera o PDF) · `finalizar cotação 1` |
| ❓ Dúvidas | `qual a garantia?` · `como funciona o pagamento?` |
| 📚 Outros | `catálogo` · `todos` · `aprendizado` · `ajuda` |

Você começa na **cotação #1**. Se quiser, me diga seu nome; e me conte: o que você precisa cotar hoje?"""

AJUDA = BOAS_VINDAS      # "ajuda", "menu" e "oi" mostram a mesma apresentação

# ===== célula [20] =====
PROMPT_DUVIDA = """Você é o assistente da NexaTech Informática (empresa fictícia).
Responda à pergunta do cliente usando APENAS o CONTEXTO abaixo.
- Se o contexto não tiver a resposta, diga que não tem essa informação e que encaminhará a um atendente.
- Nunca invente preços, prazos, garantias, especificações ou condições.
- Seja objetivo, em português do Brasil."""


def responder_duvida(pergunta: str, debug: bool = False) -> str:
    q = modelo_emb.encode([pergunta], normalize_embeddings=True).astype("float32")
    scores, ids = IDX_CONHECIMENTO.search(q, 4)
    achados = [(DOCS_CONHECIMENTO[i], float(sc)) for sc, i in zip(scores[0], ids[0]) if i != -1]
    relevantes = [(d, sc) for d, sc in achados if sc >= LIMIAR_DUVIDA]
    if debug:
        print("   RAG:", [(d["fonte"], round(sc, 2)) for d, sc in achados])
    if not relevantes:
        return "Não encontrei essa informação na base da NexaTech. Vou encaminhar sua dúvida para um atendente validar."
    contexto = "\n".join(f"[{d['fonte']}] {d['texto']}" for d, _ in relevantes)
    resposta = chamar_llm(PROMPT_DUVIDA, f"CONTEXTO:\n{contexto}\n\nPERGUNTA: {pergunta}")
    fontes = ", ".join(sorted({d["fonte"] for d, _ in relevantes}))
    return f"{resposta}\n\n_Fontes: {fontes}_"

# ===== célula [22] =====
ORDINAIS = {"primeir": 1, "segund": 2, "terceir": 3, "quart": 4, "quint": 5, "sext": 6}


def _comando(n: str):
    if n in {"carrinho", "meu carrinho", "ver carrinho", "meu pedido", "resumo", "ver cotacao", "minha cotacao"}:
        return "ver_carrinho"
    if n in {"limpar", "limpar carrinho", "esvaziar", "esvaziar carrinho", "limpar cotacao", "esvaziar cotacao"}:
        return "limpar"                   # [v4] esvazia só a cotação atual; o histórico fica
    if n in {"limpar tudo", "recomecar", "reiniciar", "apagar historico", "limpar historico", "zerar tudo", "comecar do zero"}:
        return "reiniciar"
    if re.fullmatch(r"(finalizar|fechar|concluir)( cotacao| pedido)?|gerar (cotacao|pdf|proposta)", n):
        return "finalizar"
    if n in {"catalogo", "ver catalogo", "catalogo completo", "produtos", "o que voces vendem", "o que vendem", "categorias"}:
        return "catalogo_geral"
    if n in {"ajuda", "menu", "help", "comandos", "oi", "ola", "bom dia", "boa tarde", "boa noite", "e ai"}:
        return "ajuda"
    if n in {"todos", "ver todos", "mostrar todos", "todos os modelos", "mostrar todos os modelos"}:
        return "todos"
    if n in {"aprendizado", "o que voce aprendeu", "o que aprendeu", "memoria do assistente"}:
        return "memoria"
    if n in {"esquecer aprendizado", "apagar aprendizado"}:
        return "esquecer"
    return None


def _escolha_deterministica(n: str, s: Sessao):
    if not s.opcoes:
        return None
    m = re.fullmatch(r"(?:quero\s+)?(?:a\s+|o\s+)?(?:opcao\s+|numero\s+|no\s*|n\s*)?(\d{1,2})", n)
    if m:
        return [{"opcao": int(m.group(1))}]
    m = re.fullmatch(r"(?:opcao\s+)?(\d{1,2})\s*(?:x|\*)\s*(\d{1,3})", n)
    if m:
        return [{"opcao": int(m.group(1)), "quantidade": int(m.group(2))}]
    m = re.fullmatch(r"(inf\d{3})(?:\s*(?:x|\*)\s*(\d{1,3}))?", n)
    if m:
        return [{"codigo": m.group(1), "quantidade": int(m.group(2)) if m.group(2) else None}]
    m = re.fullmatch(r"(?:quero\s+)?(?:o\s+|a\s+)?(primeir|segund|terceir|quart|quint|sext)[oa]", n)
    if m:
        return [{"opcao": ORDINAIS[m.group(1)]}]

    # [ALTERADO] "o mais barato", "me dá o mais caro", "3 do mais baratinho"
    ordem, resto = detectar_ordem(n)
    if ordem:
        sobra = [t for t in tokens(resto) if t not in STOP and not t.isdigit()]
        if not sobra:
            disp = [POR_CODIGO[c] for c in s.opcoes if POR_CODIGO[c]["estoque"] > 0] or [POR_CODIGO[c] for c in s.opcoes]
            alvo = min(disp, key=lambda p: p["preco"]) if ordem == "barato" else max(disp, key=lambda p: p["preco"])
            nums = [int(t) for t in tokens(resto) if t.isdigit() and int(t) <= 99]
            return [{"codigo": alvo["codigo"], "quantidade": nums[0] if nums else None}]
    return None


# ---------- [NOVO v4] atalhos do histórico de cotações ----------
REF_COT = r"\b(?:cotacao|cotacoes|proposta|propostas|orcamento|orcamentos)\b"
RE_ORDINAL = r"\b(?:primeir|segund|terceir|quart|quint|sext)[oa]s?\b"
V_ABRIR = r"\b(?:abr\w*|volt\w*|retom\w*|continu\w*|troc\w*|mud\w*|vamos|(?:ir|va|vai|vou)\s+(?:para|pra|na|a))\b"
V_DESC_FORTE = r"\b(?:desist\w*|descart\w*|abandon\w*)\b"
V_DESC_FRACO = r"\b(?:cancel\w*|exclu\w*|apag\w*|remov\w*|delet\w*|tir\w*)\b"     # só vale junto da palavra "cotação"
V_VER = r"\b(?:ver|veja|mostr\w*|exib\w*|detalh\w*)\b"


def _numeros_cotacao(trecho: str, s: Sessao):
    """Números de cotação citados no trecho: 'cotação 2', 'a 3 e a 2', 'terceira e segunda', 'última'."""
    nums = []
    for m in re.finditer(r"\b(\d{1,2})\b|\b(primeir|segund|terceir|quart|quint|sext)[oa]s?\b|\bultim[oa]\b", trecho):
        if m.group(1):
            nums.append(int(m.group(1)))
        elif m.group(2):
            nums.append(ORDINAIS[m.group(2)])
        else:
            nums.append(max(c.numero for c in s.cotacoes))
    return nums


def _cmd_cotacoes(n: str, s: Sessao):
    """Reconhece os atalhos de cotação (texto já normalizado). Retorna a resposta ou None se não for sobre isso."""
    tem_cot = bool(re.search(REF_COT, n))

    # "cotações", "histórico", "minhas cotações"
    if re.fullmatch(r"(?:(?:ver|mostrar|mostra|listar|exibir)\s+)?(?:(?:todas as|todas|minhas|meu|meus|as)\s+)?"
                    r"(?:cotacoes|historico|propostas|orcamentos)(?:\s+(?:anteriores|salvas|abertas))?"
                    r"|historico de (?:cotacoes|propostas)", n):
        return executar_acoes(s, [("listar", [])])

    # "nova cotação", "outra cotação", "quero uma nova cotação"
    if re.fullmatch(r"(?:(?:iniciar|comecar|criar|abrir|fazer|quero|queria)\s+)?(?:uma\s+)?(?:nova|outra|novo)\s+"
                    r"(?:cotacao|proposta|pedido|orcamento)(?:\s+(?:agora|por favor))?", n):
        return executar_acoes(s, [("nova", [])])

    # "finalizar cotação 1", "fechar a primeira"
    m = re.match(r"(?:finalizar|fechar|concluir|encerrar)\b(.*)", n)
    if m:
        nums = _numeros_cotacao(m.group(1), s)
        if nums and (tem_cot or re.search(RE_ORDINAL, m.group(1))):
            return executar_acoes(s, [("finalizar", nums[:1])])
        return None

    # descartar e/ou voltar: "desisti da terceira e da segunda, volta pra primeira"
    forte = re.search(V_DESC_FORTE, n)
    fraco = re.search(V_DESC_FRACO, n) if tem_cot else None
    m_de = forte or fraco
    m_ab = re.search(V_ABRIR, n)
    marcas = sorted((m.start(), nome) for nome, m in (("descartar", m_de), ("abrir", m_ab)) if m)
    acoes = []
    for k, (ini, nome) in enumerate(marcas):
        fim = marcas[k + 1][0] if k + 1 < len(marcas) else len(n)
        trecho = n[ini:fim]
        nums = _numeros_cotacao(trecho, s)
        if nome == "descartar":
            sozinho = re.fullmatch(r"(?:desist\w*|descart\w*|abandon\w*)(?:\s+(?:dessa|desta|disso|essa|esta|da|de|do))?"
                                   r"(?:\s+(?:cotacao|proposta|pedido|orcamento))?", trecho.strip())
            if tem_cot or sozinho or re.search(RE_ORDINAL, trecho):
                acoes.append(("descartar", nums))
        elif nums and (tem_cot or re.match(r"(?:volt|retom)", trecho)):
            acoes.append(("abrir", nums[:1]))
    if acoes:
        return executar_acoes(s, acoes)

    # "ver cotação 2" (só olhar, sem trocar de cotação)
    if tem_cot and re.search(V_VER, n):
        nums = _numeros_cotacao(n, s)
        if nums:
            return executar_acoes(s, [("ver", nums)])
    return None


def _atender(msg: str, s: Sessao, debug: bool):
    texto_original = msg              # [NOVO] o LLM e o RAG recebem o texto original (com acentos)
    msg = limpar_msg(msg)             # [NOVO] gírias e erros simples corrigidos
    n = normalizar(msg)
    if not n:
        return AJUDA, "ajuda", "regra"

    social = humano.responder_social(n, texto_original, s)      # [NOVO] oi, obrigado, tchau, nome...
    if social:
        return social, "social", "regra"

    cmd = _comando(n)
    if cmd == "ver_carrinho":
        return ver_carrinho(s), cmd, "regra"
    if cmd == "limpar":
        return limpar_cotacao(s), cmd, "regra"
    if cmd == "reiniciar":
        return reiniciar_tudo(s), cmd, "regra"
    if cmd == "finalizar":
        return finalizar(s), cmd, "regra"
    if cmd == "catalogo_geral":
        return catalogo_geral(), cmd, "regra"
    if cmd == "ajuda":
        return AJUDA, cmd, "regra"
    if cmd == "todos":
        if not s.completos:
            return "Não há uma lista de categoria aberta. Busque um produto primeiro (ex.: `monitor`).", cmd, "regra"
        cat = POR_CODIGO[s.completos[0]]["categoria"]
        s.opcoes = list(s.completos)
        return f"{CATEGORIAS[cat][0]} **Todos os modelos de {CATEGORIAS[cat][1]}**\n\n" + tabela_md([POR_CODIGO[c] for c in s.opcoes]) + "\n\n👉 Digite o número da opção.", cmd, "regra"
    if cmd == "memoria":
        if not ALIAS_APRENDIDOS:
            return "🧠 Ainda não aprendi nada novo. Quando você escolher um produto depois de um termo que eu não conhecia, eu memorizo.", cmd, "regra"
        return "🧠 **O que aprendi com você:**\n" + "\n".join(f"- “{k}” → {v}" for k, v in ALIAS_APRENDIDOS.items()), cmd, "regra"
    if cmd == "esquecer":
        ALIAS_APRENDIDOS.clear(); salvar_memoria()
        return "🧽 Memória de aprendizado apagada.", cmd, "regra"

    resp = _cmd_cotacoes(n, s)               # [NOVO v4] nova / cotações / abrir / descartar / finalizar N
    if resp is not None:
        return resp, "cotacoes", "regra"

    m = re.fullmatch(r"(?:remov\w*|tir\w*|exclu\w*)\s+(?:o\s+|a\s+|item\s+)?(inf\d{3}|\d{1,2})", n)
    if m:
        return remover(s, m.group(1)), "remover", "regra"

    if "compar" in n or re.search(r"\bvs\b", n):
        refs = [{"codigo": r.upper()} if r.startswith("inf") else {"opcao": int(r)} for r in re.findall(r"inf\d{3}|\b\d{1,2}\b", n)]
        if len(refs) >= 2:
            return comparar(s, refs), "comparar", "regra"

    refs = _escolha_deterministica(n, s)
    if refs:
        return escolher(s, refs), "escolher", "regra"

    itens = heuristica_pedido(msg)
    if itens:
        if debug:
            print("   itens (heurística):", [(i["termo"], i["quantidade"], i["categoria"], i["metodo"], i["ordem"]) for i in itens])
        return iniciar_busca(s, itens), "buscar", "heuristica"

    try:
        dados = interpretar_llm(texto_original, s)
    except Exception as e:
        dados = None
        if debug:
            print("   LLM indisponível:", type(e).__name__)
    if dados is None:
        item = resolver_item({"termo": msg, "quantidade": None, "atributos": []})
        return "_(Modo sem LLM: interpretei só por similaridade.)_\n\n" + iniciar_busca(s, [item]), "buscar", "semantico"

    intencao = dados["intencao"]
    if debug:
        print("   LLM:", intencao, dados["itens"], dados["referencias"])
    if intencao == "buscar" and dados["itens"]:
        itens = [{"termo": i.get("termo"), "quantidade": _int_ou_none(i.get("quantidade")), "preco_max": i.get("preco_max"),
                  "preco_min": i.get("preco_min"), "marca": i.get("marca"), "atributos": i.get("atributos") or [],
                  "ordem": i.get("ordem") if i.get("ordem") in ("barato", "caro") else None}      # [NOVO]
                 for i in dados["itens"]]
        return iniciar_busca(s, itens), intencao, "llm"
    if intencao == "escolher":
        return escolher(s, dados["referencias"]), intencao, "llm"
    if intencao == "comparar":
        return comparar(s, dados["referencias"]), intencao, "llm"
    if intencao == "remover" and dados["referencias"]:
        r = dados["referencias"][0]
        return remover(s, str(r.get("codigo") or r.get("opcao") or "")), intencao, "llm"
    if intencao == "ver_carrinho":
        return ver_carrinho(s), intencao, "llm"
    if intencao == "finalizar":
        return finalizar(s), intencao, "llm"
    if intencao == "catalogo_geral":
        return catalogo_geral(), intencao, "llm"
    if intencao == "saudacao":
        return humano.responder_social("oi", "oi", s), intencao, "llm"
    if intencao == "gerenciar_cotacoes":
        acoes = []
        for a in dados.get("acoes") or []:
            if isinstance(a, dict):
                brutos = a.get("numeros") if isinstance(a.get("numeros"), list) else []
                acoes.append((str(a.get("acao") or ""), [int(x) for x in brutos if str(x).isdigit()]))
        return (executar_acoes(s, acoes) or cot_listar(s)), intencao, "llm"
    if intencao == "limpar":
        return limpar_cotacao(s), intencao, "llm"
    if intencao == "fora_escopo":
        return "Essa eu não sei te responder 😅 Meu forte é informática: posso mostrar modelos, montar cotações e tirar dúvidas da NexaTech. Digite **ajuda** se quiser ver exemplos.", intencao, "llm"
    return responder_duvida(texto_original, debug), "duvida", "rag"


def atender(mensagem: str, sid: str = "default", debug: bool = False) -> str:
    t0 = time.perf_counter()
    s = get_sessao(sid)
    try:
        resposta, intencao, metodo = _atender(str(mensagem), s, debug)
    except Exception as e:
        resposta, intencao, metodo = f"⚠️ Tive um problema ao processar ({type(e).__name__}). Tente reformular ou digite **ajuda**.", "erro", "-"
        if debug:
            raise
    if intencao == "buscar" and not resposta.startswith(("Vamos item", "❌", "Não", "⚠️")):
        resposta = humano.abertura_busca() + "\n\n" + resposta        # [NOVO]
    LOG.append({"mensagem": mensagem, "intencao": intencao, "metodo": metodo,
                "latencia_ms": round((time.perf_counter() - t0) * 1000)})
    return resposta