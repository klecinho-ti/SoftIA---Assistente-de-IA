# ============================================================
# SOFTIA VISION - ENVIO DE MENSAGEM NO WHATSAPP
# ============================================================
#
# Este módulo orquestra o envio de uma mensagem de texto pelo
# WhatsApp Desktop, combinando recursos que já existem no SOFTIA:
#
# 1. abrir_aplicativo()          -> abre/foca o WhatsApp Desktop
# 2. localizar_elemento_na_tela() -> encontra campos e contatos na tela
# 3. mover_e_clicar()            -> clica nos elementos encontrados
# 4. escrever_no_campo_ativo()   -> digita texto via área de transferência
#
# Cada etapa depende do resultado visual da etapa anterior, por
# isso qualquer falha no meio do caminho interrompe a ação e
# devolve uma mensagem explicando em qual passo parou.
# ============================================================

import ctypes
import time

from actions.app_actions import abrir_aplicativo
from actions.mouse_actions import mover_e_clicar
from actions.text_actions import escrever_no_campo_ativo
from vision.click_locator import localizar_elemento_na_tela

_USER32 = ctypes.windll.user32

# Tecla Enter, usada para confirmar o envio da mensagem.
_VK_RETURN = 0x0D
_KEYEVENTF_KEYUP = 0x0002


def _pressionar_enter():
    """
    Simula o pressionamento da tecla Enter,
    usada para enviar a mensagem digitada.
    """

    _USER32.keybd_event(_VK_RETURN, 0, 0, 0)
    _USER32.keybd_event(_VK_RETURN, 0, _KEYEVENTF_KEYUP, 0)


def _localizar_e_clicar(descricao_alvo, etapa):
    """
    Localiza um elemento na tela pela descrição e clica nele.

    Retorna None em caso de sucesso, ou uma mensagem de erro
    pronta para ser devolvida ao usuário quando o elemento não
    é encontrado com confiança suficiente.
    """

    localizacao = localizar_elemento_na_tela(descricao_alvo)

    if not localizacao.get("sucesso"):
        return (
            f"Não consegui {etapa}. "
            f"{localizacao.get('mensagem', '')} "
            "Nenhuma mensagem foi enviada."
        ).strip()

    resultado_clique = mover_e_clicar(
        localizacao["x"],
        localizacao["y"],
    )

    if "Coordenadas" in resultado_clique or "inválidas" in resultado_clique:
        return (
            f"Não consegui {etapa} ({resultado_clique}). "
            "Nenhuma mensagem foi enviada."
        )

    return None


def enviar_mensagem_whatsapp(contato, mensagem):
    """
    Abre o WhatsApp Desktop, localiza a conversa pelo nome do
    contato ou grupo, digita a mensagem e envia.

    Requer que o WhatsApp Desktop esteja instalado no Windows.
    Não oferece envio de áudio: essa automação sabe apenas
    clicar e digitar, e enviar áudio exigiria segurar o botão
    de gravação, algo que o controle de mouse do SOFTIA ainda
    não faz.
    """

    contato = str(contato or "").strip()
    mensagem = str(mensagem or "").strip()

    if not contato:
        return "Informe para quem devo enviar a mensagem no WhatsApp."

    if not mensagem:
        return "Informe o que devo escrever na mensagem."

    # Abre ou foca o WhatsApp Desktop.
    resultado_abertura = abrir_aplicativo("WhatsApp")

    if "não" in resultado_abertura.lower() and "encontr" in resultado_abertura.lower():
        return (
            "Não encontrei o WhatsApp Desktop instalado neste computador. "
            "Instale o aplicativo oficial do WhatsApp para Windows e tente novamente."
        )

    # Dá tempo da janela do WhatsApp abrir ou ganhar foco.
    time.sleep(1.5)

    # Localiza e clica no campo de busca de conversas.
    erro = _localizar_e_clicar(
        "campo de pesquisa de conversas do WhatsApp, geralmente "
        "identificado por um ícone de lupa no topo da lista de conversas",
        "encontrar o campo de pesquisa do WhatsApp",
    )
    if erro:
        return erro

    # Digita o nome do contato ou grupo na busca.
    escrever_no_campo_ativo(contato)

    # Aguarda o WhatsApp filtrar os resultados da pesquisa.
    time.sleep(1.2)

    # Localiza e clica no primeiro resultado da busca.
    erro = _localizar_e_clicar(
        f"primeiro contato ou grupo da lista de resultados da pesquisa, "
        f"correspondente a '{contato}'",
        f"encontrar a conversa de '{contato}'",
    )
    if erro:
        return erro

    # Aguarda a conversa abrir completamente.
    time.sleep(1.0)

    # Localiza e clica no campo de digitar mensagem.
    erro = _localizar_e_clicar(
        "campo de digitar mensagem do WhatsApp, na parte inferior "
        "da conversa aberta, ao lado do ícone de emoji e do clipe de anexo",
        "encontrar o campo de digitar mensagem",
    )
    if erro:
        return erro

    # Digita a mensagem.
    escrever_no_campo_ativo(mensagem)

    # Pequena pausa para o texto ser colado antes do envio.
    time.sleep(0.3)

    # Envia a mensagem.
    _pressionar_enter()

    return f"Mensagem enviada para {contato} no WhatsApp."
