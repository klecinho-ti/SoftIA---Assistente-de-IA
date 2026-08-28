# ============================================================
# SOFTIA VISION - ESCRITA NO CAMPO ATIVO DO WINDOWS
# ============================================================
#
# Este módulo permite que o SOFTIA insira um texto exatamente
# no campo que estiver ativo no Windows.
#
# A escrita é feita em duas etapas:
# 1. o texto é colocado na área de transferência do Windows;
# 2. o atalho Ctrl + V é enviado para o campo ativo.
#
# Essa estratégia preserva acentos, cedilha, pontuação e textos
# maiores com mais confiabilidade do que simular tecla por tecla.
# ============================================================

import ctypes
import time
from ctypes import wintypes


# Biblioteca da interface do Windows.
_USER32 = ctypes.windll.user32

# Biblioteca de gerenciamento de memória do Windows.
_KERNEL32 = ctypes.windll.kernel32

# Formato Unicode usado pela área de transferência.
_CF_UNICODETEXT = 13

# Memória compartilhada e movimentável exigida pelo Clipboard.
_GMEM_MOVEABLE = 0x0002

# Códigos das teclas Ctrl e V.
_VK_CONTROL = 0x11
_VK_V = 0x56

# Indica que uma tecla foi solta.
_KEYEVENTF_KEYUP = 0x0002

# Limite de segurança para evitar colagens enormes por engano.
_MAXIMO_CARACTERES = 10000


# Define os tipos usados pelas funções nativas do Windows.
_KERNEL32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_KERNEL32.GlobalAlloc.restype = wintypes.HGLOBAL

_KERNEL32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_KERNEL32.GlobalLock.restype = wintypes.LPVOID

_KERNEL32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
_KERNEL32.GlobalUnlock.restype = wintypes.BOOL

_KERNEL32.GlobalFree.argtypes = [wintypes.HGLOBAL]
_KERNEL32.GlobalFree.restype = wintypes.HGLOBAL

_USER32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
_USER32.SetClipboardData.restype = wintypes.HANDLE


# Coloca um texto Unicode na área de transferência do Windows.
def _copiar_para_area_transferencia(texto):
    """
    Copia o texto para o Clipboard usando a API nativa do Windows.
    """

    # O Clipboard pode estar temporariamente ocupado por outro programa.
    # Fazemos algumas tentativas curtas antes de considerar falha.
    abriu = False

    for _ in range(10):
        if _USER32.OpenClipboard(None):
            abriu = True
            break

        time.sleep(0.05)

    if not abriu:
        raise RuntimeError(
            "Não foi possível acessar a área de transferência do Windows."
        )

    memoria = None
    transferida = False

    try:
        # Limpa o conteúdo anterior do Clipboard.
        if not _USER32.EmptyClipboard():
            raise RuntimeError(
                "Não foi possível limpar a área de transferência do Windows."
            )

        # Acrescenta o caractere nulo exigido por CF_UNICODETEXT.
        texto_completo = texto + "\0"

        # Calcula o espaço necessário em bytes para caracteres Unicode.
        tamanho = len(texto_completo) * ctypes.sizeof(ctypes.c_wchar)

        # Reserva uma área de memória compartilhável.
        memoria = _KERNEL32.GlobalAlloc(
            _GMEM_MOVEABLE,
            tamanho,
        )

        if not memoria:
            raise MemoryError(
                "Não foi possível reservar memória para o texto."
            )

        # Bloqueia a memória para obter um ponteiro gravável.
        ponteiro = _KERNEL32.GlobalLock(memoria)

        if not ponteiro:
            raise MemoryError(
                "Não foi possível acessar a memória reservada."
            )

        try:
            # Copia o texto Unicode para a memória reservada.
            ctypes.memmove(
                ponteiro,
                ctypes.create_unicode_buffer(texto_completo),
                tamanho,
            )

        finally:
            _KERNEL32.GlobalUnlock(memoria)

        # Entrega a memória ao Clipboard.
        # Depois desta chamada bem-sucedida, o Windows passa a ser
        # responsável por liberar essa memória.
        if not _USER32.SetClipboardData(
            _CF_UNICODETEXT,
            memoria,
        ):
            raise RuntimeError(
                "Não foi possível copiar o texto para a área de transferência."
            )

        transferida = True

    finally:
        _USER32.CloseClipboard()

        # Só libera manualmente quando a memória não foi entregue ao Windows.
        if memoria and not transferida:
            _KERNEL32.GlobalFree(memoria)


# Envia o atalho Ctrl + V para a janela ativa.
def _colar_no_campo_ativo():
    """
    Simula Ctrl + V usando a API nativa do Windows.
    """

    # Pressiona Ctrl.
    _USER32.keybd_event(
        _VK_CONTROL,
        0,
        0,
        0,
    )

    # Pressiona V.
    _USER32.keybd_event(
        _VK_V,
        0,
        0,
        0,
    )

    # Solta V.
    _USER32.keybd_event(
        _VK_V,
        0,
        _KEYEVENTF_KEYUP,
        0,
    )

    # Solta Ctrl.
    _USER32.keybd_event(
        _VK_CONTROL,
        0,
        _KEYEVENTF_KEYUP,
        0,
    )


# Função pública chamada pelo live_client.py.
def escrever_no_campo_ativo(texto):
    """
    Cola um texto no campo que estiver ativo no Windows.

    O usuário precisa deixar o cursor piscando no local desejado
    antes de dar o comando de voz ao SOFTIA.
    """

    # Garante que o valor recebido seja texto.
    texto = str(texto or "")

    # Bloqueia uma chamada sem conteúdo útil.
    if not texto.strip():
        return "Nenhum texto foi informado. Nada foi escrito."

    # Impede textos exageradamente grandes por segurança.
    if len(texto) > _MAXIMO_CARACTERES:
        return (
            "O texto ultrapassa o limite de "
            f"{_MAXIMO_CARACTERES} caracteres. Nada foi escrito."
        )

    try:
        # Copia preservando acentos e quebras de linha.
        _copiar_para_area_transferencia(texto)

        # Pequena pausa para o Windows concluir a atualização do Clipboard.
        time.sleep(0.12)

        # Cola no campo atualmente selecionado.
        _colar_no_campo_ativo()

        return "Texto inserido no campo ativo com sucesso."

    except Exception as erro:
        return f"Não foi possível inserir o texto: {erro}"