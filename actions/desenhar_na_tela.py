# -*- coding: utf-8 -*-
# ============================================================
# SOFTIA - DESENHAR DE VERDADE NO PAINT (UI Automation)
# ============================================================
#
# Portado do JARVIS-CyberBot (actions/desenhar_na_tela.py, 2148
# linhas) em 19/09/2026, a pedido do Klecio.
#
# A IDEIA, que continua igual: o cérebro decide o desenho INTEIRO
# de uma vez (uma lista de formas geométricas com cor, preenchimento
# e coordenadas) e este arquivo EXECUTA o plano no Paint do Windows
# 11 com a ferramenta certa para cada peça — retângulo com a
# ferramenta Retângulo, sol com a Oval, telhado com o Triângulo —
# achando os botões e as amostras de cor PELO NOME, com a API de
# acessibilidade do Windows (UIA, a mesma que um leitor de tela
# usa), e desenhando com SendInput. Fazer isso passo a passo pela
# rede (como o computer use faz) dá quatro traços tortos; o plano
# inteiro de uma vez e a execução local em segundos é o que faz o
# desenho sair parecido com o pedido.
#
# O QUE MUDOU EM RELAÇÃO AO JARVIS ORIGINAL:
#
# - QUEM PENSA O DESENHO: o JARVIS mandava a receita para uma VPS
#   que conversava com o Codex CLI. Aqui é uma chamada direta à API
#   do Gemini (google.genai), pedindo o plano de formas em JSON
#   ESTRUTURADO (response_schema) — sem VPS, sem Codex, mesma chave
#   usada no resto do SOFTIA. Como a saída já vem validada pelo
#   schema, a lógica de "tentar de novo se não veio JSON válido" do
#   original ficou mais simples (mas o `_limpar_plano`, que conserta
#   valor fora da faixa e nome de forma torto, continua).
# - JANELA SEM PYWIN32: o SOFTIA não tem win32gui/win32com como
#   dependência. Achar a janela do Paint, focar e maximizar virou
#   ctypes puro (EnumWindows, SetForegroundWindow, ShowWindow —
#   mesmo padrão já usado em actions/janela_actions.py).
# - UIA CONTINUA COMO NO ORIGINAL: comtypes é uma dependência NOVA
#   (adicionada só para isto), diferente de pywin32. A classe
#   `PaintPorAcessibilidade`, a thread MTA e o SendInput foram
#   traduzidos quase linha a linha — é a parte que funciona de
#   verdade e não tinha por que reinventar.
# - ESC PARA NA HORA: o freio (`_FreioEsc`, ctypes GetAsyncKeyState)
#   é o mesmo padrão já portado em actions/usar_computador.py.
#   Duplicado aqui de propósito — é pequeno e este código já
#   duplica bastante entre arquivos de ações, por design.
#
# O QUE FOI CORTADO (e por quê):
# - A SEGUNDA PASSADA de autocrítica do plano ("_melhorar_o_plano" no
#   original, o modelo relê o próprio plano e conserta sobreposição/
#   corte na borda) e o VEREDITO POR VISÃO depois de pronto (o
#   modelo OLHA a foto do desenho e manda refazer se saiu ruim) foram
#   cortados. Os dois dobravam o número de chamadas ao Gemini e o
#   tempo de espera — deixados de fora para manter o primeiro porte
#   simples; a base (plano único bem instruído + `_limpar_plano`)
#   já cobre o essencial. Dá para trazer depois se fizer falta.
# - "DESENHAR EM CIMA DE UMA FOTO" (a foto vira a folha e o desenho
#   pedido entra por cima dela) foi cortado. "DESENHAR A FOTO" (a
#   foto vira desenho sozinha, via OpenCV) continua.
# - SUPORTE A OUTROS EDITORES (Photoshop, GIMP, Krita, Paint 3D) foi
#   cortado — sempre Paint. Se a janela for o Paint CLÁSSICO do
#   Windows 10 (sem as marcas do Paint novo), o plano ainda sai: cai
#   no caminho de montar a imagem com Pillow e colar (Ctrl+V), que
#   funciona em qualquer editor de imagem, mas só é acionado para o
#   Paint aqui.
# - NARRAÇÃO CONTÍNUA durante o desenho ("ainda desenhando, não mexa
#   no mouse") e o registro no diário de memória foram cortados — o
#   SOFTIA ainda não tem `narrador_pc` nem um diário automático
#   (ambos pendentes no PENDENCIAS.txt).
# - "Melhora essa casa" (refazer o último pedido com uma crítica em
#   palavras) continua: é barato e não depende da autocrítica cortada
#   acima.
#
# O QUE FICOU IGUAL:
# - As QUATRO ARMADILHAS medidas no original (ver os comentários
#   junto de cada uma abaixo): UIA só funciona em thread MTA;
#   SetCursorPos+mouse_event não desenha no Paint novo (tem de ser
#   SendInput); o Enter não fixa a forma (quem fixa é trocar de
#   ferramenta); Cor 1 é o preenchimento e Cor 2 é o contorno.
# - A folha sempre no maior tamanho que couber na janela.
# - O teto de peças e de tempo, com aviso HONESTO do que ficou de
#   fora (nunca corta calado).
# - Nunca o mesmo desenho duas vezes (empurrão de variação sorteado).
# ============================================================
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import math
import random
import re
import subprocess
import threading
import time
import unicodedata

from google import genai
from google.genai import types

from core.config import GEMINI_API_KEY


# Modelo usado para pensar o plano de desenho. Mesmo escolhido no
# resto do SOFTIA para tarefas de texto/estruturadas fora da
# conversa por voz (code_actions.py, comando_actions.py).
MODELO_DESENHO = "gemini-3.6-flash"

# O último plano que o Gemini devolveu, e o último pedido — o que
# faz "melhora essa casa" funcionar sem que o dono repita o pedido.
ULTIMO_PLANO: dict = {}
ULTIMO_PEDIDO: str = ""
ULTIMO_EM: float = 0.0


def ultimo_desenho(dentro_de_s: float = 1800.0) -> str:
    """O que foi pedido por último para desenhar, se foi há pouco. Senão, vazio."""
    if not ULTIMO_PEDIDO or not ULTIMO_EM:
        return ""
    return ULTIMO_PEDIDO if (time.monotonic() - ULTIMO_EM) <= dentro_de_s else ""


# Teto de peças e de tempo. O que passar do teto é CORTADO, mas
# DITO na resposta — um teto que corta calado faz o SOFTIA dizer que
# terminou com o desenho pela metade.
TETO_DE_PECAS = 70
TETO_DE_TEMPO_S = 210.0

_VK_RETURN, _VK_ESCAPE = 0x0D, 0x1B
_MOUSE_DOWN, _MOUSE_UP = 0x0002, 0x0004

# Identificadores do UIA (números fixos da Microsoft, não mudam).
_UIA_Name, _UIA_AutoId, _UIA_ControlType = 30005, 30011, 30003
_TIPO_BOTAO, _TIPO_ITEM_LISTA, _TIPO_MENU = 50000, 50007, 50011
_TIPO_RADIO, _TIPO_SLIDER = 50013, 50015
_ESCOPO_DESCENDENTES = 4
_PADRAO_FAIXA = 10003            # RangeValuePattern (o cursor de Tamanho)


# ─────────────────────────────────────────────────────────── texto e cor
def _vazio(el) -> bool:
    """O UIA não devolve None quando não acha: devolve um PONTEIRO NULO.

    `if el is None` dá False para o ponteiro nulo — e a linha seguinte
    estoura com "NULL COM pointer access". O ponteiro nulo é FALSO num
    if, então a conferência certa é esta.
    """
    return el is None or not bool(el)


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFD", str(texto or "").strip().lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t)


def _hex_para_rgb(valor: str):
    s = str(valor or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return None


def _distancia_de_cor(a, b) -> float:
    """Quão diferentes duas cores parecem AO OLHO — fórmula clássica
    ponderada pelo vermelho (sem ela, azul escuro e preto ficam
    "perto" e um céu noturno vira um borrão)."""
    rm = (a[0] + b[0]) / 2.0
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return math.sqrt((2 + rm / 256.0) * dr * dr + 4 * dg * dg
                     + (2 + (255 - rm) / 256.0) * db * db)


# As 20 cores fixas da paleta padrão do Paint (nome sem acento -> RGB).
# Só serve de rede de segurança: o normal é ler nome e cor do próprio
# Paint (ver `PaintPorAcessibilidade.paleta`).
_PALETA_CONHECIDA = {
    "preto": (0, 0, 0), "cinza": (127, 127, 127), "vermelho escuro": (136, 0, 21),
    "vermelho": (237, 28, 36), "laranja": (255, 127, 39), "amarelo": (255, 242, 0),
    "verde": (34, 177, 76), "turquesa": (0, 162, 232), "indigo": (63, 72, 204),
    "roxo": (163, 73, 164), "branco": (255, 255, 255), "cinza claro": (195, 195, 195),
    "marrom": (185, 122, 87), "rosa": (255, 174, 201), "dourado": (255, 201, 14),
    "amarelo claro": (239, 228, 176), "lima": (181, 230, 29),
    "turqueza claro": (153, 217, 234), "cinza azulado": (112, 146, 190),
    "lavanda": (200, 191, 231),
}

# Como o dono (e o modelo) chamam a cor -> como o Paint chama.
_APELIDO_DE_COR = {
    "azul": "turquesa", "azul claro": "turqueza claro", "azul escuro": "indigo",
    "ceu": "turqueza claro", "celeste": "turqueza claro", "anil": "indigo",
    "verde claro": "lima", "verde escuro": "verde", "verde limao": "lima",
    "bege": "amarelo claro", "creme": "amarelo claro", "areia": "amarelo claro",
    "ouro": "dourado", "amarelo ouro": "dourado", "mostarda": "dourado",
    "vinho": "vermelho escuro", "bordo": "vermelho escuro", "telha": "vermelho escuro",
    "tijolo": "vermelho escuro", "salmao": "rosa", "pele": "rosa",
    "madeira": "marrom", "terra": "marrom", "cafe": "marrom", "castanho": "marrom",
    "prata": "cinza claro", "chumbo": "cinza", "grafite": "cinza",
    "violeta": "roxo", "lilas": "lavanda", "magenta": "roxo", "purpura": "roxo",
    "ciano": "turquesa", "turqueza": "turquesa", "laranja escuro": "laranja",
    "cinza-azulado": "cinza azulado",
}

# Como o modelo pede a forma -> o nome do botão no Paint (sem acento).
_APELIDO_DE_FORMA = {
    "retangulo": "retangulo", "quadrado": "retangulo", "caixa": "retangulo",
    "retangulo arredondado": "retangulo arredondado",
    "quadrado arredondado": "retangulo arredondado",
    "circulo": "oval", "elipse": "oval", "oval": "oval", "bola": "oval",
    "triangulo": "triangulo", "triangulo retangulo": "triangulo retangulo",
    "losango": "losango", "diamante": "losango",
    "pentagono": "pentagono", "hexagono": "hexagono",
    "estrela": "estrela de cinco pontas",
    "estrela de quatro pontas": "estrela de quatro pontas",
    "estrela de cinco pontas": "estrela de cinco pontas",
    "estrela de seis pontas": "estrela de seis pontas",
    "coracao": "coracao", "raio": "raio",
    "seta": "seta para a direita",
    "seta para a direita": "seta para a direita",
    "seta para a esquerda": "seta para a esquerda",
    "seta para cima": "seta para cima", "seta para baixo": "seta para baixo",
    "balao": "balao em elipse", "balao em elipse": "balao em elipse",
    "balao retangular arredondado": "balao retangular arredondado",
    "nuvem": "balao em nuvem", "balao em nuvem": "balao em nuvem",
}
_FORMAS_DE_PONTOS = ("linha", "poligono", "traco", "curva", "livre", "mao livre")


# ─────────────────────────────────────────────────────── mouse e teclado
#
# POR QUE `SendInput` E NÃO `mouse_event` — medido no JARVIS original,
# custou três rodadas de teste. `SetCursorPos` + `mouse_event` é o
# jeito antigo, e no Paint do Windows 11 ele FALHA QUASE SEMPRE, sem
# erro nenhum: o mouse anda na tela, mas o Paint simplesmente não
# desenha (de 18 formas, saíram 2). O Paint novo é WinUI 3 e lê
# entrada por POINTER, não pela fila antiga de mouse — `SendInput`
# com MOVE|ABSOLUTE entra pelo caminho que ele escuta. Não mexer
# nisto de volta.
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_ulonglong
                 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong)]


class _ENTRADA(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT), ("enchimento", ctypes.c_ubyte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("tipo", ctypes.c_ulong), ("u", _U)]


_MOVER_ABS = 0x0001 | 0x8000          # MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE


def _tela_virtual():
    """(esquerda, topo, largura, altura) de todos os monitores juntos."""
    u = ctypes.windll.user32
    larg = u.GetSystemMetrics(78) or u.GetSystemMetrics(0)
    alt = u.GetSystemMetrics(79) or u.GetSystemMetrics(1)
    return u.GetSystemMetrics(76), u.GetSystemMetrics(77), max(2, larg), max(2, alt)


def _enviar_mouse(x=None, y=None, bandeiras: int = 0) -> None:
    ev = _ENTRADA(tipo=0)
    if x is not None:
        esq, topo, larg, alt = _tela_virtual()
        ev.mi.dx = int((int(x) - esq) * 65535 / (larg - 1))
        ev.mi.dy = int((int(y) - topo) * 65535 / (alt - 1))
        bandeiras |= _MOVER_ABS
    ev.mi.dwFlags = bandeiras
    ctypes.windll.user32.SendInput(1, ctypes.byref(ev), ctypes.sizeof(_ENTRADA))


def _mover(x: int, y: int) -> None:
    _enviar_mouse(x, y)


def _clique(x: int = None, y: int = None, espera: float = 0.05) -> None:
    if x is not None:
        _mover(x, y)
        time.sleep(0.06)
    _enviar_mouse(bandeiras=_MOUSE_DOWN)
    time.sleep(0.05)
    _enviar_mouse(bandeiras=_MOUSE_UP)
    time.sleep(espera)


# O freio do ESC, para a duração do desenho. Fica aqui em cima porque
# `_tecla` precisa dele: o PRÓPRIO desenho aperta ESC (fechar menu,
# soltar seleção) e o freio não distingue tecla de gente de tecla de
# programa — sem este aviso ele pararia sozinho.
_FREIO = None


def _tecla(vk: int) -> None:
    if vk == _VK_ESCAPE and _FREIO is not None:
        try:
            _FREIO.ignorar_por(0.9)
        except Exception:
            pass
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.02)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
    time.sleep(0.05)


def _arrastar(x1, y1, x2, y2, passos: int = 10) -> None:
    """Arrasto com passos no meio — o Paint não desenha se o mouse
    pular do início ao fim, precisa ver as posições entre os dois."""
    _mover(x1, y1)
    time.sleep(0.09)
    _enviar_mouse(bandeiras=_MOUSE_DOWN)
    time.sleep(0.08)
    for i in range(1, passos + 1):
        _mover(x1 + (x2 - x1) * i / passos, y1 + (y2 - y1) * i / passos)
        time.sleep(0.010)
    time.sleep(0.08)
    _enviar_mouse(bandeiras=_MOUSE_UP)
    time.sleep(0.11)


def _poligono(pontos) -> None:
    """A ferramenta POLÍGONO do Paint: arrasta o 1º lado, clica os
    vértices e fecha com clique duplo no ponto de partida.

    Por que ela e não o balde de tinta: o balde só pinta a mancha
    CONTÍNUA de cor igual embaixo do clique — se já houver desenho
    atrás (uma montanha cruzando o telhado), a área de dentro fica
    cortada em pedaços e ele pinta só um. O polígono nativo cobre a
    área inteira, aconteça o que acontecer embaixo.
    """
    if len(pontos) < 3:
        _tracar_pontos(pontos)
        return
    _arrastar(*pontos[0], *pontos[1], passos=10)     # o primeiro lado
    for x, y in pontos[2:]:
        _clique(x, y, espera=0.16)
    _mover(*pontos[0])
    time.sleep(0.18)
    _clique(espera=0.10)
    _clique(espera=0.45)


def _menos_pontos(pontos, teto: int = 14):
    """Polígono com 40 vértices são 40 cliques (14s). Guarda os que
    importam, tirando sempre o vértice mais "reto" (mesmo critério do
    Douglas-Peucker, só que por contagem)."""
    pts = [tuple(p) for p in pontos]
    while len(pts) > teto:
        pior, pior_custo = 1, None
        for i in range(1, len(pts) - 1):
            (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
            custo = abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0))
            if pior_custo is None or custo < pior_custo:
                pior, pior_custo = i, custo
        pts.pop(pior)
    return pts


def _tracar_pontos(pontos, passo_px: float = 12.0) -> None:
    """Mão livre: aperta, passeia por todos os pontos, solta."""
    if len(pontos) < 2:
        return
    _mover(*pontos[0])
    time.sleep(0.12)
    _enviar_mouse(bandeiras=_MOUSE_DOWN)
    time.sleep(0.10)
    for (x1, y1), (x2, y2) in zip(pontos, pontos[1:]):
        dist = math.hypot(x2 - x1, y2 - y1)
        n = max(2, int(dist / passo_px))
        for i in range(1, n + 1):
            _mover(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n)
            time.sleep(0.006)
    time.sleep(0.10)
    _enviar_mouse(bandeiras=_MOUSE_UP)
    time.sleep(0.15)


# ── ESC mata o desenho, em qualquer janela (mesmo padrão do usar_computador) ──
class _FreioEsc:
    """ESC apertado em QUALQUER lugar interrompe o desenho na hora.

    Uma thread pergunta ao Windows, 20x por segundo, se ESC está
    pressionado AGORA (GetAsyncKeyState enxerga a tecla em qualquer
    janela). O próprio desenho às vezes aperta Esc (soltar seleção) —
    por isso `ignorar_por()` antes, senão pararia sozinho.
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
        self._thread = threading.Thread(target=self._laco, daemon=True, name="freio-esc-desenhar")
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


# ───────────────────────────────────────────────────────── o Paint pelo UIA
class PaintPorAcessibilidade:
    """Os botões do Paint achados pelo NOME, não pelo pixel."""

    def __init__(self, hwnd: int, log=None):
        import comtypes.client  # noqa: PLC0415
        self._log = log or (lambda _m: None)
        self._mod = comtypes.client.GetModule("UIAutomationCore.dll")
        self._uia = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}", interface=self._mod.IUIAutomation)
        self.hwnd = hwnd
        self._raiz = self._uia.ElementFromHandle(hwnd)
        self._cache: dict = {}
        self._ferramenta = ""
        self._cor1 = ""
        self._cor2 = ""
        self._modo_preenche = ""
        self._grossura_forma = 0
        self._grossura_lapis = -1
        self._forma_solta = False        # há uma forma desenhada e não fixada

    # -- procurar -------------------------------------------------------
    def _achar(self, nome=None, autoid=None, tipo=None, de=None):
        cond = []
        if nome is not None:
            cond.append(self._uia.CreatePropertyCondition(_UIA_Name, nome))
        if autoid is not None:
            cond.append(self._uia.CreatePropertyCondition(_UIA_AutoId, autoid))
        if tipo is not None:
            cond.append(self._uia.CreatePropertyCondition(_UIA_ControlType, tipo))
        if not cond:
            return None
        c = cond[0] if len(cond) == 1 else self._uia.CreateAndConditionFromArray(cond)
        return (de or self._raiz).FindFirst(_ESCOPO_DESCENDENTES, c)

    def _todos(self, tipo, de=None):
        c = self._uia.CreatePropertyCondition(_UIA_ControlType, tipo)
        achados = (de or self._raiz).FindAll(_ESCOPO_DESCENDENTES, c)
        return [achados.GetElement(i) for i in range(achados.Length)]

    @staticmethod
    def _centro(el):
        r = el.CurrentBoundingRectangle
        return ((r.left + r.right) // 2, (r.top + r.bottom) // 2)

    def _clicar_elemento(self, el, espera: float = 0.12) -> bool:
        if _vazio(el):
            return False
        x, y = self._centro(el)
        if x <= 0 and y <= 0:
            return False
        _clique(x, y, espera)
        return True

    def _por_nome(self, nome: str, tipo=None):
        """Acha pelo nome exato; guarda para não procurar de novo.

        Não guarda quando não acha: um menu de flyout só existe
        enquanto está aberto, guardar o vazio faria a próxima
        tentativa falhar de graça.
        """
        chave = (nome, tipo)
        achado = self._cache.get(chave)
        if _vazio(achado):
            achado = self._achar(nome=nome, tipo=tipo)
            if not _vazio(achado):
                self._cache[chave] = achado
        return achado

    # -- peças do Paint --------------------------------------------------
    def retangulo_da_tela(self):
        """A área branca onde se desenha, em pixel de tela."""
        el = self._achar(autoid="image")
        if _vazio(el):
            return None
        r = el.CurrentBoundingRectangle
        return (r.left, r.top, r.right, r.bottom)

    def area_visivel(self):
        """O espaço onde a folha cabe (a parte rolável da janela)."""
        el = self._achar(autoid="scrollViewer")
        if _vazio(el):
            return None
        r = el.CurrentBoundingRectangle
        return (r.left, r.top, r.right, r.bottom)

    def usar_folha_maxima(self, tentativas: int = 5) -> bool:
        """Deixa a folha do tamanho da janela ANTES de desenhar.

        A folha do Paint GUARDA o tamanho da última imagem — basta
        ter aberto uma foto pequena um dia para o desenho nascer do
        tamanho de um selo. Só AUMENTA, nunca diminui.

        VÁRIAS voltas porque a folha é CENTRALIZADA: quando cresce,
        ela anda para a esquerda e a alça que acabou de ser solta já
        não está onde a conta dizia — cada volta ganha só metade do
        que falta.
        """
        mudou = False
        for _ in range(max(1, tentativas)):
            folha = self.retangulo_da_tela()
            espaco = self.area_visivel()
            if not folha or not espaco:
                return mudou
            fl, ft, fr, fb = folha
            el_, et, er, eb = espaco
            alvo_x = min(fl + (er - el_) - 44, er - 22)
            alvo_y = min(ft + (eb - et) - 44, eb - 22)
            if alvo_x <= fr + 12 and alvo_y <= fb + 12:
                return mudou            # já está do tamanho da janela
            self._log(f"[desenhar] folha {fr - fl}x{fb - ft}; esticando para caber na janela")
            # A ALÇA FICA FORA DA FOLHA, NÃO EM CIMA DELA (medido no
            # original): em (fr,fb) e (fr-3,fb-3) não acontece nada;
            # em (fr+2,fb+2) e (fr+5,fb+5) ela estica.
            _arrastar(fr + 4, fb + 4, max(alvo_x, fr), max(alvo_y, fb), passos=18)
            time.sleep(0.6)
            mudou = True
        return mudou

    def paleta(self) -> dict:
        """{nome sem acento: (elemento, (r,g,b))} — as 20 amostras da barra."""
        if "paleta" in self._cache:
            return self._cache["paleta"]
        grupo = self._achar(nome="Cores")
        itens = [] if _vazio(grupo) else self._todos(_TIPO_ITEM_LISTA, de=grupo)
        foto = None
        try:
            from PIL import ImageGrab  # noqa: PLC0415
            foto = ImageGrab.grab(all_screens=True)
        except Exception:
            pass
        saida = {}
        for el in itens:
            nome = _sem_acento(el.CurrentName)
            if not nome:
                continue
            rgb = _PALETA_CONHECIDA.get(nome)
            if foto is not None:
                try:
                    rgb = foto.getpixel(self._centro(el))[:3]
                except Exception:
                    pass
            if rgb:
                saida[nome] = (el, tuple(rgb))
        self._cache["paleta"] = saida
        return saida

    def _amostra_de(self, cor: str):
        """Do que foi pedido para a amostra que existe de verdade."""
        paleta = self.paleta()
        if not paleta:
            return None, ""
        pedido = _sem_acento(cor)
        if not pedido:
            return None, ""
        pedido = _APELIDO_DE_COR.get(pedido, pedido)
        if pedido in paleta:
            return paleta[pedido][0], pedido
        alvo = _hex_para_rgb(pedido)
        if alvo is None:
            for nome in paleta:
                if pedido in nome or nome in pedido:
                    return paleta[nome][0], nome
            alvo = _PALETA_CONHECIDA.get(pedido)
        if alvo is None:
            return None, ""
        melhor = min(paleta.items(), key=lambda kv: _distancia_de_cor(alvo, kv[1][1]))
        return melhor[1][0], melhor[0]

    def cor(self, qual: int, nome_da_cor: str) -> str:
        """Põe a cor na Cor 1 ou na Cor 2.

        CUIDADO, ISTO É AO CONTRÁRIO DO QUE PARECE: no Paint do
        Windows 11, para as FORMAS, a Cor 1 é o PREENCHIMENTO e a
        Cor 2 é o CONTORNO — o contrário do Paint antigo (medido com
        uma bola de Cor 1 vermelha e Cor 2 amarela: saiu vermelha por
        dentro e com a borda amarela). Para o Lápis e o balde, Cor 1
        é a cor que pinta. Use `cor_de_dentro`/`cor_do_contorno`, que
        já tratam disso pelo nome.
        """
        amostra, nome = self._amostra_de(nome_da_cor)
        if _vazio(amostra):
            return ""
        atual = self._cor1 if qual == 1 else self._cor2
        if atual == nome:
            return nome
        prefixo = "Cor 1" if qual == 1 else "Cor 2"
        alvo = None
        for el in self._todos(_TIPO_RADIO):
            if (el.CurrentName or "").startswith(prefixo):
                alvo = el
                break
        if not _vazio(alvo):
            self._clicar_elemento(alvo, 0.07)
        self._clicar_elemento(amostra, 0.07)
        if qual == 1:
            self._cor1 = nome
        else:
            self._cor2 = nome
        return nome

    def cor_de_dentro(self, nome_da_cor: str) -> str:
        """A cor que enche a forma. No Paint do Win11 é a Cor 1."""
        return self.cor(1, nome_da_cor)

    def cor_do_contorno(self, nome_da_cor: str) -> str:
        """A cor da borda da forma. No Paint do Win11 é a Cor 2."""
        return self.cor(2, nome_da_cor)

    def limpar_folha(self) -> None:
        """Apaga tudo e deixa a folha branca, só para REFAZER o desenho."""
        self.carimbar()
        ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)      # Ctrl
        _tecla(0x41)                                          # A
        ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
        time.sleep(0.35)
        _tecla(0x2E)                                          # Delete
        time.sleep(0.5)
        _tecla(_VK_ESCAPE)                                    # solta a seleção
        time.sleep(0.3)
        self._ferramenta = ""

    def carimbar(self) -> None:
        """Fixa na imagem a forma que ainda está 'pousada'.

        O ENTER NÃO CARIMBA: depois do Enter a forma continua
        editável — mudar a Cor 1 muda ela junto. O que fixa é TROCAR
        DE FERRAMENTA. O Lápis serve de martelo: é barato, não
        desenha nada por ser escolhido, e deixa tudo pronto para a
        próxima.
        """
        if not self._forma_solta:
            return
        self._forma_solta = False
        self.ferramenta("Lápis")

    def ferramenta(self, nome_uia: str) -> bool:
        """Escolhe a ferramenta/forma pelo nome que o Paint mostra."""
        if self._ferramenta == nome_uia:
            return True
        el = self._por_nome(nome_uia)
        if _vazio(el):
            for cand in self._todos(_TIPO_ITEM_LISTA) + self._todos(_TIPO_BOTAO):
                if _sem_acento(cand.CurrentName) == _sem_acento(nome_uia):
                    el = cand
                    break
        if _vazio(el):
            self._log(f"[desenhar] não achei a ferramenta {nome_uia!r}")
            return False
        if not self._clicar_elemento(el, 0.12):
            return False
        self._ferramenta = nome_uia
        return True

    def grossura_do_lapis(self, px: int) -> None:
        px = max(1, min(90, int(px)))
        if self._grossura_lapis == px:
            return
        for el in self._todos(_TIPO_SLIDER):
            if (el.CurrentName or "") != "Tamanho":
                continue
            try:
                faixa = el.GetCurrentPattern(_PADRAO_FAIXA).QueryInterface(
                    self._mod.IUIAutomationRangeValuePattern)
                faixa.SetValue(float(px))
                self._grossura_lapis = px
            except Exception as exc:
                self._log(f"[desenhar] cursor de tamanho não aceitou: {str(exc)[:60]}")
            return

    def grossura_da_forma(self, px: int) -> None:
        """O menu Tamanho da barra de Formas: 3px, 5px, 8px."""
        px = 8 if px >= 7 else (5 if px >= 4 else 3)
        if self._grossura_forma == px:
            return
        botao = None
        for el in self._todos(_TIPO_BOTAO):
            if (el.CurrentName or "") == "Tamanho":
                r = el.CurrentBoundingRectangle
                if r.top < 200:                    # o da barra, não o cursor lateral
                    botao = el
                    break
        if _vazio(botao) or not self._clicar_elemento(botao, 0.38):
            return
        alvo = self._achar(nome=f"{px}px", tipo=_TIPO_MENU)
        if _vazio(alvo):
            _tecla(_VK_ESCAPE)
            return
        self._clicar_elemento(alvo, 0.16)
        self._grossura_forma = px

    def preenchimento(self, ligado: bool) -> None:
        """Liga/desliga o preenchimento sólido das formas (usa a Cor 2)."""
        desejado = "Preenchimento sólido" if ligado else "Sem preenchimento"
        if self._modo_preenche == desejado:
            return
        botao = self._por_nome("Preenchimento de forma", _TIPO_BOTAO)
        if _vazio(botao) or not self._clicar_elemento(botao, 0.38):
            return
        alvo = self._achar(nome=desejado, tipo=_TIPO_MENU)
        if _vazio(alvo):
            _tecla(_VK_ESCAPE)
            return
        self._clicar_elemento(alvo, 0.16)
        self._modo_preenche = desejado

    def desfazer_tudo(self, vezes: int = 40) -> None:
        for _ in range(vezes):
            ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)      # Ctrl
            _tecla(0x5A)                                         # Z
            ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)


def _e_paint_do_windows_11(paint: PaintPorAcessibilidade) -> bool:
    """O Paint novo (WinUI) x o Paint clássico de faixa do Windows 10.

    As duas marcas do Paint novo são a folha com o identificador
    "image" e o botão "Preenchimento de forma"; nenhuma das duas
    existe no Paint de faixa. No Paint clássico o desenho sai pelo
    caminho universal (montar a imagem com Pillow e colar).
    """
    try:
        if not paint.retangulo_da_tela():
            return False
        return not _vazio(paint._por_nome("Preenchimento de forma", _TIPO_BOTAO))
    except Exception:
        return False


def _nome_de_botao_da_forma(paint: PaintPorAcessibilidade, nome_sem_acento: str) -> str:
    """'coracao' -> 'Coração' (o nome com acento que o Paint mostra)."""
    chave = f"botao:{nome_sem_acento}"
    if chave in paint._cache:
        return paint._cache[chave]
    achado = ""
    for el in paint._todos(_TIPO_ITEM_LISTA) + paint._todos(_TIPO_BOTAO):
        if _sem_acento(el.CurrentName) == nome_sem_acento:
            achado = el.CurrentName
            break
    paint._cache[chave] = achado
    return achado


# ────────────────────────────────────────────── achar/focar a janela (ctypes)
#
# O SOFTIA não tem pywin32. Enumerar janelas, focar e maximizar aqui
# é ctypes puro — mesmo padrão já usado em actions/janela_actions.py.
class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def _listar_janelas():
    user32 = ctypes.windll.user32
    achadas = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _visitar(hwnd, _lp):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            tamanho = user32.GetWindowTextLengthW(hwnd)
            if tamanho <= 0:
                return True
            buf = ctypes.create_unicode_buffer(tamanho + 1)
            user32.GetWindowTextW(hwnd, buf, tamanho + 1)
            achadas.append((hwnd, buf.value))
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(_visitar, 0)
    except Exception:
        pass
    return achadas


def _achar_paint():
    for hwnd, titulo in _listar_janelas():
        if "paint" in titulo.lower():
            return hwnd, titulo
    return 0, ""


def _focar(hwnd: int) -> bool:
    user32 = ctypes.windll.user32
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)        # SW_RESTORE
            time.sleep(0.4)
        for _ in range(3):
            if user32.GetForegroundWindow() == hwnd:
                return True
            try:
                user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
            time.sleep(0.25)
        # SÓ se o Windows recusar: o Alt solto libera o foco — e abre
        # o menu do programa junto, por isso o Esc logo atrás.
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        try:
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(0.25)
        _tecla(_VK_ESCAPE)
        return user32.GetForegroundWindow() == hwnd
    except Exception:
        return False


def _maximizar(hwnd: int) -> None:
    """Janela maior = folha maior = desenho maior. Sempre maximiza o
    Paint: a folha só pode crescer até onde a janela deixa."""
    try:
        ctypes.windll.user32.ShowWindow(hwnd, 3)   # SW_MAXIMIZE
        time.sleep(0.8)
    except Exception:
        pass


def _abrir_paint(log):
    hwnd, _t = _achar_paint()
    if not hwnd:
        try:
            subprocess.Popen(["mspaint.exe"])                     # noqa: S607
        except Exception as exc:
            return 0, f"Não consegui abrir o Paint: {str(exc)[:60]}"
        for _ in range(80):
            time.sleep(0.25)
            hwnd, _t = _achar_paint()
            if hwnd:
                break
        if not hwnd:
            return 0, "Abri o Paint mas a janela não apareceu."
        time.sleep(2.0)                 # janela recém-nascida engole clique
    return hwnd, ""


# ───────────────────────────────────────────────────── o plano do desenho
_CORES_PARA_O_MODELO = ("preto, cinza, cinza claro, branco, vermelho escuro, "
                        "vermelho, laranja, amarelo, amarelo claro, dourado, "
                        "verde, lima, turquesa, turqueza claro, indigo, roxo, "
                        "marrom, rosa, cinza azulado, lavanda")

_FORMAS_COM_TAMANHO = sorted(set(_APELIDO_DE_FORMA.values()))

# A receita enviada ao Gemini. Encolhida em relação ao original (que
# tinha ~2.500 caracteres para sobreviver a um corte de 800 caracteres
# que a VPS antiga fazia) — aqui o texto vai inteiro numa chamada
# direta, sem corte nenhum, então o essencial basta.
_RECEITA = (
    "Você desenha por meio de um robô que opera o Microsoft Paint, escolhendo "
    "a FERRAMENTA certa do Paint para cada peça (retângulo, oval, triângulo, "
    "polígono...). Monte um plano de formas geométricas simples para o pedido "
    "abaixo, respeitando o schema JSON pedido.\n\n"
    "COORDENADAS: x,y é o canto de cima e da esquerda da forma (0 a 1, sendo "
    "0 a borda esquerda/topo da folha); l,a são largura e altura (0 a 1). "
    "Formas com pontos (linha, traço, polígono) usam uma lista de [x,y] em "
    "vez de x,y,l,a.\n\n"
    f"FORMAS COM TAMANHO (x,y,l,a): {', '.join(_FORMAS_COM_TAMANHO)}.\n"
    "FORMAS COM PONTOS: 'poligono' fecha sozinho e pode ser preenchido (bom "
    "para telhado, monte, vela de barco); 'linha' liga dois pontos; 'traco' é "
    "mão livre, não fecha e não preenche (bom para fumaça, cabelo, onda, "
    "galho, detalhe fino).\n\n"
    "CORES — use EXATAMENTE um destes nomes, em 'cor' (contorno) e "
    f"'preenche' (o que enche a forma por dentro): {_CORES_PARA_O_MODELO}.\n\n"
    "O QUE FAZ O DESENHO FICAR BOM:\n"
    "1. De 18 a 34 formas. Quatro traços não é desenho, é rabisco.\n"
    "2. Ordem do FUNDO para a FRENTE: céu e chão primeiro, depois os objetos "
    "grandes, por último os detalhes pequenos — o que vem depois cobre o que "
    "veio antes.\n"
    "3. PREENCHA TUDO QUE É SÓLIDO ('preenche' presente). Forma sem preenche "
    "fica OCA: aparece por dentro dela o que estava atrás, e o desenho fica "
    "furado. Deixe sem preenche só linha e detalhe fino.\n"
    "4. Use a folha inteira: de 0.02 a 0.98. Nada espremido num canto, nada "
    "cortado na borda.\n"
    "5. Detalhe é o que separa desenho de rabisco: janela com cruz, porta com "
    "maçaneta, telha, raio de sol, folhas na árvore.\n"
    "6. Nada de texto escrito.\n"
    "7. CADA COISA É MONTADA COM VÁRIAS PEÇAS, nunca com uma só — um carro não "
    "é um retângulo, é a carroceria, o teto, dois vidros, duas rodas com o "
    "miolo de outra cor, o farol. Gaste de 5 a 8 peças no assunto principal.\n"
    "8. PROPORÇÃO DE GENTE GRANDE: o telhado é mais largo que a parede; a "
    "roda encosta no chão; nada flutuando no ar sem apoio.\n"
)

# NUNCA DUAS VEZES O MESMO DESENHO: um modelo de linguagem repete —
# pedir "uma casa" duas vezes dá a mesma casa. Um empurrão sorteado
# muda o PEDIDO, que é o que realmente muda o resultado.
_EMPURROES = (
    "Mude a HORA: de manhã cedo, ao entardecer, ou de noite com lua e "
    "estrelas — e deixe as cores combinarem com a hora escolhida.",
    "Mude o ÂNGULO e a COMPOSIÇÃO: não ponha o assunto no meio; jogue para um "
    "lado e deixe o outro lado com o cenário.",
    "Acrescente DOIS elementos que ninguém pediu, mas que combinam com a cena.",
    "Mude o CLIMA: chuva, neve, vento, muita nuvem ou sol a pino.",
    "Fuja da cor ÓBVIA: escolha uma paleta diferente da primeira que vier à "
    "cabeça, sem ficar feio.",
    "Ponha VIDA na cena: um bicho, um pássaro, uma pessoa ao longe.",
    "Mude a ESTAÇÃO do ano e deixe isso claro no desenho.",
    "Escolha um PONTO DE VISTA diferente: de baixo para cima, ou de bem "
    "perto.",
)


def _empurrao_de_variacao() -> str:
    return ("\n\nESTE DESENHO TEM DE SER DIFERENTE DE QUALQUER OUTRO QUE VOCÊ "
            "JÁ TENHA FEITO DESTE MESMO ASSUNTO. " + random.choice(_EMPURROES))


# Schema JSON estruturado (response_schema) para a resposta do Gemini —
# substitui a comunicação com a VPS/Codex do original: o modelo devolve
# o plano já validado, sem cerca de código nem texto solto.
_ESQUEMA_FORMA = {
    "type": "object",
    "properties": {
        "forma": {"type": "string", "enum": list(_FORMAS_COM_TAMANHO) + ["poligono", "linha", "traco"]},
        "x": {"type": "number", "minimum": 0, "maximum": 1},
        "y": {"type": "number", "minimum": 0, "maximum": 1},
        "l": {"type": "number", "minimum": 0, "maximum": 1},
        "a": {"type": "number", "minimum": 0, "maximum": 1},
        "pontos": {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "number", "minimum": 0, "maximum": 1},
                "minItems": 2, "maxItems": 2,
            },
        },
        "cor": {"type": "string"},
        "preenche": {"type": "string"},
        "grossura": {"type": "integer", "minimum": 1, "maximum": 20},
    },
    "required": ["forma", "cor"],
}

ESQUEMA_PLANO = {
    "type": "object",
    "properties": {
        "nome": {"type": "string"},
        "formas": {"type": "array", "items": _ESQUEMA_FORMA, "maxItems": TETO_DE_PECAS + 10},
    },
    "required": ["nome", "formas"],
}


def _pedir_plano_ao_gemini(pedido: str, extra: str) -> dict:
    """Chama o Gemini direto (sem VPS, sem Codex) pedindo o plano de
    formas em JSON estruturado."""
    cliente = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"{_RECEITA}\n\nAGORA DESENHE ISTO: {pedido}{extra}"
    resposta = cliente.models.generate_content(
        model=MODELO_DESENHO,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=1.0,
            response_mime_type="application/json",
            response_schema=ESQUEMA_PLANO,
        ),
    )
    texto = str(resposta.text or "").strip()
    if texto.startswith("```"):
        linhas = [l for l in texto.splitlines() if not l.strip().startswith("```")]
        texto = "\n".join(linhas).strip()
    try:
        dados = json.loads(texto)
    except Exception:
        return {}
    return dados if isinstance(dados, dict) else {}


def _numero(v, padrao=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return padrao


def _limpar_plano(bruto: dict) -> dict:
    """Deixa só o que dá para desenhar, e conserta o que dá para
    consertar (nome de forma torto, coordenada fora da folha)."""
    formas = []
    for f in (bruto.get("formas") or []):
        if not isinstance(f, dict):
            continue
        nome = _sem_acento(f.get("forma") or "")
        if not nome:
            continue
        cor = str(f.get("cor") or "preto")
        preenche = f.get("preenche") or ""
        grossura = int(_numero(f.get("grossura"), 5))
        pontos = f.get("pontos") or []
        limpos = []
        for p in pontos if isinstance(pontos, (list, tuple)) else []:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                x, y = _numero(p[0], -1), _numero(p[1], -1)
                if 0 <= x <= 1 and 0 <= y <= 1:
                    limpos.append((x, y))
        if nome in _FORMAS_DE_PONTOS or (limpos and nome not in _APELIDO_DE_FORMA):
            if len(limpos) < 2:
                continue
            formas.append({"forma": "traco" if nome in ("traco", "curva", "livre",
                                                        "mao livre") else nome,
                           "pontos": limpos, "cor": cor,
                           "preenche": str(preenche), "grossura": grossura})
            continue
        alvo = _APELIDO_DE_FORMA.get(nome)
        if alvo is None:
            for apelido, real in _APELIDO_DE_FORMA.items():
                if apelido in nome or nome in apelido:
                    alvo = real
                    break
        if alvo is None:
            continue
        x, y = _numero(f.get("x"), -1), _numero(f.get("y"), -1)
        l = _numero(f.get("l"), 0)
        a = _numero(f.get("a"), 0)
        if x < 0 or y < 0 or l <= 0 or a <= 0:
            continue
        x, y = min(max(x, 0.0), 0.99), min(max(y, 0.0), 0.99)
        l, a = min(l, 1.0 - x), min(a, 1.0 - y)
        if l < 0.01 or a < 0.01:
            continue
        formas.append({"forma": alvo, "x": x, "y": y, "l": l, "a": a, "cor": cor,
                       "preenche": str(preenche), "grossura": grossura})
    return {"nome": str(bruto.get("nome") or "").strip(), "formas": formas}


# ──────────────────────────────────────────────────── desenhar no Paint
def _desenhar_no_paint(plano: dict, hwnd: int, log, deve_parar,
                       esticar_folha: bool = True, limpar: bool = False) -> tuple:
    """Executa o plano. Devolve (quantas formas saíram, aviso)."""
    paint = PaintPorAcessibilidade(hwnd, log=log)
    if esticar_folha:
        paint.usar_folha_maxima()
    if limpar:
        paint.limpar_folha()
    tela = paint.retangulo_da_tela()
    if not tela:
        return 0, "não achei a área de desenho do Paint"
    esq, topo, dir_, base = tela
    # RESPIRO NA BORDA — não é frescura: a folha do Paint tem oito
    # ALÇAS de redimensionar em cima da borda. Um arrasto que começa
    # perto do canto pega a alça e encolhe a folha sem querer.
    marg = 10
    esq, topo = esq + marg, topo + marg
    dir_, base = dir_ - marg, base - marg
    larg, alt = max(1, dir_ - esq), max(1, base - topo)
    log(f"[desenhar] folha {larg}x{alt} em ({esq},{topo})")

    def px(fx, fy):
        return (int(esq + fx * larg), int(topo + fy * alt))

    feitas = 0
    fim = time.monotonic() + TETO_DE_TEMPO_S
    for forma in plano["formas"]:
        if deve_parar and deve_parar():
            paint.carimbar()
            return feitas, "parado pelo dono"
        if time.monotonic() > fim:
            paint.carimbar()
            log(f"[desenhar] estourei o tempo com {feitas} de {len(plano['formas'])}")
            return feitas, "faltou tempo"
        nome = forma["forma"]
        grossura = forma.get("grossura") or 5
        try:
            # A ORDEM DESTE BLOCO É O DESENHO INTEIRO: 1º carimbar a
            # forma anterior, 2º escolher a ferramenta, 3º só então
            # as cores. Trocar cor com uma forma ainda solta RECOLORE
            # a forma solta.
            paint.carimbar()
            if nome == "poligono" and len(forma["pontos"]) >= 3:
                nome_uia = _nome_de_botao_da_forma(paint, "poligono")
                if not nome_uia or not paint.ferramenta(nome_uia):
                    continue
                tem_dentro = bool(forma.get("preenche"))
                paint.cor_de_dentro(forma.get("preenche") or forma["cor"])
                paint.cor_do_contorno(forma["cor"])
                paint.preenchimento(tem_dentro)
                paint.grossura_da_forma(grossura)
                _poligono([px(x, y) for x, y in _menos_pontos(forma["pontos"])])
                paint._forma_solta = True
            elif nome in ("traco", "linha"):
                if not paint.ferramenta("Lápis"):
                    continue
                paint.cor(1, forma["cor"])          # o Lápis pinta com a Cor 1
                paint.grossura_do_lapis(max(2, min(20, grossura)))
                _tracar_pontos([px(x, y) for x, y in forma["pontos"]])
            else:
                # A FORMA VEM PRIMEIRO, e não por capricho: "Preenchimento
                # de forma" e "Tamanho" só ficam ativos DEPOIS que uma
                # forma está escolhida.
                nome_uia = _nome_de_botao_da_forma(paint, nome)
                if not nome_uia or not paint.ferramenta(nome_uia):
                    continue
                tem_dentro = bool(forma.get("preenche"))
                paint.cor_de_dentro(forma.get("preenche") or forma["cor"])
                paint.cor_do_contorno(forma["cor"])
                paint.preenchimento(tem_dentro)
                paint.grossura_da_forma(grossura)
                x1, y1 = px(forma["x"], forma["y"])
                x2, y2 = px(forma["x"] + forma["l"], forma["y"] + forma["a"])
                _arrastar(x1, y1, x2, y2)
                paint._forma_solta = True
            feitas += 1
        except Exception as exc:
            log(f"[desenhar] pulei {nome}: {type(exc).__name__} {str(exc)[:70]}")
    paint.carimbar()          # a última forma também precisa ser fixada
    return feitas, ""


# ─────────────────────────── Paint clássico (Windows 10): montar e colar
def _cor_rgb(nome: str) -> tuple:
    n = _sem_acento(nome)
    n = _APELIDO_DE_COR.get(n, n)
    if n in _PALETA_CONHECIDA:
        return _PALETA_CONHECIDA[n]
    achado = _hex_para_rgb(n)
    if achado:
        return achado
    return (0, 0, 0)


def _pontos_da_forma(nome: str, caixa) -> list:
    """Triângulo, losango, estrela... como polígono dentro da caixa."""
    x1, y1, x2, y2 = caixa
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    if nome == "triangulo":
        return [(cx, y1), (x2, y2), (x1, y2)]
    if nome == "triangulo retangulo":
        return [(x1, y1), (x2, y2), (x1, y2)]
    if nome == "losango":
        return [(cx, y1), (x2, cy), (cx, y2), (x1, cy)]
    if nome in ("pentagono", "hexagono"):
        n = 5 if nome == "pentagono" else 6
        return [(cx + w / 2 * math.sin(2 * math.pi * i / n),
                 cy - h / 2 * math.cos(2 * math.pi * i / n)) for i in range(n)]
    if nome.startswith("estrela"):
        pontas = 4 if "quatro" in nome else (6 if "seis" in nome else 5)
        saida = []
        for i in range(pontas * 2):
            raio = 1.0 if i % 2 == 0 else 0.42
            ang = math.pi * i / pontas - math.pi / 2
            saida.append((cx + w / 2 * raio * math.cos(ang),
                          cy + h / 2 * raio * math.sin(ang)))
        return saida
    return []


def _montar_imagem(plano: dict, larg: int, alt: int):
    """O mesmo plano, desenhado com o Pillow — para colar no Paint
    clássico (Windows 10), que não tem os botões do Paint novo."""
    from PIL import Image, ImageDraw  # noqa: PLC0415
    img = Image.new("RGB", (larg, alt), (255, 255, 255))
    d = ImageDraw.Draw(img)

    def cx(v):
        return int(v * larg)

    def cy(v):
        return int(v * alt)

    for f in plano["formas"]:
        cor = _cor_rgb(f["cor"])
        dentro = _cor_rgb(f["preenche"]) if f.get("preenche") else None
        larg_linha = max(1, int(f.get("grossura") or 5))
        nome = f["forma"]
        if nome in ("traco", "linha", "poligono"):
            pts = [(cx(x), cy(y)) for x, y in f["pontos"]]
            if nome == "poligono":
                d.polygon(pts, fill=dentro, outline=cor, width=larg_linha)
            else:
                d.line(pts, fill=cor, width=larg_linha, joint="curve")
            continue
        cxy = [cx(f["x"]), cy(f["y"]), cx(f["x"] + f["l"]), cy(f["y"] + f["a"])]
        if nome == "oval":
            d.ellipse(cxy, fill=dentro, outline=cor, width=larg_linha)
        elif nome == "retangulo":
            d.rectangle(cxy, fill=dentro, outline=cor, width=larg_linha)
        elif nome == "retangulo arredondado":
            d.rounded_rectangle(cxy, radius=max(4, (cxy[2] - cxy[0]) // 10),
                                fill=dentro, outline=cor, width=larg_linha)
        else:
            pts = _pontos_da_forma(nome, cxy)
            if pts:
                d.polygon(pts, fill=dentro, outline=cor, width=larg_linha)
            else:
                d.rectangle(cxy, fill=dentro, outline=cor, width=larg_linha)
    return img


def _copiar_imagem(img) -> bool:
    """Põe a imagem na área de transferência no formato DIB (BMP sem
    cabeçalho) que o Paint entende no Ctrl+V."""
    import io  # noqa: PLC0415
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "BMP")
        dados = buf.getvalue()[14:]
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32
        if not u.OpenClipboard(None):
            return False
        try:
            u.EmptyClipboard()
            bloco = k.GlobalAlloc(0x2000, len(dados))   # GMEM_MOVEABLE(2)|DDESHARE
            ponteiro = k.GlobalLock(bloco)
            ctypes.memmove(ponteiro, dados, len(dados))
            k.GlobalUnlock(bloco)
            u.SetClipboardData(8, bloco)                # CF_DIB
        finally:
            u.CloseClipboard()
        return True
    except Exception:
        return False


def _colar_no_paint_classico(plano: dict, hwnd: int, log) -> tuple:
    """Monta a imagem com o Pillow e cola com Ctrl+V — caminho para o
    Paint clássico do Windows 10, que não tem os botões do Paint novo."""
    try:
        rect = _RECT()
        ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
        larg = max(400, min(1600, rect.right - 80))
        alt = max(300, min(1200, rect.bottom - 220))
    except Exception:
        larg, alt = 900, 600
    img = _montar_imagem(plano, larg, alt)
    if not _copiar_imagem(img):
        return 0, "não consegui pôr a imagem na área de transferência"
    _focar(hwnd)
    time.sleep(0.4)
    ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)      # Ctrl
    _tecla(0x56)                                          # V
    ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
    time.sleep(1.2)
    _tecla(_VK_ESCAPE)          # solta a seleção flutuante, sem apagar nada
    log(f"[desenhar] colei uma imagem de {larg}x{alt}")
    return len(plano["formas"]), ""


# ═══════════════════════════ DESENHAR A PARTIR DE UMA FOTO ═══════════════
#
# "desenha essa foto": a foto vira desenho AQUI no computador, com o
# OpenCV — manchas de cor grandes primeiro, contorno por cima (a
# ordem de quem pinta de verdade: cor antes, traço depois, senão a
# cor cobriria o traço). Não passa pela rede e não gasta cota.
def _abrir_foto(caminho: str):
    """Lê a imagem mesmo com acento no caminho (o cv2.imread não lê)."""
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    dados = np.fromfile(caminho, dtype=np.uint8)
    return cv2.imdecode(dados, cv2.IMREAD_COLOR)


def _plano_da_foto(caminho: str, estilo: str = "colorido", log=None) -> dict:
    """A foto virada em plano de desenho: manchas de cor + contorno.

    `estilo`: "colorido" (manchas + contorno) ou "contorno" (só o
    traço preto, tipo esboço a lápis — mais rápido e melhor para
    rosto).
    """
    log = log or (lambda _m: None)
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    img = _abrir_foto(caminho)
    if img is None:
        return {"nome": "", "formas": []}
    alt0, larg0 = img.shape[:2]
    escala = 420.0 / max(alt0, larg0)
    if escala < 1.0:
        img = cv2.resize(img, (max(1, int(larg0 * escala)), max(1, int(alt0 * escala))),
                         interpolation=cv2.INTER_AREA)
    alt, larg = img.shape[:2]
    formas: list = []

    if estilo != "contorno":
        # 1) achatar a foto: o filtro bilateral apaga a textura e
        #    MANTÉM a borda — sem ele cada folha de árvore vira uma
        #    mancha e o desenho fica com centenas de peças.
        macio = cv2.bilateralFilter(img, 9, 90, 90)
        rgb = cv2.cvtColor(macio, cv2.COLOR_BGR2RGB).astype(np.float32)
        # 2) cada pixel vai para a cor mais parecida da paleta do Paint
        nomes = list(_PALETA_CONHECIDA)
        tabela = np.array([_PALETA_CONHECIDA[n] for n in nomes], dtype=np.float32)
        rm = (rgb[:, :, None, 0] + tabela[None, None, :, 0]) / 2.0
        d = rgb[:, :, None, :] - tabela[None, None, :, :]
        peso_r = 2 + rm / 256.0
        peso_b = 2 + (255 - rm) / 256.0
        dist = peso_r * d[..., 0] ** 2 + 4 * d[..., 1] ** 2 + peso_b * d[..., 2] ** 2
        indice = np.argmin(dist, axis=2).astype(np.int32)
        # 3) uma mancha por cor, da maior para a menor
        nucleo = np.ones((3, 3), np.uint8)
        minima = 0.004 * alt * larg          # menos de 0,4% da foto: é sujeira
        # A COR QUE DOMINA A FOTO VIRA O FUNDO, não uma mancha — numa
        # foto escura, o preto tomaria 70% da imagem e o "desenho"
        # sairia um retângulo preto com o contorno preto por cima.
        contagem = np.bincount(indice.ravel(), minlength=len(nomes))
        dominante = int(np.argmax(contagem))
        fundo = ""
        if contagem[dominante] > 0.42 * alt * larg:
            fundo = nomes[dominante]
            formas.append({"forma": "retangulo", "x": 0.0, "y": 0.0, "l": 1.0,
                           "a": 1.0, "cor": fundo, "preenche": fundo, "grossura": 3})
        achadas = []
        for i, nome in enumerate(nomes):
            if nome == fundo:
                continue
            mascara = (indice == i).astype(np.uint8)
            if mascara.sum() < minima:
                continue
            mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, nucleo, iterations=2)
            mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, nucleo, iterations=2)
            contornos, _h = cv2.findContours(mascara, cv2.RETR_EXTERNAL,
                                             cv2.CHAIN_APPROX_SIMPLE)
            for c in contornos:
                area = cv2.contourArea(c)
                if area < minima:
                    continue
                aprox = cv2.approxPolyDP(c, 0.008 * cv2.arcLength(c, True), True)
                if len(aprox) < 3:
                    continue
                achadas.append((area, nome, aprox[:40]))
        achadas.sort(key=lambda x: -x[0])
        for _area, nome, c in achadas[:20]:
            formas.append({
                "forma": "poligono",
                "pontos": [[float(px[0][0]) / larg, float(px[0][1]) / alt] for px in c],
                "cor": nome, "preenche": nome, "grossura": 3})
        log(f"[desenhar] {len(formas)} manchas de cor tiradas da foto")

    # 4) o contorno por cima — é ele que faz a foto ser reconhecida.
    # Preto em foto escura não aparece: o traço preto some dentro da
    # mancha preta, então a cor do traço vem do brilho médio da foto.
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cor_do_traco = "branco" if float(cinza.mean()) < 92 else "preto"
    cinza = cv2.GaussianBlur(cinza, (5, 5), 0)
    bordas = cv2.Canny(cinza, 60, 150)
    bordas = cv2.dilate(bordas, np.ones((2, 2), np.uint8), iterations=1)
    contornos, _h = cv2.findContours(bordas, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    riscos = []
    for c in contornos:
        if cv2.arcLength(c, False) < max(40, 0.08 * max(alt, larg)):
            continue
        aprox = cv2.approxPolyDP(c, 2.0, False)
        if len(aprox) < 2:
            continue
        riscos.append((cv2.arcLength(c, False), aprox[:60]))
    riscos.sort(key=lambda x: -x[0])
    teto = 14 if estilo != "contorno" else 26
    for _comp, c in riscos[:teto]:
        formas.append({
            "forma": "traco",
            "pontos": [[float(px[0][0]) / larg, float(px[0][1]) / alt] for px in c],
            "cor": cor_do_traco, "preenche": "", "grossura": 2})
    log(f"[desenhar] {len(formas)} peças no total (manchas + contorno)")
    return {"nome": "o desenho da sua foto", "formas": formas}


# ────────────────────────────────────────────────────────────── o trabalho
def _trabalho(pedido: str, foto: str, estilo: str, refazer: bool, critica: str,
             log, deve_parar, saida: dict) -> None:
    """Tudo o que mexe no Paint. Roda numa thread MTA — ver o motivo
    no comentário de `desenhar_na_tela`, mais abaixo."""
    ctypes.windll.ole32.CoInitializeEx(None, 0)          # 0 = MULTITHREADED

    if refazer and not pedido:
        pedido = ultimo_desenho()

    hwnd, erro = _abrir_paint(log)
    if erro:
        saida["texto"] = erro
        return
    _maximizar(hwnd)
    if not _focar(hwnd):
        log("[desenhar] a janela não veio para a frente; sigo assim mesmo")
    time.sleep(0.3)

    global _FREIO
    freio = _FreioEsc()
    freio.ligar()
    _FREIO = freio
    try:
        _desenhar_mesmo(pedido, foto, estilo, refazer, critica, log,
                        lambda: bool(freio.apertado) or bool(deve_parar and deve_parar()),
                        saida, hwnd)
    finally:
        _FREIO = None
        freio.parar()


def _desenhar_mesmo(pedido: str, foto: str, estilo: str, refazer: bool,
                    critica: str, log, deve_parar, saida: dict, hwnd: int) -> None:
    # ── o plano ────────────────────────────────────────────────────────
    t0 = time.monotonic()
    if foto:
        # A FOTO VIRA DESENHO AQUI NO COMPUTADOR, sem rede e sem cota.
        try:
            plano = _limpar_plano(_plano_da_foto(foto, estilo or "colorido", log))
        except Exception as exc:
            log(f"[desenhar] não consegui ler a foto: {type(exc).__name__} {str(exc)[:70]}")
            saida["texto"] = "Não consegui ler essa imagem para desenhar."
            return
    else:
        if not GEMINI_API_KEY:
            saida["texto"] = "GEMINI_API_KEY não encontrada — não tenho como pensar o desenho."
            return
        extra = _empurrao_de_variacao()
        if refazer:
            extra = ("\n\nO DONO VIU O SEU DESENHO ANTERIOR DISTO E NÃO GOSTOU"
                     + (f': "{critica}".' if critica else ".")
                     + " Faça OUTRO, bem melhor: mais peças, mais detalhe, "
                     "proporção certa e composição diferente da anterior. "
                     "Não repita o desenho de antes.")
        try:
            bruto = _pedir_plano_ao_gemini(pedido, extra)
        except Exception as exc:
            log(f"[desenhar] o Gemini falhou: {str(exc)[:90]}")
            bruto = {}
        plano = _limpar_plano(bruto)
    log(f"[desenhar] plano em {time.monotonic() - t0:.1f}s, {len(plano['formas'])} formas")

    if not plano["formas"]:
        saida["texto"] = ("Não consegui montar o desenho — não veio um plano que eu "
                          "entendesse. Tenta pedir de novo?")
        return
    global ULTIMO_PLANO, ULTIMO_PEDIDO, ULTIMO_EM
    ULTIMO_PLANO = plano
    cortadas = max(0, len(plano["formas"]) - TETO_DE_PECAS)
    if cortadas:
        plano["formas"] = plano["formas"][:TETO_DE_PECAS]
        log(f"[desenhar] o plano tinha {len(plano['formas']) + cortadas} peças; "
            f"desenho {TETO_DE_PECAS} e digo que deixei {cortadas} de fora")
    if pedido:
        ULTIMO_PEDIDO, ULTIMO_EM = pedido, time.monotonic()
    if deve_parar and deve_parar():
        saida["texto"] = "Parei antes de começar."
        return

    # ── desenhar ───────────────────────────────────────────────────────
    t0 = time.monotonic()
    modo = "a mao"
    try:
        paint = PaintPorAcessibilidade(hwnd, log=log)
        novo_paint = _e_paint_do_windows_11(paint)
    except Exception as exc:
        log(f"[desenhar] acessibilidade fora do ar: {str(exc)[:70]}")
        novo_paint = False
    if novo_paint:
        feitas, aviso = _desenhar_no_paint(
            plano, hwnd, log, deve_parar, esticar_folha=True, limpar=refazer)
    else:
        log("[desenhar] Paint clássico (Windows 10) — monto a imagem e colo")
        modo = "colado"
        feitas, aviso = _colar_no_paint_classico(plano, hwnd, log)
    log(f"[desenhar] {feitas} peças em {time.monotonic() - t0:.0f}s {aviso}")

    o_que = plano.get("nome") or pedido or "o desenho"
    if not feitas:
        saida["texto"] = f"Não consegui desenhar no Paint. {aviso}".strip()
        return
    if aviso == "parado pelo dono":
        saida["texto"] = (f"Parei como você pediu — {feitas} peças já estavam na "
                          "tela. O computador é seu de novo.")
        return
    faltou = ""
    se_faltaram = cortadas + max(0, len(plano["formas"]) - feitas)
    if aviso == "faltou tempo":
        faltou = (f" Parei em {feitas} peças para não passar de três minutos; "
                  f"ficaram {se_faltaram} detalhes de fora. Se quiser, eu completo.")
    elif se_faltaram:
        faltou = f" Deixei {se_faltaram} detalhes de fora para não demorar demais."
    if modo == "colado":
        saida["texto"] = f"Pronto, montei {o_que} e coloquei no Paint.{faltou}"
    else:
        saida["texto"] = f"Pronto, desenhei {o_que} no Paint, com {feitas} peças.{faltou}"


# ────────────────────────────────────────────────────────────── entrada
def desenhar_na_tela(pedido: str = "", foto: str = "", estilo: str = "",
                     refazer: bool = False, critica: str = "",
                     deve_parar=None) -> str:
    """Ferramenta: desenha no Paint o que foi pedido, sozinho.

    pedido  : o que desenhar ("uma casa com sol e uma árvore"). Pode
              ficar vazio se `foto` ou `refazer` estiverem preenchidos.
    foto    : caminho de um arquivo de imagem — se vier, a foto vira o
              desenho (via OpenCV), sem depender do Gemini.
    estilo  : só junto com `foto`: "colorido" (padrão) ou "contorno".
    refazer : refaz o último pedido (ver `ultimo_desenho`), com uma
              composição diferente — útil para "melhora esse desenho".
    critica : o que o dono não gostou no desenho anterior, se houver
              (só faz sentido junto com `refazer`).
    """
    pedido = str(pedido or "").strip()
    foto = str(foto or "").strip()

    tem_pedido = bool(pedido) or bool(foto)
    if refazer:
        tem_pedido = tem_pedido or bool(ultimo_desenho())
    if not tem_pedido:
        if refazer:
            return "Não lembro qual desenho você quer que eu melhore. Me diz o que desenhar?"
        return "Faltou dizer o que desenhar."

    # O COMTYPES TEM DE SER CARREGADO AQUI, ANTES DA THREAD. Ao ser
    # importado pela PRIMEIRA vez no processo, o comtypes chama
    # `CoInitializeEx` com a bandeira dele (STA). Dentro da thread nova,
    # que já é MTA, isso estouraria: "não é possível alterar o modo de
    # thread depois de o mesmo estar definido". Importando antes, lá
    # dentro o import já é só uma consulta ao cache.
    try:
        import comtypes.client  # noqa: F401,PLC0415
    except Exception as exc:
        return f"Falta uma peça do Windows para eu desenhar: {str(exc)[:70]}"

    # POR QUE UMA THREAD NOVA: a API de acessibilidade do Windows só
    # responde em thread MTA. A thread de onde isto é chamado
    # (o executor do asyncio) pode já estar em STA — e aí a PRIMEIRA
    # chamada de UIA trava para sempre, sem erro.
    saida: dict = {}
    t = threading.Thread(
        target=lambda: _trabalho(pedido, foto, estilo, refazer, critica, lambda _m: None,
                                deve_parar, saida),
        daemon=True)
    t.start()
    t.join(260)
    if t.is_alive():
        return "O desenho demorou demais e eu parei no meio."
    return saida.get("texto") or "Não consegui desenhar agora."
