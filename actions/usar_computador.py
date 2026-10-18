# ============================================================
# SOFTIA - USAR O COMPUTADOR (computer use)
# ============================================================
#
# Portado do JARVIS-CyberBot (actions/usar_computador.py) em
# 19/09/2026, a pedido do Klecio: o SOFTIA olha a tela, decide
# uma ação, executa e confere o resultado, em loop, até terminar
# a tarefa ou desistir — sem VPS e sem Codex.
#
# O QUE MUDOU EM RELAÇÃO AO JARVIS ORIGINAL:
#
# - QUEM DECIDE: no JARVIS, a foto ia para a VPS, que mostrava tudo
#   ao Codex CLI. Aqui é a própria API do Gemini (mesma chave do
#   resto do SOFTIA) que olha a foto a cada volta e decide.
# - MIRA DO CLIQUE: o JARVIS numerava os elementos clicáveis via UI
#   Automation (pywin32), que o SOFTIA não tem como dependência. Aqui
#   o Gemini aponta a coordenada (x,y normalizado de 0 a 1000) direto
#   em cima da foto, do mesmo jeito que o vision/click_locator.py já
#   faz para um clique avulso — só que agora em loop, com histórico.
# - PERIGO: o JARVIS perguntava por voz antes de ações perigosas
#   (pagar, apagar, enviar...) e guardava a autorização por família
#   de risco durante a tarefa. Aqui, mais simples: qualquer tarefa ou
#   ação que bata na lista de termos perigosos é BLOQUEADA na hora,
#   sem perguntar — o usuário pode pedir de novo, confirmando, na
#   próxima fala.
# - SEM COFRE DE CREDENCIAL: o SOFTIA não tem o `acessos.py` do
#   JARVIS. Se o Gemini pedir uma senha guardada, a tarefa recusa e
#   explica, em vez de inventar ou digitar às cegas.
# - SEM NARRAÇÃO CONTÍNUA: fica para quando o `narrador_pc` for
#   avaliado (ainda pendente no PENDENCIAS.txt).
#
# O QUE FICOU IGUAL (mesma ideia, mesmo motivo):
# - ESC mata o loop na hora, em qualquer janela (GetAsyncKeyState,
#   ctypes puro — não depende de gancho de teclado).
# - Teto de passos e de tempo, para não gastar rodada à toa.
# - Anti-teimosia: se a tela não muda depois de várias voltas,
#   desiste em vez de repetir o mesmo movimento para sempre.
# - Área de transferência: o texto digitado é colado (ctrl+v) e o
#   que estava lá antes volta ao fim, para não atrapalhar o usuário.
# ============================================================

import hashlib
import io
import json
import os
import re
import threading
import time
import unicodedata

import mss
import pyautogui
import pyperclip
from PIL import Image
from google import genai
from google.genai import types

from core.config import GEMINI_API_KEY


# Mesma variável de ambiente que o vision/click_locator.py já usa
# para o modelo de visão — trocar um troca o outro.
MODELO_VISAO = os.getenv("GEMINI_VISION_MODEL", "gemini-3.1-flash-lite")

MAX_PASSOS = 40
TEMPO_MAXIMO_S = 600
MAX_ACOES_POR_PASSO = 3
# Voltas seguidas sem a tela mudar antes de desistir. Tela parada
# também acontece de boa-fé (página carregando, campo já preenchido).
SEM_MUDANCA_LIMITE = 6


def _sem_acento(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


# Termos que nunca rodam sozinhos, por mais que o Gemini insista.
# Bloqueia a tarefa inteira (na entrada) e cada ação individual
# (durante o loop) — sem pedir confirmação, só recusa.
_PERIGOSO = re.compile(
    r"\b(pagar|pague|paga|pagamento|comprar|compre|compra|"
    r"finalizar (a )?compra|checkout|"
    r"excluir|exclui|exclua|apagar|apaga|apague|deletar|delete|deleta|"
    r"remover|remove|remova|formatar|formate|"
    r"enviar|envie|envia|transferir|transfira|"
    r"desinstalar|desinstale|instalar|instale|"
    r"confirmar (o )?pedido|assinar|assine|contratar|"
    r"cancelar (a )?conta|redefinir|resetar|resete|"
    r"shutdown|desligar|desligue|reiniciar|reinicie|"
    r"executar como administrador|permissao de administrador)\b",
    re.I,
)


def _tarefa_bloqueada(texto):
    """Devolve o motivo do bloqueio, ou "" se a tarefa pode rodar."""
    achado = _PERIGOSO.search(_sem_acento(texto))
    return f"isso envolve {achado.group(1)}, que é uma ação sem volta fácil" if achado else ""


def _tecla_sem_volta(teclas):
    """shift+delete apaga sem passar pela lixeira — não tem volta."""
    t = _sem_acento(teclas)
    return "shift" in t and ("del" in t or "excluir" in t)


def _acao_perigosa(acao):
    if _tecla_sem_volta(str(acao.get("teclas") or "")):
        return "isso apaga sem passar pela lixeira"
    texto = f"{acao.get('alvo') or ''} {acao.get('texto') or ''} {acao.get('teclas') or ''}"
    achado = _PERIGOSO.search(_sem_acento(texto))
    return f"isso envolve {achado.group(1)}" if achado else ""


# ── ESC mata o loop, em qualquer janela (mesma ideia do JARVIS) ────────────

class _FreioEsc:
    """ESC apertado em QUALQUER lugar interrompe o computer use na hora.

    Uma thread pergunta ao Windows, 20x por segundo, se a tecla ESC está
    pressionada AGORA (GetAsyncKeyState enxerga a tecla em qualquer janela).
    O próprio loop às vezes aperta Esc (fechar menu) — por isso ele avisa
    `ignorar_por()` antes, senão pararia sozinho.
    """

    _VK_ESCAPE = 0x1B

    def __init__(self):
        self._apertado = False
        self._fim = threading.Event()
        self._ignorar_ate = 0.0
        self._thread = None

    def ligar(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._laco, daemon=True, name="freio-esc-usar-pc")
        self._thread.start()

    def parar(self):
        self._fim.set()
        self._thread = None

    def ignorar_por(self, segundos=0.8):
        self._ignorar_ate = time.monotonic() + float(segundos)

    @property
    def apertado(self):
        return self._apertado

    def _laco(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.GetAsyncKeyState.restype = ctypes.c_short
            user32.GetAsyncKeyState(self._VK_ESCAPE)  # descarta o que já estava acumulado
        except Exception:
            return
        while not self._fim.is_set():
            try:
                if time.monotonic() >= self._ignorar_ate:
                    if user32.GetAsyncKeyState(self._VK_ESCAPE) & 0x8000:
                        self._apertado = True
                        return
            except Exception:
                return
            time.sleep(0.05)


def _janela_e_do_softia():
    """A janela em primeiro plano é a do próprio SOFTIA?

    Digitar às cegas ali dentro seria inútil e, com credencial, perigoso —
    mesma checagem que o digitacao_actions.py já faz, em ctypes puro.
    """
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()
    except Exception:
        return False


# ── Ver a tela ──────────────────────────────────────────────────────────

def _capturar_tela():
    """Foto de toda a área virtual (todos os monitores), em JPEG.

    Devolve também um hash pequeno da imagem (para notar se a tela mudou
    entre uma volta e outra) e o suficiente para converter a coordenada
    normalizada (0-1000) que o Gemini devolve em pixel real da tela.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        captura = sct.grab(monitor)
        imagem = Image.frombytes("RGB", captura.size, captura.rgb)

        buffer = io.BytesIO()
        imagem.save(buffer, format="JPEG", quality=80)

        pequena = imagem.convert("L").resize((48, 27))

        return {
            "bytes": buffer.getvalue(),
            "largura": captura.width,
            "altura": captura.height,
            "esquerda": monitor["left"],
            "topo": monitor["top"],
            "hash": hashlib.md5(pequena.tobytes()).hexdigest(),
        }


def _pixel_absoluto(captura, x_norm, y_norm):
    x_norm = max(0, min(1000, int(x_norm)))
    y_norm = max(0, min(1000, int(y_norm)))
    x = captura["esquerda"] + round((x_norm / 1000) * (captura["largura"] - 1))
    y = captura["topo"] + round((y_norm / 1000) * (captura["altura"] - 1))
    return x, y


def _extrair_json(texto):
    texto = str(texto or "").strip()
    if texto.startswith("```"):
        linhas = [l for l in texto.splitlines() if not l.strip().startswith("```")]
        texto = "\n".join(linhas).strip()
    return json.loads(texto)


# ── Fazer o movimento na tela ───────────────────────────────────────────

# Nomes em português dos atalhos mais comuns -> nome que o pyautogui conhece.
_TECLAS = {
    "controle": "ctrl", "control": "ctrl", "alternar": "alt", "opcao": "alt",
    "cmd": "win", "windows": "win", "super": "win", "janela": "win",
    "maiuscula": "shift", "maiusculo": "shift",
    "esc": "esc", "escape": "esc", "sair": "esc",
    "voltar": "backspace", "apagar": "backspace", "retrocesso": "backspace",
    "espaco": "space", "tabulacao": "tab",
    "entra": "enter", "return": "enter", "confirma": "enter",
    "del": "delete", "deletar": "delete", "excluir": "delete",
    "inicio": "home", "fim": "end",
    "pagedown": "pgdn", "pageup": "pgup",
    "cima": "up", "baixo": "down", "esquerda": "left", "direita": "right",
    "seta cima": "up", "seta baixo": "down", "seta esquerda": "left", "seta direita": "right",
    "imprimir tela": "printscreen", "print": "printscreen",
    "menu de contexto": "apps", "contexto": "apps",
}
for _i in range(1, 25):
    _TECLAS[f"f{_i}"] = f"f{_i}"


def _mapa_teclas(texto):
    partes = [p.strip().lower() for p in re.split(r"\s*\+\s*", str(texto or "")) if p.strip()]
    return [_TECLAS.get(p, _TECLAS.get(_sem_acento(p), p)) for p in partes]


def _digitar(texto):
    """Escreve na janela em foco colando (ctrl+v), e devolve o que
    estava na área de transferência antes, para não atrapalhar o usuário.
    """
    guardado = None
    try:
        guardado = pyperclip.paste()
    except Exception:
        guardado = None
    try:
        pyperclip.copy(texto)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.12)
    finally:
        if guardado is not None:
            try:
                pyperclip.copy(guardado)
            except Exception:
                pass


def _arrastar(x1, y1, x2, y2):
    """Arrasta em vários passos pequenos: o Explorador e o navegador só
    começam a arrastar depois de ver o mouse ANDAR com o botão apertado.
    """
    pyautogui.moveTo(x1, y1, duration=0.15)
    pyautogui.mouseDown()
    time.sleep(0.15)
    passos = 10
    for i in range(1, passos + 1):
        pyautogui.moveTo(
            round(x1 + (x2 - x1) * i / passos),
            round(y1 + (y2 - y1) * i / passos),
            duration=0.03,
        )
    time.sleep(0.3)
    pyautogui.moveTo(x2, y2)
    pyautogui.mouseUp()
    time.sleep(0.3)


def _executar_acao(acao, captura, freio):
    tipo = str(acao.get("tipo") or "").strip().lower()
    alvo = str(acao.get("alvo") or "").strip()

    motivo = _acao_perigosa(acao)
    if motivo:
        return False, f"não fiz — {motivo}, e isso é bloqueado sem confirmação"

    if tipo in ("credencial", "senha", "login"):
        return False, "não tenho um cofre de credenciais guardado — peça ao usuário para digitar"

    if tipo in ("clicar", "clicar_duplo", "clicar_direito", "mover"):
        if acao.get("x") is None or acao.get("y") is None:
            return False, f"{tipo} sem coordenadas — nada feito"
        x, y = _pixel_absoluto(captura, acao.get("x"), acao.get("y"))
        pyautogui.moveTo(x, y, duration=0.18)
        if tipo == "mover":
            return True, f"mouse movido até {alvo or f'({x},{y})'}"
        if tipo == "clicar_duplo":
            pyautogui.click(x, y, clicks=2, interval=0.08)
            return True, f"cliquei duas vezes em {alvo or f'({x},{y})'}"
        if tipo == "clicar_direito":
            pyautogui.click(x, y, button="right")
            return True, f"cliquei com o botão direito em {alvo or f'({x},{y})'} (o menu deve ter aberto)"
        pyautogui.click(x, y)
        return True, f"cliquei em {alvo or f'({x},{y})'}"

    if tipo == "arrastar":
        if None in (acao.get("x"), acao.get("y"), acao.get("x2"), acao.get("y2")):
            return False, "arrastar sem origem e destino completos — nada feito"
        x1, y1 = _pixel_absoluto(captura, acao.get("x"), acao.get("y"))
        x2, y2 = _pixel_absoluto(captura, acao.get("x2"), acao.get("y2"))
        _arrastar(x1, y1, x2, y2)
        return True, f"arrastei até {alvo or f'({x2},{y2})'}"

    if tipo == "digitar":
        texto = str(acao.get("texto") or "")
        if not texto:
            return False, "digitar sem texto — nada feito"
        if _janela_e_do_softia():
            return False, "a janela do SOFTIA estava em primeiro plano — não digitei nada"
        _digitar(texto)
        return True, f"digitei {texto[:45]!r}" + (f" em {alvo}" if alvo else "")

    if tipo == "tecla":
        teclas = _mapa_teclas(acao.get("teclas") or "")
        if not teclas:
            return False, "tecla vazia — nada feito"
        invalidas = [t for t in teclas if t not in pyautogui.KEYBOARD_KEYS]
        if invalidas:
            return False, f"não conheço a tecla {', '.join(invalidas)!r}"
        freio.ignorar_por(0.4)
        if len(teclas) == 1:
            pyautogui.press(teclas[0])
        else:
            pyautogui.hotkey(*teclas)
        return True, f"apertei {'+'.join(teclas)}"

    if tipo in ("rolar", "scroll"):
        direcao = _sem_acento(str(acao.get("direcao") or "baixo"))
        try:
            quantidade = max(1, min(20, int(acao.get("quantidade") or 3)))
        except (TypeError, ValueError):
            quantidade = 3
        larg, alt = pyautogui.size()
        pyautogui.moveTo(larg // 2, alt // 2, duration=0.1)
        sinal = 1 if direcao in ("cima", "up", "acima") else -1
        pyautogui.scroll(sinal * quantidade * 120)
        return True, f"rolei {quantidade} para {direcao}"

    return False, f"não conheço a ação {tipo!r}"


# ── Perguntar ao Gemini o que fazer ─────────────────────────────────────

ESQUEMA_PASSO = {
    "type": "object",
    "properties": {
        "estado": {
            "type": "string",
            "enum": ["continuar", "concluido", "falhou"],
        },
        "mensagem": {"type": "string"},
        "acoes": {
            "type": "array",
            "maxItems": MAX_ACOES_POR_PASSO,
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": [
                            "clicar", "clicar_duplo", "clicar_direito", "mover",
                            "arrastar", "digitar", "tecla", "rolar",
                        ],
                    },
                    "alvo": {"type": "string"},
                    "x": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "y": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "x2": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "y2": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "texto": {"type": "string"},
                    "teclas": {"type": "string"},
                    "direcao": {"type": "string"},
                    "quantidade": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["tipo"],
            },
        },
    },
    "required": ["estado", "mensagem", "acoes"],
}

_INSTRUCOES = """Você está controlando o mouse e o teclado de um computador Windows
para completar a tarefa abaixo, olhando uma foto da tela a cada rodada.

Responda em JSON conforme o schema. Em "acoes", devolva até {max_acoes} movimentos
para executar em sequência ANTES da próxima foto — só encadeie movimentos quando
tiver certeza do que vai aparecer (ex.: clicar num campo e digitar em seguida).

Coordenadas x,y são NORMALIZADAS de 0 a 1000 na foto atual: x=0 é a borda
esquerda, x=1000 a direita; y=0 é o topo, y=1000 o rodapé. "arrastar" usa
x,y para a origem e x2,y2 para o destino.

Em "alvo", descreva em poucas palavras o que está clicando/mexendo (ex.:
"botão Salvar", "campo de busca") — ajuda a auditar o que foi feito.

Use "estado":"concluido" com uma "mensagem" curta assim que a tarefa estiver
pronta. Use "estado":"falhou" se não for possível continuar, explicando o
motivo em "mensagem". Caso contrário, "estado":"continuar".

NÃO tente pagar, comprar, excluir, apagar, enviar, transferir, instalar,
desinstalar, formatar ou desligar nada — essas ações são sempre bloqueadas
e o passo será recusado; use "falhou" explicando isso em vez de tentar.

TAREFA: {tarefa}
""".format(max_acoes=MAX_ACOES_POR_PASSO, tarefa="{tarefa}")


def _montar_prompt(tarefa, historico, passo, aviso_parado):
    partes = [_INSTRUCOES.format(tarefa=tarefa)]
    partes.append(f"\nRodada {passo} de {MAX_PASSOS}.")
    if aviso_parado:
        partes.append(aviso_parado)
    if historico:
        partes.append("\nO que já foi feito, mais recente por último:")
        for linha in historico[-10:]:
            partes.append(f"- {linha}")
    return "\n".join(partes)


def _resumo(historico):
    if not historico:
        return "Nenhuma ação chegou a ser feita."
    return "Últimas ações: " + "; ".join(historico[-5:]) + "."


# ── Função principal ────────────────────────────────────────────────────

def usar_computador(tarefa):
    """Olha a tela, decide, clica/digita/arrasta sozinho e confere o
    resultado, em loop, até terminar a tarefa pedida ou desistir.

    tarefa: o que o usuário quer que seja feito no computador, nas
            palavras dele (ex.: "abre o bloco de notas e escreve...").
    """
    if not tarefa or not str(tarefa).strip():
        return "Preciso saber o que fazer no computador."

    bloqueio = _tarefa_bloqueada(tarefa)
    if bloqueio:
        return f"Não vou fazer isso no computador: {bloqueio}."

    if not GEMINI_API_KEY:
        return "GEMINI_API_KEY não encontrada."

    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.0

    freio = _FreioEsc()
    freio.ligar()

    cliente = genai.Client(api_key=GEMINI_API_KEY)

    historico = []
    hash_anterior = None
    sem_mudanca = 0
    inicio = time.monotonic()

    try:
        for passo in range(1, MAX_PASSOS + 1):
            if freio.apertado:
                return "Parei na hora porque você apertou ESC. " + _resumo(historico)

            if time.monotonic() - inicio > TEMPO_MAXIMO_S:
                return "Parei porque a tarefa passou de 10 minutos. " + _resumo(historico)

            captura = _capturar_tela()

            aviso_parado = ""
            if hash_anterior is not None and captura["hash"] == hash_anterior:
                sem_mudanca += 1
                if sem_mudanca >= SEM_MUDANCA_LIMITE:
                    return "Desisti: a tela não mudou depois de várias tentativas. " + _resumo(historico)
                aviso_parado = "A tela NÃO mudou desde a última ação — tente outro caminho."
            else:
                sem_mudanca = 0
            hash_anterior = captura["hash"]

            prompt = _montar_prompt(tarefa, historico, passo, aviso_parado)

            try:
                resposta = cliente.models.generate_content(
                    model=MODELO_VISAO,
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=captura["bytes"], mime_type="image/jpeg"),
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        response_schema=ESQUEMA_PASSO,
                    ),
                )
                dados = _extrair_json(resposta.text)
            except Exception as erro:
                return f"Não consegui decidir o próximo passo: {erro}. " + _resumo(historico)

            estado = str(dados.get("estado") or "continuar").strip().lower()
            mensagem = str(dados.get("mensagem") or "").strip()

            if estado == "concluido":
                return mensagem or "Pronto, tarefa concluída."

            if estado == "falhou":
                return f"Não consegui completar: {mensagem or 'motivo não informado'}. " + _resumo(historico)

            acoes = dados.get("acoes") or []
            if not acoes:
                historico.append("(nenhuma ação neste passo)")
                continue

            for acao in acoes[:MAX_ACOES_POR_PASSO]:
                if freio.apertado:
                    return "Parei na hora porque você apertou ESC. " + _resumo(historico)
                ok, relato = _executar_acao(acao, captura, freio)
                historico.append(relato)
                if not ok:
                    break
                time.sleep(0.35)

        return "Parei: cheguei ao limite de passos sem terminar a tarefa. " + _resumo(historico)

    finally:
        freio.parar()
