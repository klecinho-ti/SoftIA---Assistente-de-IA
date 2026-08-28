# [Klecio] Qt fornece constantes do framework PySide6.
# [Klecio] Neste arquivo, Qt.AlignCenter é usado para centralizar textos.
from PySide6.QtCore import Qt, QTimer

# [Klecio] Importa os componentes visuais usados pela janela:
# [Klecio] QFrame cria os painéis; QHBoxLayout e QVBoxLayout organizam os elementos;
# [Klecio] QLabel exibe textos; QPushButton cria botões; QTextEdit mostra o log;
# [Klecio] QSizePolicy controla expansão; QWidget funciona como container central.
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# [Klecio] Importa a thread que mantém a conexão em tempo real com o Gemini.
# [Klecio] Ela envia status, erros, áudio e sinais de encerramento para a interface.
from gemini.live_client import GeminiLiveWorker
# [Klecio] Importa o visualizador futurista que desenha a esfera,
# [Klecio] os anéis, o status e a animação de áudio.
from ui.softia_visualizer import SoftIAVisualizer


# [Klecio] A variável abaixo contém todo o QSS da interface.
# [Klecio] QSS é semelhante ao CSS e controla cores, bordas, fontes e estados.
# [Klecio] Nenhum comentário foi colocado dentro desta string para não alterar o estilo.
ESTILO_GLOBAL = """
QMainWindow {
    background-color: #050507;
}

QWidget {
    color: #f2f2f4;
    font-family: "Segoe UI";
}

QFrame#painelLateral {
    background-color: rgba(9, 9, 12, 242);
    border: 1px solid rgba(45, 140, 255, 70);
    border-radius: 18px;
}

QFrame#painelPrincipal {
    background-color: rgba(5, 5, 7, 246);
    border: 1px solid rgba(45, 140, 255, 55);
    border-radius: 22px;
}

QLabel#tituloPainel {
    color: #ffffff;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 3px;
}

QLabel#subtituloPainel {
    color: #8c8c94;
    font-size: 11px;
}

QPushButton {
    min-height: 46px;
    padding: 0 16px;
    color: #f5f5f6;
    background-color: rgba(18, 18, 22, 235);
    border: 1px solid rgba(60, 150, 255, 75);
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: rgba(10, 35, 70, 245);
    border: 1px solid rgba(70, 170, 255, 180);
}

QPushButton:pressed {
    background-color: rgba(15, 55, 120, 250);
    border: 1px solid #2f8fff;
}

QPushButton#botaoChamada {
    min-height: 54px;
    color: #ffffff;
    background-color: #0b4cb9;
    border: 1px solid #2f8fff;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#botaoChamada:hover {
    background-color: #1272dd;
}

QPushButton#botaoChamada[encerrando="true"] {
    background-color: #2b2b31;
    border: 1px solid #696973;
    color: #b8b8be;
}

QTextEdit#logBox {
    color: #d7d7dc;
    background-color: rgba(2, 2, 4, 225);
    border: 1px solid rgba(50, 150, 255, 50);
    border-radius: 13px;
    padding: 10px;
    font-family: "Consolas";
    font-size: 10px;
    selection-background-color: #0b4ca1;
}

QScrollBar:vertical {
    width: 7px;
    background: transparent;
}

QScrollBar::handle:vertical {
    min-height: 30px;
    background: rgba(60, 160, 255, 115);
    border-radius: 3px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


# [Klecio] Classe principal da interface futurista.
# [Klecio] Ela herda de QMainWindow, que fornece a estrutura base da janela.
class MainWindow(QMainWindow):

    # [Klecio] Inicializa a janela, define tamanho, estilo
    # [Klecio] e cria todos os componentes visuais.
    def __init__(self):
        # [Klecio] Inicializa corretamente a classe QMainWindow.
        super().__init__()

        # [Klecio] Define o título mostrado na barra superior da janela.
        self.setWindowTitle(
            "SOFTIA // Neural Desktop Assistant"
        )

        # [Klecio] Impede que a janela seja reduzida abaixo deste tamanho.
        self.setMinimumSize(
            1000,
            680,
        )

        # [Klecio] Define o tamanho inicial da janela.
        self.resize(
            1180,
            760,
        )

        # [Klecio] Remove a referência da thread já finalizada.
        self.live_worker = None
        self.session_handle = None
        self.reconectar_automaticamente = False
        self.encerramento_manual = False

        # [Klecio] Aplica o QSS completo armazenado em ESTILO_GLOBAL.
        self.setStyleSheet(
            ESTILO_GLOBAL
        )

        # [Klecio] Chama o método que monta toda a interface.
        self._criar_interface()

    # [Klecio] Cria os painéis, layouts, textos, botões,
    # [Klecio] log e visualizador do SOFTIA.
    def _criar_interface(self):
        # [Klecio] Container central que receberá o layout raiz.
        container = QWidget()

        # [Klecio] Remove margens internas do container.
        container.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        # [Klecio] Layout horizontal principal.
        # [Klecio] Coloca o painel lateral à esquerda e o painel visual à direita.
        layout_raiz = QHBoxLayout(
            container
        )

        # [Klecio] Define as margens externas da interface.
        layout_raiz.setContentsMargins(
            18,
            18,
            18,
            18,
        )

        # [Klecio] Define o espaço entre os dois painéis.
        layout_raiz.setSpacing(
            16
        )

        # [Klecio] Cria o painel lateral de controles e eventos.
        painel_lateral = QFrame()

        # [Klecio] Define o nome usado pelo seletor QSS QFrame#painelLateral.
        painel_lateral.setObjectName(
            "painelLateral"
        )

        # [Klecio] Mantém a largura do painel lateral fixa.
        painel_lateral.setFixedWidth(
            280
        )

        # [Klecio] Organiza verticalmente os itens do painel lateral.
        layout_lateral = QVBoxLayout(
            painel_lateral
        )

        # [Klecio] Define as margens internas do painel lateral.
        layout_lateral.setContentsMargins(
            18,
            20,
            18,
            18,
        )

        # [Klecio] Define o espaço entre os componentes laterais.
        layout_lateral.setSpacing(
            12
        )

        # [Klecio] Cria o título principal do painel lateral.
        titulo = QLabel(
            "SYSTEM CORE"
        )

        # [Klecio] Liga este QLabel ao estilo QLabel#tituloPainel.
        titulo.setObjectName(
            "tituloPainel"
        )

        # [Klecio] Centraliza o título horizontal e verticalmente.
        titulo.setAlignment(
            Qt.AlignCenter
        )

        # [Klecio] Cria o subtítulo descritivo do painel.
        subtitulo = QLabel(
            "Controle neural e telemetria local"
        )

        subtitulo.setObjectName(
            "subtituloPainel"
        )

        subtitulo.setAlignment(
            Qt.AlignCenter
        )

        # [Klecio] Permite quebra automática de linha no subtítulo.
        subtitulo.setWordWrap(
            True
        )

        # [Klecio] Botão principal para iniciar ou encerrar a conexão.
        self.btn_chamada = QPushButton(
            "INICIAR CONEXÃO"
        )

        # [Klecio] Liga o botão ao estilo QPushButton#botaoChamada.
        self.btn_chamada.setObjectName(
            "botaoChamada"
        )

        # [Klecio] Botão que solicita uma captura e análise da tela.
        self.btn_tela = QPushButton(
            "▣  ANALISAR TELA"
        )

        # [Klecio] Botão que solicita uma captura e análise da webcam.
        self.btn_camera = QPushButton(
            "◉  ANALISAR CÂMERA"
        )

        # [Klecio] Título da área de eventos do sistema.
        log_titulo = QLabel(
            "EVENT STREAM"
        )

        log_titulo.setObjectName(
            "subtituloPainel"
        )

        log_titulo.setAlignment(
            Qt.AlignCenter
        )

        # [Klecio] Caixa usada para mostrar mensagens de atividade.
        self.log_box = QTextEdit()

        # [Klecio] Liga a caixa ao estilo QTextEdit#logBox.
        self.log_box.setObjectName(
            "logBox"
        )

        # [Klecio] Impede que o usuário edite o registro manualmente.
        self.log_box.setReadOnly(
            True
        )

        # [Klecio] Mostra uma mensagem enquanto não houver eventos.
        self.log_box.setPlaceholderText(
            "Aguardando eventos do sistema..."
        )

        # [Klecio] Permite que o log se expanda para ocupar o espaço disponível.
        self.log_box.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        # [Klecio] Adiciona um widget ao layout lateral na ordem definida.
        layout_lateral.addWidget(
            titulo
        )

        # [Klecio] Adiciona um widget ao layout lateral na ordem definida.
        layout_lateral.addWidget(
            subtitulo
        )

        # [Klecio] Adiciona um espaço fixo entre grupos de componentes.
        layout_lateral.addSpacing(
            10
        )

        # [Klecio] Adiciona um widget ao layout lateral na ordem definida.
        layout_lateral.addWidget(
            self.btn_chamada
        )

        # [Klecio] Adiciona um widget ao layout lateral na ordem definida.
        layout_lateral.addWidget(
            self.btn_tela
        )

        # [Klecio] Adiciona um widget ao layout lateral na ordem definida.
        layout_lateral.addWidget(
            self.btn_camera
        )

        # [Klecio] Adiciona um espaço fixo entre grupos de componentes.
        layout_lateral.addSpacing(
            10
        )

        # [Klecio] Adiciona um widget ao layout lateral na ordem definida.
        layout_lateral.addWidget(
            log_titulo
        )

        # [Klecio] Adiciona um widget ao layout lateral na ordem definida.
        layout_lateral.addWidget(
            self.log_box,
            1,
        )

        # [Klecio] Cria o painel que receberá o visualizador futurista.
        painel_principal = QFrame()

        # [Klecio] Liga o painel ao estilo QFrame#painelPrincipal.
        painel_principal.setObjectName(
            "painelPrincipal"
        )

        # [Klecio] Cria o layout interno do painel principal.
        layout_principal = QVBoxLayout(
            painel_principal
        )

        # [Klecio] Define uma margem pequena ao redor do visualizador.
        layout_principal.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        # [Klecio] Cria a animação visual do SOFTIA.
        self.visualizador = SoftIAVisualizer()

        # [Klecio] Insere o visualizador no painel principal.
        layout_principal.addWidget(
            self.visualizador
        )

        # [Klecio] Adiciona cada painel ao layout raiz.
        layout_raiz.addWidget(
            painel_lateral
        )

        # [Klecio] Adiciona cada painel ao layout raiz.
        layout_raiz.addWidget(
            painel_principal,
            1,
        )

        # [Klecio] Define o container como conteúdo central da QMainWindow.
        self.setCentralWidget(
            container
        )

        # [Klecio] Ao clicar no botão principal, chama alternar_chamada.
        self.btn_chamada.clicked.connect(
            self.alternar_chamada
        )

        # [Klecio] Liga o botão de tela ao método analisar_tela.
        self.btn_tela.clicked.connect(
            self.analisar_tela
        )

        # [Klecio] Liga o botão da câmera ao método analisar_camera.
        self.btn_camera.clicked.connect(
            self.analisar_camera
        )

    # [Klecio] Acrescenta uma mensagem ao registro de atividades.
    def escrever_log(self, texto):
        # [Klecio] append adiciona o texto ao final, em uma nova linha.
        self.log_box.append(
            f"> {texto}"
        )

    # [Klecio] Decide se deve iniciar ou encerrar a conexão.
    def alternar_chamada(self):
        # [Klecio] Sem worker ativo, inicia uma nova conexão.
        if self.live_worker is None:
            # Uma chamada iniciada manualmente pelo usuário deve começar limpa.
            # O session_handle só é preservado em reconexões automáticas.
            self.session_handle = None
            self.iniciar_chamada()

        # [Klecio] Com worker ativo, solicita o encerramento.
        else:
            self.encerrar_chamada()

    # [Klecio] Atualiza a interface, cria o worker,
    # [Klecio] conecta os sinais e inicia a thread Gemini.
    def iniciar_chamada(self):
        # [Klecio] Troca o texto do botão para indicar que agora ele encerra.
        self.btn_chamada.setText(
            "ENCERRAR CONEXÃO"
        )

        # [Klecio] Define a propriedade dinâmica usada pelo QSS.
        # [Klecio] O valor True ativa o seletor [encerrando="true"].
        self.btn_chamada.setProperty(
            "encerrando",
            True,
        )

        # [Klecio] Remove temporariamente o estilo atual do botão.
        self.btn_chamada.style().unpolish(
            self.btn_chamada
        )

        # [Klecio] Reaplica o estilo considerando a nova propriedade.
        self.btn_chamada.style().polish(
            self.btn_chamada
        )

        # [Klecio] Ativa o modo animado do visualizador.
        self.visualizador.definir_ativo(
            True
        )

        # [Klecio] Atualiza o texto de status da esfera.
        self.visualizador.definir_status(
            "CONECTANDO"
        )

        # [Klecio] Cria a thread responsável pela chamada Gemini Live.
        self.encerramento_manual = False
        self.live_worker = GeminiLiveWorker(
            session_handle=self.session_handle
        )

        # [Klecio] Encaminha mensagens de status para atualizar_status.
        self.live_worker.status_recebido.connect(
            self.atualizar_status
        )

        # [Klecio] Encaminha erros para mostrar_erro.
        self.live_worker.erro_recebido.connect(
            self.mostrar_erro
        )

        # [Klecio] Chama chamada_finalizada quando a thread termina.
        self.live_worker.chamada_encerrada.connect(
            self.chamada_finalizada
        )

        # [Klecio] Permite que o comando de voz encerre a conexão.
        self.live_worker.solicitou_encerramento.connect(
            self.encerrar_chamada_por_voz
        )

        # O GoAway é uma renovação normal solicitada pelo servidor.
        # Não deve aparecer como erro nem como encerramento manual.
        self.live_worker.solicitou_reconexao.connect(
            self.preparar_reconexao_automatica
        )

        self.live_worker.session_handle_atualizado.connect(
            self.salvar_session_handle
        )

        # [Klecio] Verifica se esta versão do worker possui o sinal nivel_audio.
        if hasattr(
            self.live_worker,
            "nivel_audio",
        ):
            # [Klecio] Liga o volume da voz à animação do visualizador.
            self.live_worker.nivel_audio.connect(
                self.visualizador.definir_nivel_audio
            )

        # [Klecio] Inicia efetivamente a QThread.
        self.live_worker.start()

    def encerrar_chamada_por_voz(self):
        """
        Encerra definitivamente a conversa atual por comando de voz.

        O token da sessão é apagado para que a próxima chamada iniciada
        pelo usuário não retome o comando antigo de encerramento.
        """

        self.session_handle = None
        self.encerrar_chamada()

    # [Klecio] Solicita o encerramento controlado da conexão.
    def encerrar_chamada(self):
        # [Klecio] Só executa se houver worker ativo.
        if self.live_worker:
            self.encerramento_manual = True
            self.reconectar_automaticamente = False

            # Encerramento solicitado pelo usuário finaliza a conversa atual.
            # Apenas GoAway/erro automático preserva o session_handle.
            self.session_handle = None
            self.visualizador.definir_status(
                "ENCERRANDO CONEXÃO"
            )

            # [Klecio] Altera o estado interno do worker para finalizar os loops.
            self.live_worker.parar()

    # [Klecio] Atualiza o status visual e registra a mesma mensagem no log.
    def atualizar_status(self, texto):
        # [Klecio] Atualiza o texto de status da esfera.
        self.visualizador.definir_status(
            texto
        )

        self.escrever_log(
            texto
        )

    # [Klecio] Exibe o estado de erro, zera a animação
    # [Klecio] de áudio e registra os detalhes.
    def mostrar_erro(self, erro):
        if not self.encerramento_manual:
            self.reconectar_automaticamente = True

        # [Klecio] Atualiza o texto de status da esfera.
        self.visualizador.definir_status(
            "ERRO NA CONEXÃO"
        )

        # [Klecio] Zera a reação visual de áudio.
        self.visualizador.definir_nivel_audio(
            0.0
        )

        self.escrever_log(
            f"Erro: {erro}"
        )

    # [Klecio] Restaura toda a interface após o fim da chamada.
    def chamada_finalizada(self):
        # [Klecio] Remove a referência da thread já finalizada.
        self.live_worker = None

        # [Klecio] Troca o texto do botão para indicar que agora ele encerra.
        self.btn_chamada.setText(
            "INICIAR CONEXÃO"
        )

        # [Klecio] Define a propriedade dinâmica usada pelo QSS.
        # [Klecio] O valor True ativa o seletor [encerrando="true"].
        self.btn_chamada.setProperty(
            "encerrando",
            False,
        )

        # [Klecio] Remove temporariamente o estilo atual do botão.
        self.btn_chamada.style().unpolish(
            self.btn_chamada
        )

        # [Klecio] Reaplica o estilo considerando a nova propriedade.
        self.btn_chamada.style().polish(
            self.btn_chamada
        )

        # [Klecio] Ativa o modo animado do visualizador.
        self.visualizador.definir_ativo(
            False
        )

        # [Klecio] Atualiza o texto de status da esfera.
        self.visualizador.definir_status(
            "OFFLINE"
        )

        # [Klecio] Zera a reação visual de áudio.
        self.visualizador.definir_nivel_audio(
            0.0
        )

        if self.reconectar_automaticamente and not self.encerramento_manual:
            self.reconectar_automaticamente = False
            self.escrever_log(
                "Reconectando automaticamente sem perder a conversa..."
            )
            QTimer.singleShot(450, self.iniciar_chamada)
        else:
            self.escrever_log(
                "Chamada encerrada."
            )

    def preparar_reconexao_automatica(self):
        """
        Marca a próxima abertura como renovação normal da sessão.
        O worker atual será fechado de forma limpa e a interface
        iniciará outro usando o mesmo session_handle.
        """

        if self.encerramento_manual:
            return

        self.reconectar_automaticamente = True
        self.visualizador.definir_status(
            "RENOVANDO CONEXÃO"
        )

        self.escrever_log(
            "Renovando a conexão sem perder a conversa..."
        )

    def salvar_session_handle(self, handle):
        if handle:
            self.session_handle = handle

    # [Klecio] Solicita ao worker a captura e análise da tela.
    def analisar_tela(self):
        # [Klecio] Impede a ação quando não há conexão ativa.
        if not self.live_worker:
            self.escrever_log(
                "Inicie a conexão antes de analisar a tela."
            )

            return

        self.escrever_log(
            "Solicitando análise da tela..."
        )

        # [Klecio] Encaminha o pedido de tela para a thread Gemini.
        self.live_worker.solicitar_analise_tela()

    # [Klecio] Solicita ao worker a captura e análise da câmera.
    def analisar_camera(self):
        # [Klecio] Impede a ação quando não há conexão ativa.
        if not self.live_worker:
            self.escrever_log(
                "Inicie a conexão antes de analisar a câmera."
            )

            return

        self.escrever_log(
            "Solicitando análise da câmera..."
        )

        # [Klecio] Encaminha o pedido de câmera para a thread Gemini.
        self.live_worker.solicitar_analise_camera()

    # [Klecio] Evento executado automaticamente ao fechar a janela.
    # [Klecio] Ele garante que a thread não permaneça rodando em segundo plano.
    def closeEvent(self, event):
        # [Klecio] Só executa se houver worker ativo.
        if self.live_worker:
            # [Klecio] Altera o estado interno do worker para finalizar os loops.
            self.live_worker.parar()

            # [Klecio] Aguarda por até 3 segundos o encerramento da thread.
            self.live_worker.wait(
                3000
            )

        # [Klecio] Autoriza o fechamento definitivo da janela.
        event.accept()