# math fornece funções matemáticas.
# Neste arquivo, é utilizado em cálculos de curvas,
# senoides, proporções e dimensões dos elementos visuais.
import math
# time é utilizado para medir o tempo da animação.
# time.monotonic() fornece um relógio contínuo e confiável.
import time

# Componentes principais do Qt:
# QPointF representa pontos com coordenadas decimais.
# QRectF representa retângulos com coordenadas decimais.
# Qt fornece constantes do framework.
# QTimer controla a frequência da animação.
from PySide6.QtCore import (
    QPointF,
    QRectF,
    Qt,
    QTimer,
)

# Componentes gráficos utilizados para desenhar a interface:
# QColor define cores.
# QFont define fontes.
# QLinearGradient cria gradientes lineares.
# QPainter desenha na tela.
# QPen configura contornos.
# QPixmap armazena imagens em memória.
# QRadialGradient cria gradientes circulares.
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)

# QWidget é a classe base do componente visual personalizado.
from PySide6.QtWidgets import QWidget


# Classe responsável por desenhar toda a interface animada do SOFTIA.
# Como herda de QWidget, pode ser colocada diretamente na janela principal.
class SoftIAVisualizer(QWidget):
    """
    Visualizador futurista otimizado do SOFTIA.

    Elementos pesados, como fundo e esfera, são criados
    apenas quando a janela abre ou muda de tamanho.

    Durante a animação são atualizados somente:
    - dois anéis;
    - brilho reativo;
    - indicador de áudio;
    - textos.

    Isso reduz bastante o uso de CPU.
    """

    # Quantidade de quadros por segundo quando o SOFTIA está offline.
    # O valor baixo reduz o consumo de CPU.
    FPS_OFFLINE = 6
    # Quantidade de quadros por segundo quando o SOFTIA está conectado.
    FPS_ATIVO = 15
    # Quantidade de quadros por segundo durante a fala.
    # Um FPS maior deixa o indicador de áudio mais fluido.
    FPS_FALANDO = 20

    # Inicializa o visualizador, seus estados,
    # caches gráficos e o temporizador de animação.
    def __init__(self, parent=None):
        # Inicializa a classe QWidget.
        super().__init__(parent)

        # Define a altura mínima do componente.
        self.setMinimumHeight(360)

        # Configura atributos de pintura para reduzir
        # processamento desnecessário do fundo pelo Qt.
        self.setAttribute(
            Qt.WA_OpaquePaintEvent,
            True,
        )

        # Configura atributos de pintura para reduzir
        # processamento desnecessário do fundo pelo Qt.
        self.setAttribute(
            Qt.WA_NoSystemBackground,
            True,
        )

        # Indica se o SOFTIA está conectado ou ativo.
        self.ativo = False
        # Texto de status exibido abaixo do título.
        self.status = "OFFLINE"
        # Nome exibido no título central, já espaçado entre letras.
        # Pode ser trocado em tempo real pela janela de Configurações.
        self.nome_exibido = "S O F T I A"

        # Nível bruto de áudio recebido da thread.
        self.nivel_audio = 0.0
        # Versão suavizada do nível de áudio.
        # Evita movimentos bruscos na animação.
        self.nivel_suavizado = 0.0

        # Registra o início da animação.
        # Esse valor é usado para calcular movimentos contínuos.
        self.tempo_inicial = time.monotonic()

        # Imagem em memória que armazena o fundo já desenhado.
        self.cache_fundo = QPixmap()
        # Imagem em memória que armazena a esfera fixa já desenhada.
        self.cache_esfera = QPixmap()

        # Guarda o último tamanho utilizado para evitar
        # recriar caches sem necessidade.
        self.ultimo_tamanho = None

        # QTimer chama periodicamente a atualização da animação.
        self.timer = QTimer(self)

        # Liga o evento do timer ao método que atualiza a animação.
        self.timer.timeout.connect(
            self._atualizar_animacao
        )

        # Define o FPS inicial do modo offline.
        self._definir_fps(
            self.FPS_OFFLINE
        )

        # Inicia o temporizador.
        self.timer.start()

    # ========================================================
    # CONTROLE EXTERNO
    # ========================================================

    # Atualiza o texto de status exibido na interface.
    def definir_status(self, texto):
        # Converte o valor para texto e transforma em maiúsculas.
        self.status = str(
            texto
        ).upper()

        # Solicita ao Qt uma nova pintura do componente.
        self.update()

    # Atualiza o nome exibido no título central da esfera.
    def definir_nome(self, nome):
        # Converte para maiúsculas e remove espaços extras nas pontas.
        nome = str(
            nome or "SOFTIA"
        ).strip().upper() or "SOFTIA"

        # Insere um espaço entre cada letra, como no visual original
        # ("SOFTIA" -> "S O F T I A").
        self.nome_exibido = " ".join(
            list(nome)
        )

        # Solicita ao Qt uma nova pintura do componente.
        self.update()

    # Ativa ou desativa visualmente o SOFTIA.
    def definir_ativo(self, ativo):
        # Garante que o valor seja booleano.
        self.ativo = bool(
            ativo
        )

        # Define cor e símbolo quando o SOFTIA está ativo.
        if self.ativo:
            self._definir_fps(
                self.FPS_ATIVO
            )

        # Define cor e símbolo quando está offline.
        else:
            self.nivel_audio = 0.0
            self.nivel_suavizado = 0.0

            self._definir_fps(
                self.FPS_OFFLINE
            )

        # Solicita ao Qt uma nova pintura do componente.
        self.update()

    # Recebe o nível de áudio calculado na thread Gemini.
    def definir_nivel_audio(self, nivel):
        try:
            # Converte o valor recebido para número decimal.
            nivel = float(
                nivel
            )

        except (
            TypeError,
            ValueError,
        ):
            nivel = 0.0

        # Limita o nível à faixa entre 0 e 1.
        self.nivel_audio = max(
            0.0,
            min(
                1.0,
                nivel,
            ),
        )

        # Quando há fala detectável, aumenta o FPS.
        if self.nivel_audio > 0.04:
            self._definir_fps(
                self.FPS_FALANDO
            )

        # Se não estiver falando, mas estiver ativo,
        # retorna ao FPS normal.
        elif self.ativo:
            self._definir_fps(
                self.FPS_ATIVO
            )

    # ========================================================
    # FPS
    # ========================================================

    # Converte o FPS desejado em intervalo de milissegundos.
    def _definir_fps(self, fps):
        # Calcula o tempo entre quadros.
        # Exemplo: 1000 / 20 = 50 ms por quadro.
        intervalo = max(
            1,
            int(
                1000 / fps
            ),
        )

        # Só atualiza o timer quando o intervalo mudou.
        if self.timer.interval() != intervalo:
            self.timer.setInterval(
                intervalo
            )

    # ========================================================
    # ANIMAÇÃO
    # ========================================================

    # Atualiza o nível suavizado e solicita nova pintura.
    def _atualizar_animacao(self):
        # O alvo da animação é o nível atual de áudio.
        alvo = self.nivel_audio

        # Mantém uma leve animação mesmo quando o SOFTIA
        # está ativo e em silêncio.
        if self.ativo and alvo < 0.02:
            alvo = 0.015

        # Ao aumentar o áudio, a animação reage mais rápido.
        if alvo > self.nivel_suavizado:
            # Velocidade de subida do nível suavizado.
            velocidade = 0.36

        # Define cor e símbolo quando está offline.
        else:
            # Velocidade de queda do nível suavizado.
            velocidade = 0.10

        # Interpolação simples entre o valor atual e o alvo.
        self.nivel_suavizado += (
            alvo - self.nivel_suavizado
        ) * velocidade

        # Verifica condições antes de continuar.
        if (
            self.nivel_audio <= 0.02
            and self.ativo
        ):
            self._definir_fps(
                self.FPS_ATIVO
            )

        # Solicita ao Qt uma nova pintura do componente.
        self.update()

    # ========================================================
    # REDIMENSIONAMENTO
    # ========================================================

    # Evento chamado automaticamente quando o widget muda de tamanho.
    def resizeEvent(self, event):
        # Recria o fundo e a esfera no novo tamanho.
        self._recriar_cache()

        super().resizeEvent(
            event
        )

    # Recria os elementos gráficos estáticos.
    # Isso evita desenhá-los em todos os quadros.
    def _recriar_cache(self):
        # Obtém o tamanho atual do componente.
        tamanho = self.size()

        # Verifica condições antes de continuar.
        if (
            tamanho.width() <= 0
            or tamanho.height() <= 0
        ):
            return

        # Cria uma tupla simples com largura e altura.
        tamanho_atual = (
            tamanho.width(),
            tamanho.height(),
        )

        # Evita recriar os caches se o tamanho não mudou.
        if tamanho_atual == self.ultimo_tamanho:
            return

        self.ultimo_tamanho = tamanho_atual

        # Gera e armazena o fundo em memória.
        self.cache_fundo = (
            self._criar_fundo_cache()
        )

        # Gera e armazena a esfera em memória.
        self.cache_esfera = (
            self._criar_esfera_cache()
        )

    # ========================================================
    # FUNDO
    # ========================================================

    # Desenha o fundo completo uma única vez por tamanho.
    def _criar_fundo_cache(self):
        # Obtém a largura atual do widget.
        largura = self.width()
        # Obtém a altura atual do widget.
        altura = self.height()

        # Cria uma imagem em memória com o tamanho do widget.
        pixmap = QPixmap(
            largura,
            altura,
        )

        # Preenche o pixmap com transparência.
        pixmap.fill(
            QColor(
                2,
                4,
                10,
            )
        )

        # Cria o pintor diretamente sobre o widget.
        painter = QPainter(
            pixmap
        )

        # Define o centro visual do gradiente.
        centro = QPointF(
            largura * 0.50,
            altura * 0.48,
        )

        # Cria o gradiente radial principal do fundo.
        gradiente = QRadialGradient(
            centro,
            max(
                largura,
                altura,
            ) * 0.76,
        )

        # Define uma etapa de cor dentro do gradiente.
        gradiente.setColorAt(
            0.0,
            QColor(
                0,
                40,
                80,
            ),
        )

        # Define uma etapa de cor dentro do gradiente.
        gradiente.setColorAt(
            0.32,
            QColor(
                0,
                18,
                40,
            ),
        )

        # Define uma etapa de cor dentro do gradiente.
        gradiente.setColorAt(
            0.68,
            QColor(
                3,
                8,
                18,
            ),
        )

        # Define uma etapa de cor dentro do gradiente.
        gradiente.setColorAt(
            1.0,
            QColor(
                1,
                2,
                6,
            ),
        )

        # Preenche toda a imagem com o gradiente.
        painter.fillRect(
            pixmap.rect(),
            gradiente,
        )

        # Cria uma vinheta horizontal para escurecer as laterais.
        vinheta = QLinearGradient(
            0,
            0,
            largura,
            0,
        )

        vinheta.setColorAt(
            0.0,
            QColor(
                0,
                0,
                0,
                170,
            ),
        )

        vinheta.setColorAt(
            0.20,
            QColor(
                0,
                0,
                0,
                25,
            ),
        )

        vinheta.setColorAt(
            0.80,
            QColor(
                0,
                0,
                0,
                25,
            ),
        )

        vinheta.setColorAt(
            1.0,
            QColor(
                0,
                0,
                0,
                170,
            ),
        )

        # Preenche toda a imagem com o gradiente.
        painter.fillRect(
            pixmap.rect(),
            vinheta,
        )

        # Finaliza o QPainter e libera os recursos.
        painter.end()

        return pixmap

    # ========================================================
    # ESFERA
    # ========================================================

    # Desenha a esfera e seus elementos fixos em um cache.
    def _criar_esfera_cache(self):
        # Obtém a largura atual do widget.
        largura = self.width()
        # Obtém a altura atual do widget.
        altura = self.height()

        # Cria uma imagem em memória com o tamanho do widget.
        pixmap = QPixmap(
            largura,
            altura,
        )

        # Preenche o pixmap com transparência.
        pixmap.fill(
            Qt.transparent
        )

        # Cria o pintor diretamente sobre o widget.
        painter = QPainter(
            pixmap
        )

        # Ativa antialiasing para deixar curvas suaves.
        painter.setRenderHint(
            QPainter.Antialiasing,
            True,
        )

        # Centralização exata da esfera
        # Define o centro visual do gradiente.
        centro = QPointF(
            largura * 0.50,
            altura * 0.49,
        )

        # Calcula o raio com base no menor lado disponível.
        # Isso mantém a esfera proporcional.
        raio = min(
            largura,
            altura,
        ) * 0.245

        # ====================================================
        # SOMBRA INFERIOR
        # ====================================================

        # Define o centro da sombra abaixo da esfera.
        centro_sombra = QPointF(
            centro.x(),
            centro.y() + raio * 1.48,
        )

        # Cria o gradiente da sombra inferior.
        sombra = QRadialGradient(
            centro_sombra,
            raio * 1.05,
        )

        sombra.setColorAt(
            0.0,
            QColor(
                40,
                140,
                255,
                65,
            ),
        )

        sombra.setColorAt(
            0.50,
            QColor(
                20,
                90,
                180,
                20,
            ),
        )

        sombra.setColorAt(
            1.0,
            QColor(
                0,
                0,
                0,
                0,
            ),
        )

        # Define a cor do texto.
        painter.setPen(
            Qt.NoPen
        )

        # Configura o preenchimento usado nos próximos desenhos.
        painter.setBrush(
            sombra
        )

        # Desenha uma elipse usando as dimensões informadas.
        painter.drawEllipse(
            centro_sombra,
            raio * 1.00,
            raio * 0.20,
        )

        # ====================================================
        # HALO EXTERNO FIXO
        # ====================================================

        # Cria o halo vermelho ao redor da esfera.
        brilho_externo = QRadialGradient(
            centro,
            raio * 1.48,
        )

        brilho_externo.setColorAt(
            0.0,
            QColor(
                60,
                160,
                255,
                48,
            ),
        )

        brilho_externo.setColorAt(
            0.62,
            QColor(
                30,
                110,
                200,
                15,
            ),
        )

        brilho_externo.setColorAt(
            1.0,
            QColor(
                0,
                0,
                0,
                0,
            ),
        )

        # Configura o preenchimento usado nos próximos desenhos.
        painter.setBrush(
            brilho_externo
        )

        # Desenha uma elipse usando as dimensões informadas.
        painter.drawEllipse(
            centro,
            raio * 1.48,
            raio * 1.48,
        )

        # ====================================================
        # CORPO DA ESFERA
        # ====================================================

        # Cria o gradiente principal do corpo da esfera.
        esfera = QRadialGradient(
            QPointF(
                centro.x() - raio * 0.22,
                centro.y() - raio * 0.25,
            ),
            raio * 1.25,
        )

        esfera.setColorAt(
            0.0,
            QColor(
                10,
                60,
                130,
            ),
        )

        esfera.setColorAt(
            0.32,
            QColor(
                5,
                30,
                70,
            ),
        )

        esfera.setColorAt(
            0.72,
            QColor(
                2,
                10,
                25,
            ),
        )

        esfera.setColorAt(
            1.0,
            QColor(
                1,
                3,
                8,
            ),
        )

        # Define a cor do texto.
        painter.setPen(
            QPen(
                QColor(
                    70,
                    170,
                    255,
                    190,
                ),
                1.4,
            )
        )

        # Define a cor do texto.
        painter.setPen(
            QPen(
                QColor(
                    70,
                    170,
                    255,
                    190,
                ),
                1.4,
            )
        )

        # Configura o preenchimento usado nos próximos desenhos.
        painter.setBrush(
            esfera
        )

        # Desenha uma elipse usando as dimensões informadas.
        painter.drawEllipse(
            centro,
            raio,
            raio,
        )

        # Configura o preenchimento usado nos próximos desenhos.
        painter.setBrush(
            Qt.NoBrush
        )

        # ====================================================
        # LINHAS HORIZONTAIS
        # ====================================================

        # Define a cor do texto.
        painter.setPen(
            QPen(
                QColor(
                    60,
                    150,
                    255,
                    90,
                ),
                0.9,
            )
        )

        # Desenha cada barra individualmente.
        for indice in range(
            -5,
            6,
        ):
            # Converte o índice em uma proporção entre valores negativos e positivos.
            proporcao = (
                indice / 6.0
            )

            y = (
                centro.y()
                + proporcao * raio
            )

            # Calcula a largura da linha com base na curvatura da esfera.
            largura_linha = (
                raio
                * math.sqrt(
                    max(
                        0.0,
                        1.0
                        - proporcao
                        * proporcao,
                    )
                )
            )

            # Define uma altura mínima para a curva.
            altura_curva = max(
                4.0,
                raio * 0.105,
            )

            painter.drawEllipse(
                QRectF(
                    centro.x()
                    - largura_linha,
                    y
                    - altura_curva / 2,
                    largura_linha * 2,
                    altura_curva,
                )
            )

        # ====================================================
        # LINHAS VERTICAIS MAIS PRÓXIMAS DA ESFERA
        # ====================================================

        # Desenha cada barra individualmente.
        for indice in range(
            -5,
            6,
        ):
            # Converte o índice em uma proporção entre valores negativos e positivos.
            proporcao = (
                indice / 6.0
            )

            # Antes as linhas se afastavam muito nas laterais.
            # Agora ficam mais próximas da superfície circular.
            # Calcula a largura das elipses verticais.
            largura_curva = (
                raio
                * 2
                * (
                    0.10
                    + 0.72
                    * (
                        1.0
                        - abs(
                            proporcao
                        )
                    )
                )
            )

            # Desloca cada curva vertical horizontalmente.
            deslocamento = (
                proporcao
                * raio
                * 0.58
            )

            painter.drawEllipse(
                QRectF(
                    centro.x()
                    - largura_curva / 2
                    + deslocamento,
                    centro.y()
                    - raio * 0.985,
                    largura_curva,
                    raio * 1.97,
                )
            )

        # ====================================================
        # CÍRCULO CENTRAL
        # ====================================================

        # Cria o brilho do núcleo central.
        nucleo = QRadialGradient(
            centro,
            raio * 0.27,
        )

        nucleo.setColorAt(
            0.0,
            QColor(
                225,
                240,
                255,
                220,
            ),
        )

        nucleo.setColorAt(
            0.18,
            QColor(
                70,
                170,
                255,
                195,
            ),
        )

        nucleo.setColorAt(
            1.0,
            QColor(
                20,
                90,
                180,
                0,
            ),
        )

        # Define a cor do texto.
        painter.setPen(
            Qt.NoPen
        )

        # Configura o preenchimento usado nos próximos desenhos.
        painter.setBrush(
            nucleo
        )

        # Desenha uma elipse usando as dimensões informadas.
        painter.drawEllipse(
            centro,
            raio * 0.27,
            raio * 0.27,
        )

        # Finaliza o QPainter e libera os recursos.
        painter.end()

        return pixmap

    # ========================================================
    # DESENHO PRINCIPAL
    # ========================================================

    # Método principal de pintura do widget.
    # É chamado pelo Qt sempre que o componente precisa ser redesenhado.
    def paintEvent(self, event):
        # Verifica condições antes de continuar.
        if (
            self.cache_fundo.isNull()
            or self.cache_esfera.isNull()
        ):
            # Garante que os caches existam antes de desenhar.
            self._recriar_cache()

        # Obtém a largura atual do widget.
        largura = self.width()
        # Obtém a altura atual do widget.
        altura = self.height()

        # Cria o pintor diretamente sobre o widget.
        painter = QPainter(
            self
        )

        # Ativa antialiasing para deixar curvas suaves.
        painter.setRenderHint(
            QPainter.Antialiasing,
            True,
        )

        # Desenha um pixmap já armazenado em cache.
        painter.drawPixmap(
            0,
            0,
            self.cache_fundo,
        )

        # Desenha um pixmap já armazenado em cache.
        painter.drawPixmap(
            0,
            0,
            self.cache_esfera,
        )

        # Calcula o tempo decorrido desde o início.
        tempo = (
            time.monotonic()
            - self.tempo_inicial
        )

        # Define o centro visual do gradiente.
        centro = QPointF(
            largura * 0.50,
            altura * 0.49,
        )

        # Calcula o raio com base no menor lado disponível.
        # Isso mantém a esfera proporcional.
        raio = min(
            largura,
            altura,
        ) * 0.245

        # Desenha o brilho que reage ao áudio.
        self._desenhar_brilho_reativo(
            painter,
            centro,
            raio,
        )

        # Desenha os dois anéis animados.
        self._desenhar_aneis(
            painter,
            centro,
            raio,
            tempo,
        )

        # Desenha as barras inferiores de áudio.
        self._desenhar_indicador_audio(
            painter,
            largura,
            altura,
            tempo,
        )

        # Desenha o título e o status.
        self._desenhar_textos(
            painter,
            largura,
            altura,
        )

        # Finaliza o QPainter e libera os recursos.
        painter.end()

    # ========================================================
    # BRILHO REATIVO
    # ========================================================

    # Desenha um halo adicional baseado no volume da voz.
    def _desenhar_brilho_reativo(
        self,
        painter,
        centro,
        raio,
    ):
        # Evita desenhar quando a intensidade é muito baixa.
        if self.nivel_suavizado < 0.015:
            return

        # Usa o nível suavizado como intensidade visual.
        intensidade = (
            self.nivel_suavizado
        )

        # Aumenta o tamanho do halo conforme o áudio.
        raio_brilho = (
            raio
            * (
                1.06
                + intensidade * 0.20
            )
        )

        # Cria o gradiente do brilho reativo.
        brilho = QRadialGradient(
            centro,
            raio_brilho,
        )

        brilho.setColorAt(
            0.56,
            QColor(
                60,
                160,
                255,
                int(
                    18
                    + intensidade * 58
                ),
            ),
        )

        brilho.setColorAt(
            1.0,
            QColor(
                60,
                160,
                255,
                0,
            ),
        )

        # Define a cor do texto.
        painter.setPen(
            Qt.NoPen
        )

        # Configura o preenchimento usado nos próximos desenhos.
        painter.setBrush(
            brilho
        )

        # Desenha uma elipse usando as dimensões informadas.
        painter.drawEllipse(
            centro,
            raio_brilho,
            raio_brilho,
        )

    # ========================================================
    # DOIS ANÉIS ANIMADOS
    # ========================================================

    # Desenha dois anéis pontilhados animados ao redor da esfera.
    def _desenhar_aneis(
        self,
        painter,
        centro,
        raio,
        tempo,
    ):
        # Configura o preenchimento usado nos próximos desenhos.
        painter.setBrush(
            Qt.NoBrush
        )

        # Aumenta a velocidade aparente conforme o nível de áudio.
        energia = (
            1.0
            + self.nivel_suavizado
            * 0.65
        )

        # O terceiro e maior círculo foi removido.
        # Cada tupla define:
        # escala, achatamento, velocidade e transparência.
        dados_aneis = [
            (
                1.12,
                0.48,
                16.0,
                125,
            ),
            (
                1.32,
                0.66,
                -10.0,
                85,
            ),
        ]

        # Percorre as configurações dos anéis.
        for (
            escala,
            achatamento,
            velocidade,
            alpha,
        ) in dados_aneis:

            # Calcula a largura do anel.
            largura_anel = (
                raio
                * 2
                * escala
            )

            # Calcula a altura usando o fator de achatamento.
            altura_anel = (
                largura_anel
                * achatamento
            )

            # Define o retângulo que limita a elipse.
            retangulo = QRectF(
                centro.x()
                - largura_anel / 2,
                centro.y()
                - altura_anel / 2,
                largura_anel,
                altura_anel,
            )

            # Ajusta a transparência conforme o áudio.
            alpha_final = min(
                220,
                alpha
                + int(
                    self.nivel_suavizado
                    * 75
                ),
            )

            # Cria a caneta usada para desenhar o anel.
            caneta = QPen(
                QColor(
                    60,
                    160,
                    255,
                    alpha_final,
                ),
                1.1
                + self.nivel_suavizado
                * 1.4,
            )

            # Define o padrão pontilhado da linha.
            caneta.setDashPattern(
                [
                    9.0,
                    7.0,
                ]
            )

            # Move o padrão pontilhado ao longo do tempo,
            # criando a sensação de rotação.
            caneta.setDashOffset(
                tempo
                * velocidade
                * energia
            )

            painter.setPen(
                caneta
            )

            painter.drawEllipse(
                retangulo
            )

    # ========================================================
    # INDICADOR DE ÁUDIO
    # ========================================================

    # Desenha as barras que representam o áudio.
    def _desenhar_indicador_audio(
        self,
        painter,
        largura,
        altura,
        tempo,
    ):
        # Número total de barras.
        quantidade = 24

        # Limita a largura total do indicador.
        largura_total = min(
            largura * 0.42,
            420,
        )

        inicio_x = (
            largura
            - largura_total
        ) / 2

        base_y = (
            altura * 0.89
        )

        # Calcula o espaço disponível para cada barra.
        espaco = (
            largura_total
            / quantidade
        )

        # Define a altura máxima proporcional à janela.
        altura_maxima = (
            altura * 0.08
        )

        # Define a cor do texto.
        painter.setPen(
            Qt.NoPen
        )

        # Desenha cada barra individualmente.
        for indice in range(
            quantidade
        ):
            # Mede a distância da barra até o centro.
            distancia_centro = abs(
                indice
                - (
                    quantidade - 1
                ) / 2
            )

            # Faz as barras centrais reagirem mais que as laterais.
            fator_centro = max(
                0.15,
                1.0
                - distancia_centro
                / (
                    quantidade / 2
                ),
            )

            # Cria uma oscilação baseada em seno.
            movimento = (
                math.sin(
                    tempo * 5.0
                    + indice * 0.58
                )
                + 1.0
            ) * 0.5

            # Combina nível de áudio, posição e movimento.
            valor = (
                0.05
                + self.nivel_suavizado
                * fator_centro
                * (
                    0.45
                    + movimento * 0.55
                )
            )

            # Calcula a altura final da barra.
            altura_barra = max(
                2.0,
                altura_maxima * valor,
            )

            largura_barra = max(
                2.0,
                espaco * 0.28,
            )

            # Ajusta a transparência conforme o áudio.
            alpha = int(
                55
                + self.nivel_suavizado
                * 180
            )

            painter.setBrush(
                QColor(
                    60,
                    160,
                    255,
                    alpha,
                )
            )

            x = (
                inicio_x
                + indice * espaco
            )

            # Desenha a barra com cantos arredondados.
            painter.drawRoundedRect(
                QRectF(
                    x,
                    base_y
                    - altura_barra,
                    largura_barra,
                    altura_barra,
                ),
                largura_barra / 2,
                largura_barra / 2,
            )

    # ========================================================
    # TEXTOS
    # ========================================================

    # Desenha o título SOFTIA e o status atual.
    def _desenhar_textos(
        self,
        painter,
        largura,
        altura,
    ):
        # Cria a fonte usada no título.
        fonte_titulo = QFont(
            "Segoe UI",
            19,
        )

        # Define o peso visual da fonte.
        fonte_titulo.setWeight(
            QFont.DemiBold
        )

        # Aumenta o espaçamento entre as letras.
        fonte_titulo.setLetterSpacing(
            QFont.AbsoluteSpacing,
            5,
        )

        # Aplica a fonte ao pintor.
        painter.setFont(
            fonte_titulo
        )

        # Define a cor do texto.
        painter.setPen(
            QColor(
                245,
                238,
                240,
                235,
            )
        )

        # O título usa exatamente o mesmo centro da esfera.
        # Desenha um texto dentro de um retângulo.
        painter.drawText(
            QRectF(
                0,
                altura * 0.07,
                largura,
                40,
            ),
            Qt.AlignCenter,
            self.nome_exibido,
        )

        # Cria a fonte usada no status.
        fonte_status = QFont(
            "Consolas",
            9,
        )

        fonte_status.setLetterSpacing(
            QFont.AbsoluteSpacing,
            1.5,
        )

        # Aplica a fonte ao pintor.
        painter.setFont(
            fonte_status
        )

        # Define cor e símbolo quando o SOFTIA está ativo.
        if self.ativo:
            cor = QColor(
                70,
                170,
                255,
                220,
            )

            simbolo = "●"

        # Define cor e símbolo quando está offline.
        else:
            cor = QColor(
                135,
                135,
                142,
                175,
            )

            simbolo = "○"

        # Define a cor do texto.
        painter.setPen(
            cor
        )

        # Desenha um texto dentro de um retângulo.
        painter.drawText(
            QRectF(
                0,
                altura * 0.135,
                largura,
                28,
            ),
            Qt.AlignCenter,
            f"{simbolo}  {self.status}",
        )
