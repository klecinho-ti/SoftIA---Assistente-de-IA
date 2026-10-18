# ============================================================
# SOFTIA - CONTROLE DE MÍDIA (VÍDEO, MÚSICA, VOLUME)
# ============================================================
#
# Criado em 19/09/2026 a pedido do Klecio: pausar/continuar vídeo,
# pular faixa, subir/baixar volume e fechar a aba ou o aplicativo
# atual — tudo por teclas de mídia nativas do Windows, do mesmo
# jeito que `text_actions.py` já usa para colar texto (keybd_event
# via ctypes, sem biblioteca nova).
#
# As teclas de mídia (play/pause, próxima faixa, volume) funcionam
# em qualquer app que respeite os atalhos do sistema — YouTube no
# navegador, Spotify, players locais — porque o Windows entrega
# esses sinais ao aplicativo em primeiro plano ou ao player ativo,
# não a um app específico.
# ============================================================

import ctypes
import time


# Biblioteca da interface do Windows, mesma usada em text_actions.py.
_USER32 = ctypes.windll.user32

# Indica que uma tecla foi solta.
_KEYEVENTF_KEYUP = 0x0002

# Códigos das teclas de mídia do teclado virtual do Windows.
_VK_MEDIA_NEXT_TRACK = 0xB0
_VK_MEDIA_PLAY_PAUSE = 0xB3
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF
_VK_CONTROL = 0x11
_VK_W = 0x57


# Pressiona e solta uma tecla virtual do Windows.
def _tocar_tecla(codigo_tecla):
    _USER32.keybd_event(
        codigo_tecla,
        0,
        0,
        0,
    )

    _USER32.keybd_event(
        codigo_tecla,
        0,
        _KEYEVENTF_KEYUP,
        0,
    )


# Alterna entre pausar e continuar o vídeo ou música em reprodução.
def pausar_ou_continuar_video():
    try:
        _tocar_tecla(_VK_MEDIA_PLAY_PAUSE)
    except Exception as erro:
        return f"Não consegui pausar ou continuar a reprodução: {erro}"

    return "Pronto."


# Avança para a próxima faixa ou vídeo, quando o player permite.
def proxima_faixa():
    try:
        _tocar_tecla(_VK_MEDIA_NEXT_TRACK)
    except Exception as erro:
        return f"Não consegui avançar para a próxima faixa: {erro}"

    return "Pronto, avancei para a próxima."


# Aumenta o volume do sistema em pequenos passos.
# quantidade: quantas vezes apertar a tecla de aumentar volume.
def aumentar_volume(quantidade=3):
    try:
        quantidade = max(1, min(int(quantidade), 20))
    except (TypeError, ValueError):
        quantidade = 3

    try:
        for _ in range(quantidade):
            _tocar_tecla(_VK_VOLUME_UP)
            # Pequena pausa entre toques para o Windows registrar
            # cada aumento separadamente.
            time.sleep(0.05)
    except Exception as erro:
        return f"Não consegui aumentar o volume: {erro}"

    return "Volume aumentado."


# Diminui o volume do sistema em pequenos passos.
# quantidade: quantas vezes apertar a tecla de diminuir volume.
def diminuir_volume(quantidade=3):
    try:
        quantidade = max(1, min(int(quantidade), 20))
    except (TypeError, ValueError):
        quantidade = 3

    try:
        for _ in range(quantidade):
            _tocar_tecla(_VK_VOLUME_DOWN)
            time.sleep(0.05)
    except Exception as erro:
        return f"Não consegui diminuir o volume: {erro}"

    return "Volume diminuído."


# Fecha a aba ativa do navegador ou a janela/documento ativo do
# aplicativo em primeiro plano, enviando Ctrl + W — o mesmo atalho
# que o próprio usuário usaria com o teclado.
def fechar_aba_ou_aplicativo():
    try:
        _USER32.keybd_event(
            _VK_CONTROL,
            0,
            0,
            0,
        )

        _USER32.keybd_event(
            _VK_W,
            0,
            0,
            0,
        )

        _USER32.keybd_event(
            _VK_W,
            0,
            _KEYEVENTF_KEYUP,
            0,
        )

        _USER32.keybd_event(
            _VK_CONTROL,
            0,
            _KEYEVENTF_KEYUP,
            0,
        )

    except Exception as erro:
        return f"Não consegui fechar a aba ou aplicativo: {erro}"

    return "Fechado."
