# [Klecio] os é usado para atualizar a chave de API em memória
# [Klecio] imediatamente após salvar as Configurações.
import os

# [Klecio] time é usado para o intervalo entre leituras do painel
# [Klecio] de hardware e para marcar quando o programa abriu (o
# [Klecio] relógio "LIG" do painel esquerdo).
import time

# [Klecio] datetime fornece a hora e a data exibidas no topo da janela.
from datetime import datetime

# [Klecio] psutil fornece o uso atual de CPU, memória, disco e rede
# [Klecio] para o painel de hardware ao vivo do painel esquerdo.
import psutil

# [Klecio] Qt fornece constantes do framework PySide6.
from PySide6.QtCore import QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont

# [Klecio] Componentes visuais usados para montar a janela.
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# [Klecio] Importa a thread que mantém a conexão em tempo real com o Gemini.
from gemini.live_client import GeminiLiveWorker
# [Klecio] Importa o visualizador futurista (o círculo central animado).
from ui.softia_visualizer import SoftIAVisualizer
# [Klecio] Importa a janela de Configurações.
from ui.settings_dialog import ConfiguracoesDialog
# [Klecio] Funções que leem e salvam as configurações do usuário.
from core.api_key_manager import carregar_configuracoes, salvar_configuracoes


# ============================================================
# ESTILO GLOBAL — painel "terminal ciano", trocado em 19/09/2026
# a pedido do Klecio para reproduzir o visual em painéis do
# JARVIS-CyberBot: janela sem moldura do Windows, caixas de
# status com borda fina, botões em forma de cápsula.
# ============================================================
ESTILO_GLOBAL = """
QMainWindow, QWidget#janelaRaiz {
    background-color: #00060a;
}

QWidget {
    color: #8ffcff;
    font-family: "Courier New";
}

/* -------------------- barra de título customizada -------------------- */
QWidget#barraTitulo {
    background-color: #010d14;
    border-bottom: 1px solid #0d3347;
}

QLabel#tituloBarra {
    color: #8ffcff;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
}

QPushButton#botaoJanela {
    min-width: 40px;
    max-width: 40px;
    min-height: 30px;
    max-height: 30px;
    color: #5ab8cc;
    background-color: transparent;
    border: none;
    font-size: 13px;
}

QPushButton#botaoJanela:hover {
    background-color: rgba(0, 212, 255, 40);
    color: #8ffcff;
}

QPushButton#botaoFechar:hover {
    background-color: #ff3355;
    color: #00060a;
}

/* -------------------- cabeçalho central -------------------- */
QLabel#tituloGrande {
    color: #8ffcff;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 8px;
}

QLabel#subtituloGrande {
    color: #3a8a9a;
    font-size: 10px;
    letter-spacing: 2px;
}

QLabel#relogio {
    color: #8ffcff;
    font-size: 14px;
    font-weight: 700;
}

QLabel#dataAtual {
    color: #3a8a9a;
    font-size: 10px;
}

/* -------------------- caixas de status (CPU/RAM/REDE/GPU/TEMP) -------------------- */
QFrame#caixaStatus {
    background-color: rgba(1, 13, 20, 230);
    border: 1px solid #0d3347;
    border-radius: 3px;
}

QLabel#rotuloStatus {
    color: #3a8a9a;
    font-size: 10px;
    letter-spacing: 1px;
}

QLabel#valorStatusNormal {
    color: #8ffcff;
    font-size: 15px;
    font-weight: 700;
}

QLabel#valorStatusAlerta {
    color: #ff3366;
    font-size: 15px;
    font-weight: 700;
}

QFrame#barraStatusFundo {
    background-color: #001820;
    border-radius: 2px;
}

QFrame#barraStatusPreenchimento {
    background-color: #00d4ff;
    border-radius: 2px;
}

QFrame#barraStatusPreenchimentoAlerta {
    background-color: #ff3366;
    border-radius: 2px;
}

/* -------------------- info compacta (LIG / PROC / SO) -------------------- */
QLabel#infoCompacta {
    color: #5ab8cc;
    font-size: 10px;
}

/* -------------------- câmera -------------------- */
QFrame#caixaCamera {
    background-color: rgba(1, 13, 20, 230);
    border: 1px solid #0d3347;
    border-radius: 3px;
}

QLabel#tituloCamera {
    color: #3a8a9a;
    font-size: 10px;
    letter-spacing: 1px;
}

QLabel#previaCamera {
    color: #3a8a9a;
    font-size: 11px;
    font-weight: 700;
}

QLabel#estadoCamera {
    color: #5ab8cc;
    font-size: 9px;
}

/* -------------------- botão de configurações -------------------- */
QPushButton#botaoConfig {
    min-height: 40px;
    color: #8ffcff;
    background-color: rgba(1, 15, 24, 235);
    border: 1px solid #0d3347;
    border-radius: 3px;
    font-size: 16px;
}

QPushButton#botaoConfig:hover {
    border: 1px solid #00d4ff;
}

/* -------------------- indicadores de rodapé do painel esquerdo -------------------- */
QLabel#indicadorOk {
    color: #00ff88;
    font-size: 10px;
    letter-spacing: 1px;
}

/* -------------------- status do círculo central -------------------- */
QLabel#statusOuvindo {
    color: #00ff88;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
}

/* -------------------- comandos rápidos -------------------- */
QLabel#tituloComandos {
    color: #3a8a9a;
    font-size: 10px;
    letter-spacing: 2px;
}

QLabel#rotuloPainelExpansivel {
    color: #3a8a9a;
    font-size: 9px;
    letter-spacing: 1px;
}

QPushButton#comandoRapido {
    min-height: 62px;
    color: #8ffcff;
    background-color: rgba(1, 15, 24, 235);
    border: 1px solid #0d3347;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    padding-top: 6px;
}

QPushButton#comandoRapido:hover {
    border: 1px solid #00d4ff;
}

QPushButton#comandoRapido[ligado="true"] {
    border: 1px solid #00ff88;
    color: #00ff88;
}

QPushButton#comandoRapido[perigo="true"] {
    border: 1px solid #ff3366;
    color: #ff3366;
}

/* -------------------- transcrição -------------------- */
QLabel#tituloTranscricao {
    color: #3a8a9a;
    font-size: 10px;
    letter-spacing: 2px;
}

QTextEdit#logBox {
    color: #5ab8cc;
    background-color: rgba(1, 5, 7, 225);
    border: 1px solid #0d3347;
    border-radius: 4px;
    padding: 10px;
    font-family: "Courier New";
    font-size: 11px;
    selection-background-color: #007a99;
}

QLineEdit#campoComando {
    min-height: 34px;
    padding: 0 10px;
    color: #8ffcff;
    background-color: rgba(1, 15, 24, 235);
    border: 1px solid #0d3347;
    border-radius: 4px;
}

QPushButton#botaoEnviar {
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    color: #00060a;
    background-color: #00d4ff;
    border: none;
    border-radius: 4px;
    font-weight: 700;
}

/* -------------------- barra de rodapé -------------------- */
QWidget#barraRodape {
    background-color: #010d14;
    border-top: 1px solid #0d3347;
}

QLabel#textoRodape {
    color: #3a8a9a;
    font-size: 9px;
}

/* -------------------- painéis gerais -------------------- */
QFrame#painelEsquerdo, QFrame#painelCentral, QFrame#painelDireito {
    background-color: rgba(0, 6, 10, 246);
    border: 1px solid #0d3347;
    border-radius: 4px;
}

QScrollBar:vertical {
    width: 7px;
    background: transparent;
}

QScrollBar::handle:vertical {
    min-height: 30px;
    background: rgba(0, 212, 255, 130);
    border-radius: 3px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


# [Klecio] Lê o uso de CPU, memória, disco e rede em uma thread
# [Klecio] separada da interface gráfica, para nenhuma leitura
# [Klecio] ocasionalmente lenta travar a janela nem atrasar o áudio
# [Klecio] durante uma chamada.
class MonitorHardwareThread(QThread):

    # Envia CPU%, RAM%, disco%, rede em KB/s e total de processos.
    dados_hardware = Signal(float, float, float, float, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ativo = True

    def run(self):
        # Primeira chamada só define a referência de comparação
        # exigida pelo psutil; o valor em si é descartado.
        psutil.cpu_percent(interval=None)

        contadores_rede = psutil.net_io_counters()
        bytes_anteriores = contadores_rede.bytes_sent + contadores_rede.bytes_recv

        while self.ativo:
            time.sleep(2)

            if not self.ativo:
                break

            try:
                uso_cpu = psutil.cpu_percent(interval=None)
                uso_ram = psutil.virtual_memory().percent
                uso_disco = psutil.disk_usage("C:\\").percent

                contadores_agora = psutil.net_io_counters()
                bytes_agora = contadores_agora.bytes_sent + contadores_agora.bytes_recv
                rede_kbps = max(0.0, (bytes_agora - bytes_anteriores) / 1024 / 2)
                bytes_anteriores = bytes_agora

                total_processos = len(psutil.pids())

            # Se qualquer leitura falhar, ignora esta rodada e tenta
            # novamente no próximo ciclo, sem derrubar a thread.
            except Exception:
                continue

            self.dados_hardware.emit(
                uso_cpu,
                uso_ram,
                uso_disco,
                rede_kbps,
                total_processos,
            )

    def parar(self):
        self.ativo = False


# [Klecio] Uma caixinha de status do painel esquerdo (CPU, RAM, REDE,
# [Klecio] GPU, TEMP): rótulo em cima, valor grande, barrinha fina
# [Klecio] embaixo representando o percentual.
class CaixaStatus(QFrame):

    def __init__(self, rotulo, parent=None):
        super().__init__(parent)
        self.setObjectName("caixaStatus")
        self.setFixedHeight(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(4)

        linha_topo = QHBoxLayout()
        linha_topo.setSpacing(6)

        rotulo_widget = QLabel(rotulo)
        rotulo_widget.setObjectName("rotuloStatus")

        self.valor_widget = QLabel("N/D")
        self.valor_widget.setObjectName("valorStatusNormal")
        self.valor_widget.setAlignment(Qt.AlignRight)

        linha_topo.addWidget(rotulo_widget)
        linha_topo.addStretch(1)
        linha_topo.addWidget(self.valor_widget)

        self._barra_fundo = QFrame()
        self._barra_fundo.setObjectName("barraStatusFundo")
        self._barra_fundo.setFixedHeight(4)

        self._barra_layout = QHBoxLayout(self._barra_fundo)
        self._barra_layout.setContentsMargins(0, 0, 0, 0)
        self._barra_layout.setSpacing(0)

        self._barra_cheia = QFrame()
        self._barra_cheia.setObjectName("barraStatusPreenchimento")
        self._barra_layout.addWidget(self._barra_cheia)
        self._barra_layout.addStretch(1)

        layout.addLayout(linha_topo)
        layout.addWidget(self._barra_fundo)

    # Atualiza o valor exibido e a barrinha de percentual.
    # `percentual=None` mantém a caixa em "N/D" (ex.: GPU e
    # temperatura, que este computador não consegue medir).
    def definir_valor(self, texto, percentual=None):
        self.valor_widget.setText(texto)

        alerta = percentual is not None and percentual >= 80
        self.valor_widget.setObjectName(
            "valorStatusAlerta" if alerta else "valorStatusNormal"
        )
        # Reaplica o estilo depois de trocar o objectName dinamicamente.
        self.valor_widget.style().unpolish(self.valor_widget)
        self.valor_widget.style().polish(self.valor_widget)

        self._barra_cheia.setObjectName(
            "barraStatusPreenchimentoAlerta" if alerta else "barraStatusPreenchimento"
        )
        self._barra_cheia.style().unpolish(self._barra_cheia)
        self._barra_cheia.style().polish(self._barra_cheia)

        largura_total = max(1, self._barra_fundo.width())
        fracao = 0.0 if percentual is None else max(0.0, min(1.0, percentual / 100))
        self._barra_cheia.setFixedWidth(int(largura_total * fracao))


# [Klecio] Barra de título própria, já que a janela não tem mais a
# [Klecio] moldura do Windows. Arrastar aqui move a janela; os três
# [Klecio] botões da direita minimizam, maximizam e fecham.
class BarraTitulo(QWidget):

    def __init__(self, janela, parent=None):
        super().__init__(parent)
        self.setObjectName("barraTitulo")
        self.setFixedHeight(32)
        self._janela = janela
        self._arrastando = False
        self._offset = QPoint()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(8)

        titulo = QLabel("SOFTIA")
        titulo.setObjectName("tituloBarra")

        botao_minimizar = QPushButton("—")
        botao_minimizar.setObjectName("botaoJanela")
        botao_minimizar.clicked.connect(janela.showMinimized)

        botao_maximizar = QPushButton("▢")
        botao_maximizar.setObjectName("botaoJanela")
        botao_maximizar.clicked.connect(self._alternar_maximizado)

        botao_fechar = QPushButton("✕")
        botao_fechar.setObjectName("botaoJanela")
        # objectName extra só para o CSS de hover ficar vermelho.
        botao_fechar.setProperty("class", "fechar")
        botao_fechar.setObjectName("botaoFechar")
        botao_fechar.clicked.connect(janela.close)

        layout.addWidget(titulo)
        layout.addStretch(1)
        layout.addWidget(botao_minimizar)
        layout.addWidget(botao_maximizar)
        layout.addWidget(botao_fechar)

    def _alternar_maximizado(self):
        if self._janela.isMaximized():
            self._janela.showNormal()
        else:
            self._janela.showMaximized()

    def mousePressEvent(self, evento):
        if evento.button() == Qt.LeftButton:
            self._arrastando = True
            self._offset = evento.globalPosition().toPoint() - self._janela.frameGeometry().topLeft()

    def mouseMoveEvent(self, evento):
        if self._arrastando and evento.buttons() & Qt.LeftButton:
            self._janela.move(evento.globalPosition().toPoint() - self._offset)

    def mouseReleaseEvent(self, evento):
        self._arrastando = False

    def mouseDoubleClickEvent(self, evento):
        self._alternar_maximizado()


# [Klecio] Classe principal da interface, agora no visual "painel
# [Klecio] JARVIS": janela sem moldura do Windows, painel de status
# [Klecio] à esquerda, círculo central, comandos rápidos embaixo,
# [Klecio] transcrição à direita e barra de rodapé.
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # Remove a moldura padrão do Windows — a barra de título
        # agora é desenhada pelo próprio SOFTIA (classe BarraTitulo).
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.setMinimumSize(1180, 760)
        self.resize(1280, 820)

        self.live_worker = None
        self.session_handle = None
        self.reconectar_automaticamente = False
        self.encerramento_manual = False
        self.modo_silencio = False

        # Guardado para o relógio "LIG" do painel esquerdo (há quanto
        # tempo o SOFTIA está aberto).
        self._aberto_desde = time.monotonic()

        self.setStyleSheet(ESTILO_GLOBAL)

        self._criar_interface()

        self._aplicar_nome_assistente(
            carregar_configuracoes()["nome_assistente"]
        )

    # ========================================================
    # MONTAGEM DA INTERFACE
    # ========================================================

    def _criar_interface(self):
        raiz = QWidget()
        raiz.setObjectName("janelaRaiz")

        layout_vertical_raiz = QVBoxLayout(raiz)
        layout_vertical_raiz.setContentsMargins(0, 0, 0, 0)
        layout_vertical_raiz.setSpacing(0)

        # -------------------- barra de título --------------------
        self._barra_titulo = BarraTitulo(self)
        layout_vertical_raiz.addWidget(self._barra_titulo)

        # -------------------- corpo --------------------
        corpo = QWidget()
        layout_corpo = QVBoxLayout(corpo)
        layout_corpo.setContentsMargins(16, 12, 16, 8)
        layout_corpo.setSpacing(10)

        layout_corpo.addLayout(self._montar_cabecalho())

        linha_principal = QHBoxLayout()
        linha_principal.setSpacing(12)
        linha_principal.addWidget(self._montar_painel_esquerdo())
        linha_principal.addWidget(self._montar_painel_central(), 1)
        linha_principal.addWidget(self._montar_painel_direito())
        layout_corpo.addLayout(linha_principal, 1)

        layout_vertical_raiz.addWidget(corpo, 1)

        # -------------------- rodapé --------------------
        layout_vertical_raiz.addWidget(self._montar_rodape())

        self.setCentralWidget(raiz)

        # Liga os botões aos mesmos métodos de sempre.
        self.btn_chamada.clicked.connect(self.alternar_chamada)
        self.btn_tela.clicked.connect(self.analisar_tela)
        self.btn_camera.clicked.connect(self.analisar_camera)
        self.btn_configuracoes.clicked.connect(self.abrir_configuracoes)

        # Thread do painel de hardware.
        self.thread_hardware = MonitorHardwareThread(self)
        self.thread_hardware.dados_hardware.connect(self._atualizar_hardware)
        self.thread_hardware.start()

        # Relógio do topo, atualizado a cada segundo.
        self._timer_relogio = QTimer(self)
        self._timer_relogio.timeout.connect(self._atualizar_relogio)
        self._timer_relogio.start(1000)
        self._atualizar_relogio()

    # -------------------- cabeçalho (título central + relógio) --------------------
    def _montar_cabecalho(self):
        layout = QHBoxLayout()
        layout.setSpacing(0)

        layout.addStretch(1)

        centro = QVBoxLayout()
        centro.setSpacing(2)

        self._titulo_grande = QLabel("S.O.F.T.I.A.")
        self._titulo_grande.setObjectName("tituloGrande")
        self._titulo_grande.setAlignment(Qt.AlignCenter)

        subtitulo = QLabel("Assistente de IA para Desktop")
        subtitulo.setObjectName("subtituloGrande")
        subtitulo.setAlignment(Qt.AlignCenter)

        centro.addWidget(self._titulo_grande)
        centro.addWidget(subtitulo)

        layout.addLayout(centro)
        layout.addStretch(1)

        direita = QVBoxLayout()
        direita.setSpacing(0)
        self._label_relogio = QLabel("--:--:--")
        self._label_relogio.setObjectName("relogio")
        self._label_relogio.setAlignment(Qt.AlignRight)
        self._label_data = QLabel("")
        self._label_data.setObjectName("dataAtual")
        self._label_data.setAlignment(Qt.AlignRight)
        direita.addWidget(self._label_relogio)
        direita.addWidget(self._label_data)
        layout.addLayout(direita)

        return layout

    # -------------------- painel esquerdo (status + câmera + config) --------------------
    def _montar_painel_esquerdo(self):
        painel = QFrame()
        painel.setObjectName("painelEsquerdo")
        painel.setFixedWidth(200)

        layout = QVBoxLayout(painel)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        self._caixa_cpu = CaixaStatus("CPU")
        self._caixa_ram = CaixaStatus("RAM")
        self._caixa_rede = CaixaStatus("REDE")
        self._caixa_gpu = CaixaStatus("GPU")
        self._caixa_temp = CaixaStatus("TEMP")

        for caixa in (
            self._caixa_cpu,
            self._caixa_ram,
            self._caixa_rede,
            self._caixa_gpu,
            self._caixa_temp,
        ):
            layout.addWidget(caixa)

        self._label_info_compacta = QLabel(
            "LIG  00:00\nPROC  --\nSO  WIN"
        )
        self._label_info_compacta.setObjectName("infoCompacta")
        layout.addWidget(self._label_info_compacta)

        # -------------------- câmera --------------------
        caixa_camera = QFrame()
        caixa_camera.setObjectName("caixaCamera")
        layout_camera = QVBoxLayout(caixa_camera)
        layout_camera.setContentsMargins(10, 8, 10, 8)
        layout_camera.setSpacing(4)

        titulo_camera = QLabel("• CÂMERA")
        titulo_camera.setObjectName("tituloCamera")

        previa_camera = QLabel("VISÃO\nDESL.")
        previa_camera.setObjectName("previaCamera")
        previa_camera.setAlignment(Qt.AlignCenter)
        previa_camera.setFixedHeight(50)

        estado_camera = QLabel("INATIVA")
        estado_camera.setObjectName("estadoCamera")
        estado_camera.setAlignment(Qt.AlignCenter)

        layout_camera.addWidget(titulo_camera)
        layout_camera.addWidget(previa_camera)
        layout_camera.addWidget(estado_camera)

        layout.addWidget(caixa_camera)

        # -------------------- botão de configurações --------------------
        self.btn_configuracoes = QPushButton("⚙")
        self.btn_configuracoes.setObjectName("botaoConfig")
        layout.addWidget(self.btn_configuracoes)

        layout.addStretch(1)

        # -------------------- indicadores de rodapé --------------------
        for texto in ("● NÚCLEO ATIVO", "● SEGURANÇA OK", "● PROTOCOLO SOFTIA"):
            indicador = QLabel(texto)
            indicador.setObjectName("indicadorOk")
            layout.addWidget(indicador)

        return painel

    # -------------------- painel central (círculo + comandos rápidos) --------------------
    def _montar_painel_central(self):
        painel = QFrame()
        painel.setObjectName("painelCentral")

        layout = QVBoxLayout(painel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.visualizador = SoftIAVisualizer()
        layout.addWidget(self.visualizador, 1)

        # -------------------- comandos rápidos --------------------
        titulo_comandos = QLabel("▾ COMANDOS RÁPIDOS")
        titulo_comandos.setObjectName("tituloComandos")
        layout.addWidget(titulo_comandos)

        linha_comandos = QHBoxLayout()
        linha_comandos.setSpacing(8)

        self.btn_chamada = QPushButton("MICROFONE\nATIVO")
        self.btn_chamada.setObjectName("comandoRapido")
        self.btn_chamada.setProperty("ligado", True)

        self.btn_tela = QPushButton("ANALISAR\nTELA")
        self.btn_tela.setObjectName("comandoRapido")

        self.btn_camera = QPushButton("ANALISAR\nCÂMERA")
        self.btn_camera.setObjectName("comandoRapido")

        for botao in (self.btn_chamada, self.btn_tela, self.btn_camera):
            linha_comandos.addWidget(botao)

        layout.addLayout(linha_comandos)

        return painel

    # -------------------- painel direito (transcrição) --------------------
    def _montar_painel_direito(self):
        painel = QFrame()
        painel.setObjectName("painelDireito")
        painel.setFixedWidth(340)

        layout = QVBoxLayout(painel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        linha_titulo = QHBoxLayout()
        titulo = QLabel("TRANSCRIÇÃO / STATUS")
        titulo.setObjectName("tituloTranscricao")
        rotulo_expansivel = QLabel("PAINEL EXPANSÍVEL")
        rotulo_expansivel.setObjectName("rotuloPainelExpansivel")
        linha_titulo.addWidget(titulo)
        linha_titulo.addStretch(1)
        linha_titulo.addWidget(rotulo_expansivel)
        layout.addLayout(linha_titulo)

        self.log_box = QTextEdit()
        self.log_box.setObjectName("logBox")
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Aguardando eventos do sistema...")
        self.log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.log_box, 1)

        linha_comando = QHBoxLayout()
        self._campo_comando = QLineEdit()
        self._campo_comando.setObjectName("campoComando")
        self._campo_comando.setPlaceholderText("Digite um comando ou pergunta...")
        botao_enviar = QPushButton("▶")
        botao_enviar.setObjectName("botaoEnviar")
        linha_comando.addWidget(self._campo_comando)
        linha_comando.addWidget(botao_enviar)
        layout.addLayout(linha_comando)

        return painel

    # -------------------- rodapé --------------------
    def _montar_rodape(self):
        rodape = QWidget()
        rodape.setObjectName("barraRodape")
        rodape.setFixedHeight(26)

        layout = QHBoxLayout(rodape)
        layout.setContentsMargins(14, 0, 14, 0)

        esquerda = QLabel("[F11] Tela cheia   ·   [ESC] Interromper")
        esquerda.setObjectName("textoRodape")

        centro = QLabel("SoftIA · Assistente de IA para Desktop")
        centro.setObjectName("textoRodape")
        centro.setAlignment(Qt.AlignCenter)

        direita = QLabel("© Klecio Mauricio")
        direita.setObjectName("textoRodape")
        direita.setAlignment(Qt.AlignRight)

        layout.addWidget(esquerda)
        layout.addWidget(centro, 1)
        layout.addWidget(direita)

        return rodape

    # ========================================================
    # RELÓGIO E HARDWARE
    # ========================================================

    def _atualizar_relogio(self):
        agora = datetime.now()
        self._label_relogio.setText(agora.strftime("%H:%M:%S"))
        self._label_data.setText(agora.strftime("%a %d %b %Y"))

    def _atualizar_hardware(self, uso_cpu, uso_ram, uso_disco, rede_kbps, total_processos):
        self._caixa_cpu.definir_valor(f"{uso_cpu:.0f}%", uso_cpu)
        self._caixa_ram.definir_valor(f"{uso_ram:.0f}%", uso_ram)

        if rede_kbps >= 1024:
            texto_rede = f"{rede_kbps / 1024:.1f}MB/s"
        else:
            texto_rede = f"{rede_kbps:.0f}KB/s"
        self._caixa_rede.definir_valor(texto_rede, None)

        # GPU e temperatura ficam "N/D": o Windows não expõe isso de
        # forma confiável sem biblioteca extra específica do fabricante
        # da placa — mesmo comportamento visto no painel original.
        self._caixa_gpu.definir_valor("N/D", None)
        self._caixa_temp.definir_valor("N/D", None)

        tempo_aberto = int(time.monotonic() - self._aberto_desde)
        horas, resto = divmod(tempo_aberto, 3600)
        minutos, _ = divmod(resto, 60)
        self._label_info_compacta.setText(
            f"LIG  {horas:02d}:{minutos:02d}\n"
            f"PROC  {total_processos}\n"
            f"SO  WIN"
        )

    # ========================================================
    # O RESTO DA LÓGICA (chamada, hardware, configurações) É O
    # MESMO DE ANTES DA TROCA DE VISUAL — só a montagem da
    # interface mudou acima.
    # ========================================================

    def escrever_log(self, texto):
        self.log_box.append(f"> {texto}")

    def alternar_chamada(self):
        if self.live_worker is None:
            self.session_handle = None
            self.iniciar_chamada()
        else:
            self.encerrar_chamada()

    def iniciar_chamada(self):
        self.btn_chamada.setText("ENCERRAR\nCONEXÃO")
        self.btn_chamada.setProperty("perigo", True)
        self.btn_chamada.setProperty("ligado", False)
        self.btn_chamada.style().unpolish(self.btn_chamada)
        self.btn_chamada.style().polish(self.btn_chamada)

        self.visualizador.definir_ativo(True)
        self.visualizador.definir_status("CONECTANDO")

        self.encerramento_manual = False
        self.live_worker = GeminiLiveWorker(
            session_handle=self.session_handle,
            modo_silencio=self.modo_silencio,
        )

        self.live_worker.status_recebido.connect(self.atualizar_status)
        self.live_worker.erro_recebido.connect(self.mostrar_erro)
        self.live_worker.chamada_encerrada.connect(self.chamada_finalizada)
        self.live_worker.solicitou_encerramento.connect(self.encerrar_chamada_por_voz)
        self.live_worker.solicitou_reconexao.connect(self.preparar_reconexao_automatica)
        self.live_worker.session_handle_atualizado.connect(self.salvar_session_handle)

        if hasattr(self.live_worker, "modo_silencio_atualizado"):
            self.live_worker.modo_silencio_atualizado.connect(self.salvar_modo_silencio)

        if hasattr(self.live_worker, "nivel_audio"):
            self.live_worker.nivel_audio.connect(self.visualizador.definir_nivel_audio)

        self.live_worker.start()

    def encerrar_chamada_por_voz(self):
        self.session_handle = None
        self.encerrar_chamada()

    def encerrar_chamada(self):
        if self.live_worker:
            self.encerramento_manual = True
            self.reconectar_automaticamente = False
            self.session_handle = None
            self.modo_silencio = False
            self.visualizador.definir_status("ENCERRANDO CONEXÃO")
            self.live_worker.parar()

    def atualizar_status(self, texto):
        self.visualizador.definir_status(texto)
        self.escrever_log(texto)

    def mostrar_erro(self, erro):
        if not self.encerramento_manual:
            self.reconectar_automaticamente = True
        self.visualizador.definir_status("ERRO NA CONEXÃO")
        self.visualizador.definir_nivel_audio(0.0)
        self.escrever_log(f"Erro: {erro}")

    def chamada_finalizada(self):
        self.live_worker = None
        self.btn_chamada.setText("MICROFONE\nATIVO")
        self.btn_chamada.setProperty("perigo", False)
        self.btn_chamada.setProperty("ligado", True)
        self.btn_chamada.style().unpolish(self.btn_chamada)
        self.btn_chamada.style().polish(self.btn_chamada)

        self.visualizador.definir_ativo(False)
        self.visualizador.definir_status("OFFLINE")
        self.visualizador.definir_nivel_audio(0.0)

        if self.reconectar_automaticamente and not self.encerramento_manual:
            self.reconectar_automaticamente = False
            self.escrever_log("Reconectando automaticamente sem perder a conversa...")
            QTimer.singleShot(450, self.iniciar_chamada)
        else:
            self.escrever_log("Chamada encerrada.")

    def preparar_reconexao_automatica(self):
        if self.encerramento_manual:
            return
        self.reconectar_automaticamente = True
        self.visualizador.definir_status("RENOVANDO CONEXÃO")
        self.escrever_log("Renovando a conexão sem perder a conversa...")

    def salvar_session_handle(self, handle):
        if handle:
            self.session_handle = handle

    def salvar_modo_silencio(self, ativo):
        self.modo_silencio = ativo

    def analisar_tela(self):
        if not self.live_worker:
            self.escrever_log("Inicie a conexão antes de analisar a tela.")
            return
        self.escrever_log("Solicitando análise da tela...")
        self.live_worker.solicitar_analise_tela()

    def analisar_camera(self):
        if not self.live_worker:
            self.escrever_log("Inicie a conexão antes de analisar a câmera.")
            return
        self.escrever_log("Solicitando análise da câmera...")
        self.live_worker.solicitar_analise_camera()

    def _aplicar_nome_assistente(self, nome):
        nome = str(nome or "SOFTIA").strip() or "SOFTIA"
        self.setWindowTitle(f"{nome.upper()} // Neural Desktop Assistant")
        self.visualizador.definir_nome(nome)

    def abrir_configuracoes(self):
        configuracoes_atuais = carregar_configuracoes()
        dialogo = ConfiguracoesDialog(self, configuracoes_atuais=configuracoes_atuais)
        if dialogo.exec() != ConfiguracoesDialog.Accepted:
            return
        novas_configuracoes = salvar_configuracoes(dialogo.configuracoes_confirmadas)
        os.environ["GEMINI_API_KEY"] = novas_configuracoes["gemini_api_key"]
        self._aplicar_nome_assistente(novas_configuracoes["nome_assistente"])
        self.escrever_log("Configurações salvas.")

    def closeEvent(self, event):
        self.thread_hardware.parar()
        self.thread_hardware.wait(3000)
        if self.live_worker:
            self.live_worker.parar()
            self.live_worker.wait(3000)
        event.accept()
