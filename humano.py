"""Camada de conversa humana do CotaIA.

Sem LLM e sem dependências pesadas: tudo aqui é regra simples, então responde na hora
e pode ser testado sem internet. Fica na mesma pasta do cotaia_backend.py.

Funções usadas pelo backend:
    responder_social(n, original, s)  -> str | None   (saudação, obrigado, tchau, nome...)
    despedida_finalizacao(s, c)       -> str          (texto de despedida ao finalizar)
    abertura_busca()                  -> str          (frase curta antes da tabela de opções)
"""
import random
import re
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    _FUSO = ZoneInfo("America/Sao_Paulo")
except Exception:          # sem tzdata (ex.: Windows sem o pacote): usa a hora da máquina
    _FUSO = None


def _escolha(opcoes):
    return random.choice(opcoes)


def _voto() -> str:
    """'Tenha um ótimo dia!' conforme a hora."""
    return {"bom dia": "Tenha um ótimo dia! ☀️", "boa tarde": "Tenha uma ótima tarde! 🌤️",
            "boa noite": "Tenha uma ótima noite! 🌙"}[_periodo()]


def _periodo() -> str:
    h = (datetime.now(_FUSO) if _FUSO else datetime.now()).hour
    if h < 5:
        return "boa noite"
    if h < 12:
        return "bom dia"
    if h < 18:
        return "boa tarde"
    return "boa noite"


def _nome(s) -> str:
    return getattr(s, "nome", None) or ""


def _com_nome(s, antes: str = ", ") -> str:
    n = _nome(s)
    return f"{antes}{n}" if n else ""


def _brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------
# Vocabulários (a mensagem já chega sem acento e em minúsculas)
# --------------------------------------------------------------------------
_SAUDACAO = {"oi", "oii", "oiii", "ola", "olaa", "opa", "eae", "e", "ai", "fala", "salve", "hey", "hello", "hi",
             "bom", "dia", "boa", "tarde", "noite", "tudo", "bem", "bom", "td", "como", "vai", "voce", "esta",
             "beleza", "pessoal", "galera", "time", "ola"}
_BEM_ESTAR = {"tudo bem", "td bem", "tudo bom", "como vai", "como voce esta", "como vai voce", "tudo certo"}

_GRATIDAO_NUCLEO = {"obrigado", "obrigada", "obg", "brigado", "brigada", "valeu", "agradeco", "agradecido", "agradecida", "vlw"}
_GRATIDAO = _GRATIDAO_NUCLEO | {"muito", "muitissimo", "demais", "pela", "pelo", "ajuda", "atencao", "atendimento",
                                "show", "top", "otimo", "perfeito", "legal", "massa", "excelente", "tambem", "voce",
                                "a", "o", "de", "tudo", "ok", "beleza", "e", "por", "paciencia", "tempo"}

_DESPEDIDA_FRASES = (r"tchau|xau|flw|falou|adeus|bye|fui|ate (?:logo|mais|breve|amanha|depois|a proxima|ja|a volta)"
                     r"|tenha (?:um|uma) (?:otimo|otima|bom|boa) \w+|bom fim de semana|boa semana")
_DESPEDIDA_EXTRA = {"tchau", "xau", "flw", "falou", "adeus", "bye", "fui", "ate", "logo", "mais", "breve", "amanha",
                    "depois", "a", "proxima", "ja", "volta", "tenha", "um", "uma", "otimo", "otima", "bom", "boa",
                    "dia", "tarde", "noite", "semana", "fim", "de", "valeu", "obrigado", "obrigada", "e", "voce",
                    "tambem", "para", "pra", "voces", "tudo"}

_IDENTIDADE = (r"quem (?:e|eh) voce|quem e voce ai|qual (?:e )?(?:o )?seu nome|como voce se chama|voce se chama como"
               r"|voce e (?:um )?(?:robo|bot|humano|pessoa|gente|ia|maquina|atendente)(?: de verdade)?"
               r"|(?:e|eh) (?:um )?(?:robo|bot|humano|pessoa)\??|o que voce faz|o que voce e|voce e real")

_SO_ISSO = (r"(?:e |eh )?so isso|(?:era|e) so isso mesmo|por enquanto (?:e |eh )?so|so isso mesmo|nao,? (?:so isso|obrigado|obrigada)"
            r"|nada mais|mais nada|(?:e|eh) tudo|(?:e|eh) so|ja (?:esta|ta) bom|ta bom assim|pode ser so isso")

_NOME_RE = re.compile(
    r"(?:meu nome (?:é|e|eh)|me chamo|pode me chamar de|podem me chamar de|aqui (?:é|e) (?:o|a)|meu apelido (?:é|e))\s+"
    r"([A-Za-zÀ-ÿ]{2,20})(?:\s+([A-Za-zÀ-ÿ]{2,20}))?", re.IGNORECASE)
_NAO_NOME = {"cliente", "novo", "nova", "aqui", "um", "uma", "o", "a", "de", "da", "do", "para", "pra", "que", "e",
             "interessado", "interessada", "dono", "dona", "gerente", "empresa", "loja", "da", "na", "no"}


def extrair_nome(original: str):
    """'meu nome é maria clara' -> 'Maria' (só o primeiro nome, que é o que soa natural na conversa)."""
    m = _NOME_RE.search(original or "")
    if not m:
        return None
    nome = m.group(1)
    if nome.lower() in _NAO_NOME:
        return None
    return nome.capitalize()


# --------------------------------------------------------------------------
# Respostas
# --------------------------------------------------------------------------
def _estado(s):
    """(cotação ativa, tem itens abertos?, finalizada?)"""
    c = getattr(s, "ativa", None)
    tem = bool(c and c.carrinho)
    return c, tem, bool(c and c.status == "finalizada")


def _saudacao(s, n: str = "") -> str:
    c, tem, final = _estado(s)
    dito = next((f for f in ("bom dia", "boa tarde", "boa noite") if f in n), None)
    per = (dito or _periodo()).capitalize()
    nome = _com_nome(s)
    if tem and not final:
        return _escolha([
            f"{per}{nome}! Que bom te ver de novo por aqui 😊 Sua cotação **#{c.numero}** continua aberta com "
            f"{c.unidades()} {'unidade' if c.unidades() == 1 else 'unidades'}. Quer seguir com ela ou adicionar mais alguma coisa?",
            f"Oi{nome}! 👋 Sua cotação **#{c.numero}** está do jeitinho que você deixou. Vamos continuar de onde paramos?",
        ])
    if not _nome(s):
        return _escolha([
            f"{per}! 😊 Eu sou o CotaIA, da NexaTech. Pode me chamar quando quiser montar uma cotação. "
            "Se quiser, me diz seu nome pra eu te atender melhor. E aí, o que você precisa hoje?",
            f"Oi, {per.lower()}! 👋 Tudo bem por aqui, e com você? Me conta o que você está procurando que eu separo as melhores opções. "
            "(Se quiser, me diz seu nome também!)",
        ])
    return _escolha([
        f"{per}, {_nome(s)}! 😊 Tudo bem? Me conta o que você precisa cotar hoje.",
        f"Oi, {_nome(s)}! 👋 Que bom falar com você. O que vamos cotar agora?",
    ])


def _bem_estar(s) -> str:
    return _escolha([
        f"Tudo ótimo por aqui, obrigado por perguntar{_com_nome(s)}! 😄 E você? Me conta o que está precisando cotar.",
        f"Tudo bem sim{_com_nome(s)}! Estou pronto pra te ajudar. O que você procura hoje?",
    ])


def _agradecimento(s) -> str:
    c, tem, final = _estado(s)
    if final:
        return despedida_curta(s)
    if tem:
        return _escolha([
            f"Por nada{_com_nome(s)}! 😊 Sua cotação **#{c.numero}** segue aberta. Quer incluir mais algum produto ou posso **finalizar** e gerar o PDF?",
            f"Imagina{_com_nome(s)}, é um prazer! Se estiver tudo certo com a cotação **#{c.numero}**, é só dizer **finalizar**. Se faltar algo, me fala.",
        ])
    return _escolha([
        f"Por nada{_com_nome(s)}! 😊 Se precisar de mais alguma coisa, estou por aqui.",
        f"Disponha{_com_nome(s)}! Qualquer dúvida sobre produtos ou cotações, é só chamar.",
    ])


def despedida_curta(s) -> str:
    return _escolha([
        f"Por nada{_com_nome(s)}! Foi um prazer te atender 💙 Qualquer coisa, é só voltar.",
        f"Eu que agradeço{_com_nome(s)}! Conta com a NexaTech sempre que precisar. 💙",
    ])


def _tchau(s) -> str:
    c, tem, final = _estado(s)
    if tem and not final:
        return (f"Já vai{_com_nome(s)}? 😊 Antes: sua cotação **#{c.numero}** ({_brl(c.total())}) ainda está em andamento. "
                "Se quiser, digite **finalizar** que eu gero o PDF agora. Ela também fica salva aqui na barra lateral enquanto esta conversa estiver aberta.")
    return _escolha([
        f"Até logo{_com_nome(s)}! 👋 Foi um prazer te atender. Volte sempre que precisar de uma cotação.",
        f"Tchau{_com_nome(s)}! 💙 Qualquer coisa é só chamar. {_voto()}",
    ])


def _identidade(s) -> str:
    return ("Eu sou o **CotaIA**, o assistente virtual da NexaTech 🤖. Sou uma inteligência artificial, não uma pessoa, "
            "mas gosto de conversar como gente. Mostro os produtos, monto a cotação com você e gero o PDF da proposta. "
            "Dúvidas que eu não souber responder, encaminho para um atendente. Por onde começamos?")


def _so_isso(s) -> str:
    c, tem, final = _estado(s)
    if tem and not final:
        return (f"Combinado{_com_nome(s)}! 😊 Sua cotação **#{c.numero}** está com {_brl(c.total())}. "
                "Quer que eu **finalize** e gere o PDF agora?")
    return f"Tudo bem{_com_nome(s)}! Se precisar de algo, é só falar. 😊"


def _apresentar_nome(s, nome: str) -> str:
    c, tem, final = _estado(s)
    base = _escolha([f"Prazer, {nome}! 😊", f"Muito prazer, {nome}! 🤝", f"Legal te conhecer, {nome}! 😄"])
    if tem and not final:
        return base + f" Vamos continuar com a cotação **#{c.numero}**?"
    return base + " O que você está procurando hoje?"


def responder_social(n: str, original: str, s):
    """Devolve a resposta humana se a mensagem for só conversa; senão None (o fluxo normal segue)."""
    n = (n or "").strip()
    if not n:
        return None

    # nome ("meu nome é Ana") -> guarda na sessão e usa nas próximas respostas
    nome = extrair_nome(original)
    if nome:
        s.nome = nome
        return _apresentar_nome(s, nome)

    palavras = n.split()
    if len(palavras) > 9:
        return None

    if re.fullmatch(_IDENTIDADE, n):
        return _identidade(s)
    if re.fullmatch(_SO_ISSO, n):
        return _so_isso(s)

    # despedida
    if re.search(rf"\b(?:{_DESPEDIDA_FRASES})\b", n) and all(p in _DESPEDIDA_EXTRA for p in palavras):
        return _tchau(s)

    # agradecimento (precisa ter uma palavra de agradecer; o resto tem que ser só enfeite)
    if any(p in _GRATIDAO_NUCLEO for p in palavras) and all(p in _GRATIDAO for p in palavras):
        return _agradecimento(s)

    # "tudo bem?" sozinho
    if n in _BEM_ESTAR:
        return _bem_estar(s)

    # saudação ("oi", "bom dia", "oi tudo bem") ou só "tudo bem com você?"
    if all(p in _SAUDACAO or p == "com" for p in palavras):
        if re.match(r"(oi+|ola+|opa|eae|e ai|bom dia|boa tarde|boa noite|fala|salve|hey|hello|hi)\b", n):
            return _saudacao(s, n)
        if any(f in n for f in _BEM_ESTAR):
            return _bem_estar(s)
    return None


def despedida_finalizacao(s, c) -> str:
    """Bloco de despedida que vai no fim da mensagem de cotação finalizada."""
    nome = _nome(s)
    agradece = _escolha([
        f"Muito obrigado pela confiança{_com_nome(s)}! 💙",
        f"Foi um prazer montar essa cotação com você{_com_nome(s)}! 💙",
        f"Obrigado por escolher a NexaTech{_com_nome(s)}! 💙",
    ])
    dica = _escolha([
        "Se bater alguma dúvida sobre a proposta, é só me chamar por aqui.",
        "Se quiser ajustar algo ou cotar mais produtos, estou por aqui.",
        "Qualquer dúvida sobre prazos ou pagamento, pergunte quando quiser.",
    ])
    fecho = _escolha(["Até a próxima! 👋", _voto(), "Volte sempre! 😊"])
    return f"---\n\n{agradece}\n\n{dica} {fecho}"


_ABERTURAS = [
    "Claro! Dá uma olhada no que temos:",
    "Pode deixar! Separei estas opções pra você:",
    "Boa! Olha o que encontrei no catálogo:",
    "Vamos lá! Estas são as opções:",
]


def abertura_busca() -> str:
    return _escolha(_ABERTURAS)
