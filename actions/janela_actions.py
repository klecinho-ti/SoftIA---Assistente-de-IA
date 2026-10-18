# ============================================================
# SOFTIA - FECHAR JANELAS PELO NOME
# ============================================================
#
# Portado do JARVIS-CyberBot (actions/janelas_windows.py) em
# 19/09/2026, a pedido do Klecio.
#
# Por que existe: o SOFTIA já sabe ABRIR aplicativos e pastas
# (actions/app_actions.py), mas não sabia FECHAR uma janela pelo
# nome enquanto ela não está em primeiro plano — só dava para
# fechar a aba/app ativo no momento (actions/media_actions.py).
# Este arquivo resolve isso enxergando as janelas de verdade pela
# API do Windows (user32, por ctypes — sem biblioteca nova),
# em vez de adivinhar por processo.
#
# Fechar aqui é educado: manda WM_CLOSE, o mesmo sinal que o botão
# X da janela manda. Uma janela com uma pergunta pendente na tela
# (\"deseja salvar?\") pode ignorar o pedido e continuar aberta —
# e por isso este código confere DEPOIS se ela realmente fechou,
# em vez de simplesmente supor que sim.
# ============================================================

import re
import time
import unicodedata


# Código do Windows para \"peça para esta janela se fechar\".
_WM_CLOSE = 0x0010

# Janelas que nunca devem ser fechadas por engano, mesmo que o nome
# falado bata por acaso. \"Program Manager\" é a própria área de
# trabalho — fechá-la derrubaria os ícones do usuário.
_TITULOS_INTOCAVEIS = (
    "program manager",
    "windows input experience",
    "microsoft text input application",
    "softia",
)

# Palavras que não contam na comparação do nome, porque são só
# enchimento (\"a pasta de downloads\" -> o que importa é \"downloads\").
_PALAVRAS_DE_ENCHIMENTO = {
    "pasta", "a", "o", "de", "do", "da", "minha", "meu", "as", "os", "e",
    "aba", "janela", "aplicativo", "programa",
}


# Remove acentos e deixa o texto em minúsculas, para comparar nomes
# ditos de formas diferentes como se fossem o mesmo.
def _normalizar(texto):
    texto = unicodedata.normalize(
        "NFD",
        str(texto or "").lower(),
    )

    texto = "".join(
        c for c in texto if unicodedata.category(c) != "Mn"
    )

    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", texto)).strip()


# Lista todas as janelas visíveis do Windows que têm título, usando
# a API nativa do sistema (EnumWindows), sem depender de nenhuma
# biblioteca externa.
def _listar_janelas_abertas():
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return []

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

            achadas.append({
                "hwnd": hwnd,
                "titulo": buffer_titulo.value,
            })

        except Exception:
            pass

        return True

    try:
        user32.EnumWindows(_visitar, 0)
    except Exception:
        return []

    return achadas


# Decide se o título de uma janela corresponde ao nome que o
# usuário falou, ignorando palavras de enchimento e pequenas
# diferenças (singular/plural, acento).
def _corresponde(titulo, nome):
    titulo_normalizado = _normalizar(titulo)
    nome_normalizado = _normalizar(nome)

    if not titulo_normalizado or not nome_normalizado:
        return False

    if titulo_normalizado in _TITULOS_INTOCAVEIS:
        return False

    palavras = [
        p for p in nome_normalizado.split()
        if p not in _PALAVRAS_DE_ENCHIMENTO
    ]

    if not palavras:
        return False

    if all(p in titulo_normalizado for p in palavras):
        return True

    for palavra in palavras:
        for pedaco in titulo_normalizado.split():
            if len(palavra) >= 4 and (
                pedaco.startswith(palavra) or palavra.startswith(pedaco)
            ):
                return True

    return False


# Fecha, de forma educada, as janelas cujo título corresponde ao
# nome falado pelo usuário. Devolve uma frase pronta para o SOFTIA
# responder, e nunca inventa que fechou algo que não conferiu.
#
# nome: como o usuário chamou a janela, aba ou aplicativo
#       (ex.: \"pasta de downloads\", \"bloco de notas\", \"calculadora\").
def fechar_janela(nome):
    if not nome or not str(nome).strip():
        return "Preciso saber o nome da janela ou aplicativo para fechar."

    try:
        import ctypes
        user32 = ctypes.windll.user32
    except Exception as erro:
        return f"Não consegui acessar as janelas do Windows: {erro}"

    todas = _listar_janelas_abertas()
    alvos = [j for j in todas if _corresponde(j["titulo"], nome)]

    if not alvos:
        return f"Não encontrei nenhuma janela aberta parecida com \"{nome}\"."

    for janela in alvos:
        try:
            user32.PostMessageW(janela["hwnd"], _WM_CLOSE, 0, 0)
        except Exception:
            pass

    # WM_CLOSE é um pedido, não uma ordem: dá até 1,5s para a janela
    # sumir de verdade antes de confirmar que fechou.
    prazo_final = time.time() + 1.5
    restantes = alvos

    while time.time() < prazo_final:
        time.sleep(0.1)

        abertas_agora = {
            j["hwnd"] for j in _listar_janelas_abertas()
        }

        restantes = [
            j for j in alvos if j["hwnd"] in abertas_agora
        ]

        if not restantes:
            break

    fechadas = len(alvos) - len(restantes)

    if fechadas == len(alvos):
        return f"Fechei \"{alvos[0]['titulo']}\", senhor."

    if fechadas > 0:
        return (
            f"Fechei {fechadas} de {len(alvos)} janelas parecidas com "
            f"\"{nome}\". Uma delas pode ter uma pergunta pendente na tela."
        )

    return (
        f"Encontrei \"{alvos[0]['titulo']}\", mas ela não fechou — "
        f"pode ter uma pergunta pendente esperando resposta."
    )
