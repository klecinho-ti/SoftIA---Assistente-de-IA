# Ativar o ambiente virtual:
# .\venv\Scripts\Activate.ps1

# [Klecio] os é usado para disponibilizar a chave de API
# [Klecio] informada pelo usuário para o restante do programa.
import os

# [Klecio] socket é usado logo abaixo para corrigir um problema de rede
# [Klecio] antes de qualquer conexão do SOFTIA ser aberta.
import socket

# [Klecio] sys fornece acesso aos argumentos da linha de comando
# [Klecio] e permite finalizar corretamente a aplicação.
import sys

# [Klecio] Em redes com IPv6 mal configurado (comum em alguns roteadores
# [Klecio] e provedores de internet), o Windows tenta primeiro os
# [Klecio] endereços IPv6 do Gemini, que ficam travados até estourar o
# [Klecio] tempo limite, e só depois caem para o IPv4 que realmente
# [Klecio] funciona. Isso faz a conexão expirar ("timed out during
# [Klecio] opening handshake") antes de chegar a tentar o IPv4.
# [Klecio] Por isso, forçamos aqui que toda resolução de nome no SOFTIA
# [Klecio] use somente endereços IPv4, eliminando essa demora.
_resolver_dns_original = socket.getaddrinfo


def _resolver_dns_somente_ipv4(
    host,
    port,
    family=0,
    type=0,
    proto=0,
    flags=0,
):
    return _resolver_dns_original(
        host,
        port,
        socket.AF_INET,
        type,
        proto,
        flags,
    )


socket.getaddrinfo = _resolver_dns_somente_ipv4

# [Klecio] qInstallMessageHandler permite interceptar mensagens internas do Qt.
# [Klecio] Neste projeto ele é usado para ocultar apenas um aviso conhecido de DPI.
from PySide6.QtCore import qInstallMessageHandler

# [Klecio] QApplication é o núcleo de qualquer aplicação Qt.
# [Klecio] Ela controla o loop de eventos da interface.
from PySide6.QtWidgets import QApplication

# [Klecio] Funções que verificam se já existe uma chave de API
# [Klecio] configurada neste computador e que salvam uma nova chave
# [Klecio] informada pelo usuário na primeira execução.
from core.api_key_manager import garantir_chave_api, salvar_chave


# [Klecio] Esta função recebe todas as mensagens emitidas pelo Qt.
# [Klecio] O objetivo é esconder apenas um aviso específico,
# [Klecio] mantendo todos os demais avisos e erros visíveis.
def filtro_mensagens_qt(
    tipo,
    contexto,
    mensagem,
):
    """
    Oculta somente o aviso conhecido de DPI do Qt no Windows.
    Outros avisos e erros continuam aparecendo normalmente.
    """

    # [Klecio] Garante que a mensagem seja tratada como texto.
    mensagem = str(
        mensagem
    )

    # [Klecio] Se a mensagem for exatamente o aviso conhecido de DPI,
    # [Klecio] simplesmente encerramos a função sem exibi-la.
    if (
        "SetProcessDpiAwarenessContext() failed"
        in mensagem
    ):
        return

    # [Klecio] Todas as demais mensagens continuam sendo enviadas
    # [Klecio] normalmente para a saída de erro do terminal.
    sys.stderr.write(
        mensagem + "\n"
    )


# [Klecio] Função principal da aplicação.
def main():
    # [Klecio] Instala o filtro ANTES da criação do QApplication.
    # [Klecio] Assim qualquer mensagem emitida pelo Qt já passará
    # [Klecio] por este filtro desde o início.
    qInstallMessageHandler(
        filtro_mensagens_qt
    )

    # [Klecio] Cria a aplicação Qt.
    app = QApplication(
        sys.argv
    )

    # [Klecio] Verifica se já existe uma chave de API configurada
    # [Klecio] (por variável de ambiente, .env de desenvolvimento
    # [Klecio] ou uma execução anterior). Isso precisa acontecer
    # [Klecio] antes de importar a janela principal, pois os módulos
    # [Klecio] do SOFTIA leem a chave assim que são carregados.
    if not garantir_chave_api():
        # [Klecio] Importa a janela de configuração apenas quando
        # [Klecio] realmente necessário.
        from ui.api_key_dialog import ApiKeyDialog

        dialogo = ApiKeyDialog()

        # [Klecio] Se o usuário cancelar a janela, o SOFTIA
        # [Klecio] não tem como funcionar e a execução é encerrada.
        if dialogo.exec() != ApiKeyDialog.Accepted:
            sys.exit(0)

        # [Klecio] Salva a chave para as próximas execuções
        # [Klecio] e a disponibiliza imediatamente para este processo.
        salvar_chave(
            dialogo.chave_informada
        )

        os.environ["GEMINI_API_KEY"] = (
            dialogo.chave_informada
        )

    # [Klecio] Importa a janela principal da versão futurista.
    # [Klecio] Este import só acontece depois da chave de API estar
    # [Klecio] garantida, pois os módulos do SOFTIA leem a chave
    # [Klecio] assim que são carregados.
    from ui.main_window import MainWindow

    # [Klecio] Cria a janela principal.
    window = MainWindow()

    # [Klecio] Exibe a janela na tela.
    window.show()

    # [Klecio] Inicia o loop de eventos do Qt.
    # [Klecio] A aplicação permanece executando até o usuário fechá-la.
    sys.exit(
        app.exec()
    )


# [Klecio] Este bloco garante que a função main()
# [Klecio] seja executada apenas quando este arquivo
# [Klecio] for iniciado diretamente.
if __name__ == "__main__":
    main()