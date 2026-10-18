# ============================================================
# SOFTIA - DIGITAR AO VIVO NA JANELA ABERTA
# ============================================================
#
# Portado do JARVIS-CyberBot (actions/digitar_na_tela.py) em
# 19/09/2026, a pedido do Klecio.
#
# Diferente do `escrever_no_campo_ativo` (text_actions.py), que
# cola o texto de uma vez via área de transferência, esta função
# digita CARACTERE POR CARACTERE, com a mesma técnica do original:
# SendInput com KEYEVENTF_UNICODE. É o que faz o usuário VER o
# texto nascendo na tela, como se estivesse sendo escrito ao vivo
# — pedido explícito de quem usa: "quero ver ele escrevendo, não
# só o arquivo pronto".
#
# Não usa pywin32 (win32gui/win32con), que o SoftIA não tem como
# dependência — a busca e o foco de janela aqui são feitos com
# ctypes puro (user32), do mesmo jeito que o resto do projeto
# (ver actions/janela_actions.py).
#
# Diferente do JARVIS original, aqui o CONTEÚDO já chega pronto:
# quem escreve o texto é a própria Gemini Live (o parâmetro
# `conteudo` da ferramenta), então não existe um segundo cérebro
# separado para gerar o texto antes de digitar.
# ============================================================

import ctypes
import re
import time
from ctypes import wintypes


# ---------------------------------------------------------------
# SendInput: digita caractere por caractere, sem depender do
# layout do teclado (funciona com acento e símbolo em qualquer
# teclado instalado).
# ---------------------------------------------------------------

_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_VK_RETURN = 0x0D
_VK_TAB = 0x09
_VK_MENU = 0x12
_VK_ESCAPE = 0x1B

_ULONG_PTR = (
    ctypes.c_ulonglong
    if ctypes.sizeof(ctypes.c_void_p) == 8
    else ctypes.c_ulong
)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", _ULONG_PTR),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("ki", _KEYBDINPUT),
        ("padding", ctypes.c_ubyte * 32),
    ]


class _INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUTUNION),
    ]


def _enviar(entradas):
    array_entradas = (_INPUT * len(entradas))(*entradas)

    ctypes.windll.user32.SendInput(
        len(entradas),
        array_entradas,
        ctypes.sizeof(_INPUT),
    )


def _tecla(vk):
    baixo = _INPUT(
        type=_INPUT_KEYBOARD,
        u=_INPUTUNION(ki=_KEYBDINPUT(wVk=vk)),
    )

    cima = _INPUT(
        type=_INPUT_KEYBOARD,
        u=_INPUTUNION(ki=_KEYBDINPUT(wVk=vk, dwFlags=_KEYEVENTF_KEYUP)),
    )

    _enviar([baixo, cima])


def _caractere(ch):
    # Um caractere pode ocupar duas unidades UTF-16 (emoji); cada
    # uma vai como um evento unicode próprio, e o Windows junta.
    bruto = ch.encode("utf-16-le")

    for i in range(0, len(bruto), 2):
        codigo = int.from_bytes(bruto[i:i + 2], "little")

        baixo = _INPUT(
            type=_INPUT_KEYBOARD,
            u=_INPUTUNION(ki=_KEYBDINPUT(
                wScan=codigo,
                dwFlags=_KEYEVENTF_UNICODE,
            )),
        )

        cima = _INPUT(
            type=_INPUT_KEYBOARD,
            u=_INPUTUNION(ki=_KEYBDINPUT(
                wScan=codigo,
                dwFlags=_KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP,
            )),
        )

        _enviar([baixo, cima])


# Digita o texto na janela em foco, caractere por caractere.
# Devolve quantos caracteres saíram.
def _digitar_texto(texto, intervalo=0.012, pausa_linha=0.12):
    n = 0

    texto_normalizado = (
        str(texto or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    for ch in texto_normalizado:
        if ch == "\n":
            _tecla(_VK_RETURN)
            time.sleep(pausa_linha)
        elif ch == "\t":
            _tecla(_VK_TAB)
        else:
            _caractere(ch)
            time.sleep(intervalo)

        n += 1

    return n


# ---------------------------------------------------------------
# Encontrar e focar a janela pedida, em ctypes puro.
# ---------------------------------------------------------------

_JANELAS_CONHECIDAS = {
    "bloco de notas": ("bloco de notas", "notepad"),
    "notepad": ("bloco de notas", "notepad"),
    "word": ("word",),
    "wordpad": ("wordpad",),
    "vscode": ("visual studio code",),
    "visual studio code": ("visual studio code",),
    "excel": ("excel",),
    "navegador": ("chrome", "edge", "firefox"),
    "chrome": ("chrome",),
    "edge": ("edge",),
}


def _achar_janela(termos):
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

            buffer_titulo = ctypes.create_unicode_buffer(tamanho + 1)
            user32.GetWindowTextW(hwnd, buffer_titulo, tamanho + 1)

            titulo_baixo = buffer_titulo.value.lower()
            if any(termo in titulo_baixo for termo in termos):
                achadas.append(hwnd)

        except Exception:
            pass

        return True

    try:
        user32.EnumWindows(_visitar, 0)
    except Exception:
        return 0

    return achadas[0] if achadas else 0


def _focar(hwnd):
    user32 = ctypes.windll.user32
    _SW_RESTORE = 9

    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, _SW_RESTORE)

        if user32.GetForegroundWindow() == hwnd:
            return True

        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)

        if user32.GetForegroundWindow() == hwnd:
            return True

        # SÓ SE O WINDOWS RECUSAR: soltar Alt libera o
        # SetForegroundWindow, mas também abre o modo de menu do
        # programa — por isso o Esc logo depois, para fechar o
        # menu sem efeito sobre o texto.
        user32.keybd_event(_VK_MENU, 0, 0, 0)
        user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)

        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        _tecla(_VK_ESCAPE)
        time.sleep(0.15)

        return user32.GetForegroundWindow() == hwnd

    except Exception:
        return False


# Põe a janela pedida na frente; abre o Bloco de Notas se for ele
# e ainda não estiver aberto. Devolve uma mensagem de erro, ou
# string vazia quando deu certo (ou quando não foi pedida janela
# nenhuma, e o texto vai para onde o cursor já estiver).
def _preparar_janela(nome):
    chave = (nome or "").strip().lower()
    termos = _JANELAS_CONHECIDAS.get(chave) or ((chave,) if chave else ())

    if not termos:
        return ""

    hwnd = _achar_janela(termos)

    if not hwnd and chave in ("bloco de notas", "notepad"):
        try:
            import os
            os.startfile("notepad.exe")
        except Exception:
            return "Não consegui abrir o Bloco de Notas."

        for _ in range(40):
            time.sleep(0.15)
            hwnd = _achar_janela(termos)
            if hwnd:
                break

        # Janela recém-criada engole as primeiras teclas mesmo já
        # em primeiro plano — um respiro evita perder caracteres.
        time.sleep(1.5)

    if not hwnd:
        return f"Não achei a janela {nome} aberta."

    user32 = ctypes.windll.user32
    _focar(hwnd)

    for _ in range(20):
        if user32.GetForegroundWindow() == hwnd:
            break
        time.sleep(0.1)
        _focar(hwnd)

    time.sleep(0.4)
    return ""


def _sem_cerca(texto):
    texto_str = str(texto or "").strip()

    correspondencia = re.search(
        r"```[a-zA-Z0-9_+-]*\n(.*?)```",
        texto_str,
        re.S,
    )

    if correspondencia:
        texto_str = correspondencia.group(1)

    return texto_str.strip("\n") + "\n"


# Guarda o último texto digitado, para um pedido futuro do tipo
# "salva esse bloco de notas" conseguir o conteúdo mesmo sem ele
# estar na conversa.
ULTIMO_TEXTO = ""


# Digita um texto ao vivo na janela pedida (ou onde o cursor já
# estiver, se nenhuma janela for indicada).
#
# conteudo: o texto pronto a digitar, já escrito pela Gemini.
# janela  : nome da janela onde digitar (bloco de notas, word,
#           vscode...). Vazio = digita onde o cursor já estiver.
def digitar_ao_vivo(conteudo, janela=""):
    if not conteudo or not str(conteudo).strip():
        return "Faltou o texto para digitar."

    texto_limpo = _sem_cerca(conteudo)

    global ULTIMO_TEXTO
    ULTIMO_TEXTO = texto_limpo

    erro = _preparar_janela(janela)
    if erro:
        return erro

    # Teto de tamanho: 12 mil caracteres são ~3 minutos digitando,
    # e termina com uma quebra de linha, como todo arquivo de texto.
    texto_final = texto_limpo[:12000].strip("\r\n") + "\n"

    n = _digitar_texto(texto_final)
    linhas = texto_final[:n].count("\n")
    onde = f" no {janela}" if janela else ""

    return f"Pronto, digitei {linhas} linhas{onde}."
