# Qt fornece constantes do framework PySide6.
from PySide6.QtCore import Qt
# Componentes visuais usados para montar a janela de configuração inicial.
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


# Janela exibida somente quando nenhuma chave de API do Gemini
# foi encontrada neste computador. Cada usuário cola aqui a própria
# chave, que fica salva localmente para as próximas execuções.
class ApiKeyDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(
            "SOFTIA — Configuração inicial"
        )

        self.setMinimumWidth(440)
        self.setModal(True)

        # Reaproveita a mesma identidade visual escura do restante do app.
        self.setStyleSheet(
            """
            QDialog {
                background-color: #050507;
            }
            QLabel {
                color: #f2f2f4;
                font-family: "Segoe UI";
            }
            QLineEdit {
                min-height: 34px;
                padding: 0 10px;
                color: #f5f5f6;
                background-color: rgba(18, 18, 22, 235);
                border: 1px solid rgba(60, 150, 255, 90);
                border-radius: 8px;
            }
            QPushButton {
                min-height: 38px;
                padding: 0 14px;
                color: #f5f5f6;
                background-color: rgba(18, 18, 22, 235);
                border: 1px solid rgba(60, 150, 255, 75);
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(10, 35, 70, 245);
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(14)

        titulo = QLabel(
            "Bem-vindo ao SOFTIA"
        )
        titulo.setStyleSheet(
            "font-size: 17px; font-weight: 700;"
        )

        instrucao = QLabel(
            "Para começar, cole abaixo a sua chave de API do "
            "Google Gemini. Ela fica salva apenas neste computador "
            "e é usada diretamente na sua própria conta Google.\n\n"
            "Você pode gerar uma chave gratuita em: "
            "aistudio.google.com/apikey"
        )
        instrucao.setWordWrap(True)

        self.campo_chave = QLineEdit()
        self.campo_chave.setEchoMode(
            QLineEdit.Password
        )
        self.campo_chave.setPlaceholderText(
            "Cole aqui sua chave de API"
        )
        # Confirma também ao pressionar Enter no campo de texto.
        self.campo_chave.returnPressed.connect(
            self._confirmar
        )

        self.botao_mostrar = QPushButton(
            "Mostrar chave"
        )
        self.botao_mostrar.setCheckable(True)
        self.botao_mostrar.toggled.connect(
            self._alternar_visibilidade
        )

        self.botao_confirmar = QPushButton(
            "Salvar e continuar"
        )
        self.botao_confirmar.clicked.connect(
            self._confirmar
        )

        layout.addWidget(titulo)
        layout.addWidget(instrucao)
        layout.addWidget(self.campo_chave)
        layout.addWidget(self.botao_mostrar)
        layout.addWidget(self.botao_confirmar)

        # Guarda a chave confirmada para ser lida por quem abriu esta janela.
        self.chave_informada = ""

    # Alterna entre esconder e revelar a chave digitada.
    def _alternar_visibilidade(self, mostrar):
        self.campo_chave.setEchoMode(
            QLineEdit.Normal
            if mostrar
            else QLineEdit.Password
        )

        self.botao_mostrar.setText(
            "Ocultar chave"
            if mostrar
            else "Mostrar chave"
        )

    # Valida o campo e fecha a janela com sucesso quando há uma chave.
    def _confirmar(self):
        chave = self.campo_chave.text().strip()

        if not chave:
            QMessageBox.warning(
                self,
                "Chave obrigatória",
                "Informe uma chave de API válida para continuar.",
            )
            return

        self.chave_informada = chave
        self.accept()
