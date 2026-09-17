# ============================================================
# SOFTIA VISION - CONTROLE DO MOUSE
# ============================================================
#
# Código original com comentários didáticos.
# O funcionamento e a lógica permanecem exatamente os mesmos.
# ============================================================

# ctypes permite acessar funções da API do Windows diretamente pelo Python.
import ctypes

# Contém estruturas prontas do Windows, como POINT.
import ctypes.wintypes

# Utilizado para pequenas pausas entre operações.
import time


# Carrega a biblioteca User32.dll, responsável pelas funções da interface
# gráfica do Windows, incluindo mouse, teclado e janelas.
_USER32 = ctypes.windll.user32

# Constantes utilizadas pela função mouse_event().
# Cada valor representa uma ação diferente do mouse.

# Pressionar botão esquerdo.
MOUSEEVENTF_LEFTDOWN = 0x0002

# Soltar botão esquerdo.
MOUSEEVENTF_LEFTUP = 0x0004

# Pressionar botão direito.
MOUSEEVENTF_RIGHTDOWN = 0x0008

# Soltar botão direito.
MOUSEEVENTF_RIGHTUP = 0x0010

# Evento da roda do mouse.
MOUSEEVENTF_WHEEL = 0x0800

# Um "clique" da roda corresponde a 120 unidades na API do Windows.
WHEEL_DELTA = 120

# Índices do GetSystemMetrics que descrevem a área virtual do Windows,
# ou seja, o retângulo que engloba TODOS os monitores conectados,
# não apenas o monitor principal.
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


# Evita diferenças de coordenadas causadas pela escala (DPI)
# utilizada pelo Windows.
try:
    _USER32.SetProcessDPIAware()
except Exception:
    # Caso a função não exista ou ocorra algum erro,
    # o código continua normalmente.
    pass


def _limitar_quantidade(quantidade):
    """
    Garante que a quantidade utilizada na rolagem
    permaneça entre 1 e 10 passos.
    """

    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError):
        # Valor padrão caso o usuário informe algo inválido.
        quantidade = 3

    # Limita o valor mínimo a 1 e o máximo a 10.
    return max(1, min(10, quantidade))


def _evento_mouse(flags, dados=0):
    """
    Envia um evento diretamente para a API do Windows.

    flags informa qual ação será realizada.
    dados é usado principalmente para a roda do mouse.
    """

    _USER32.mouse_event(
        flags,
        0,
        0,
        dados,
        0,
    )


def rolar_pagina(direcao, quantidade=3):
    """
    Realiza a rolagem da página para cima ou para baixo.
    """

    # Padroniza o texto recebido.
    direcao = str(direcao).strip().lower()

    # Garante que a quantidade esteja dentro do limite permitido.
    quantidade = _limitar_quantidade(quantidade)

    # Rolagem para cima.
    if direcao in ("cima", "para cima", "subir"):
        _evento_mouse(
            MOUSEEVENTF_WHEEL,
            WHEEL_DELTA * quantidade,
        )
        return f"Rolei a página para cima em {quantidade} passos."

    # Rolagem para baixo.
    if direcao in ("baixo", "para baixo", "descer"):
        _evento_mouse(
            MOUSEEVENTF_WHEEL,
            -WHEEL_DELTA * quantidade,
        )
        return f"Rolei a página para baixo em {quantidade} passos."

    return "Direção inválida. Use cima ou baixo."


def clicar_mouse():
    """
    Executa um clique simples utilizando a posição
    atual do cursor.
    """

    # Pressiona o botão esquerdo.
    _evento_mouse(MOUSEEVENTF_LEFTDOWN)

    # Solta o botão esquerdo.
    _evento_mouse(MOUSEEVENTF_LEFTUP)

    return "Clique executado na posição atual do mouse."


def duplo_clique_mouse():
    """
    Executa dois cliques consecutivos.
    """

    clicar_mouse()

    # Pequena pausa para o Windows reconhecer
    # corretamente um clique duplo.
    time.sleep(0.12)

    clicar_mouse()

    return "Clique duplo executado na posição atual do mouse."


def clique_direito_mouse():
    """
    Executa um clique com o botão direito.
    """

    _evento_mouse(MOUSEEVENTF_RIGHTDOWN)
    _evento_mouse(MOUSEEVENTF_RIGHTUP)

    return "Clique com o botão direito executado na posição atual do mouse."


def mover_e_clicar(x, y, duracao=0.35):
    """
    Move suavemente até uma coordenada absoluta da tela
    e realiza um clique simples.
    """

    # Converte os parâmetros para seus tipos corretos.
    try:
        x = int(x)
        y = int(y)
        duracao = float(duracao)

    except (TypeError, ValueError):
        return "Coordenadas inválidas. Nenhum clique foi executado."

    # Obtém os limites da área virtual, cobrindo todos os monitores
    # conectados (e não somente o monitor principal).
    virtual_esquerda = _USER32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    virtual_topo = _USER32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    virtual_largura = _USER32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    virtual_altura = _USER32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

    # Verifica se o ponto informado existe dentro de algum monitor.
    if not (
        virtual_esquerda <= x < virtual_esquerda + virtual_largura
        and virtual_topo <= y < virtual_topo + virtual_altura
    ):
        return "Coordenadas fora da tela. Nenhum clique foi executado."

    # Estrutura POINT utilizada pela API do Windows.
    ponto = ctypes.wintypes.POINT()

    # Descobre a posição atual do cursor.
    _USER32.GetCursorPos(ctypes.byref(ponto))

    inicio_x = ponto.x
    inicio_y = ponto.y

    # Calcula quantos pequenos movimentos serão feitos.
    # Quanto maior a duração, mais suave será a animação.
    passos = max(1, int(max(0.05, min(1.0, duracao)) * 60))

    # Move o cursor gradualmente até o destino.
    for passo in range(1, passos + 1):

        proporcao = passo / passos

        atual_x = round(
            inicio_x + (x - inicio_x) * proporcao
        )

        atual_y = round(
            inicio_y + (y - inicio_y) * proporcao
        )

        # Move o cursor.
        _USER32.SetCursorPos(atual_x, atual_y)

        # Pequena pausa entre cada movimento.
        time.sleep(max(0.001, duracao / passos))

    # Ao chegar ao destino, realiza o clique.
    clicar_mouse()

    return f"Clique visual executado em x={x}, y={y}."