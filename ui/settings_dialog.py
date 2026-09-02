# Qt fornece constantes do framework PySide6.
from PySide6.QtCore import Qt
# Componentes visuais usados para montar a janela de configurações.
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


# Janela de Configurações do SOFTIA.
# Aparece automaticamente na primeira execução (quando nenhuma chave
# de API foi encontrada) e pode ser reaberta a qualquer momento pelo
# botão "Configurações" da janela principal, para trocar a chave de
# API, o nome da assistente, a voz e a senha de autenticação sem
# precisar reinstalar o programa.
class ConfiguracoesDialog(QDialog):

    def __init__(self, parent=None, configuracoes_atuais=None):
        super().__init__(parent)

        configuracoes_atuais = configuracoes_atuais or {}

        self.setWindowTitle(
            "SOFTIA — Configurações"
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
            QLineEdit, QComboBox {
                min-height: 34px;
                padding: 0 10px;
                color: #f5f5f6;
                background-color: rgba(18, 18, 22, 235);
                border: 1px solid rgba(60, 150, 255, 90);
                border-radius: 8px;
            }
            QCheckBox {
                color: #f2f2f4;
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
        layout.setSpacing(12)

        titulo = QLabel(
            "Bem-vindo ao SOFTIA"
        )
        titulo.setStyleSheet(
            "font-size: 17px; font-weight: 700;"
        )

        instrucao = QLabel(
            "Cole abaixo a sua chave de API do Google Gemini. Ela fica "
            "salva apenas neste computador e é usada diretamente na sua "
            "própria conta Google.\n\n"
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
        self.campo_chave.setText(
            configuracoes_atuais.get("gemini_api_key", "")
        )

        self.botao_mostrar_chave = QPushButton(
            "Mostrar chave"
        )
        self.botao_mostrar_chave.setCheckable(True)
        self.botao_mostrar_chave.toggled.connect(
            self._alternar_visibilidade_chave
        )

        # ====================================================
        # NOME DA ASSISTENTE
        # ====================================================
        rotulo_nome = QLabel(
            "Nome da assistente"
        )

        self.campo_nome = QLineEdit()
        self.campo_nome.setPlaceholderText(
            "SOFTIA"
        )
        self.campo_nome.setText(
            configuracoes_atuais.get(
                "nome_assistente",
                "SOFTIA",
            )
        )

        # ====================================================
        # VOZ
        # ====================================================
        rotulo_voz = QLabel(
            "Voz da assistente"
        )

        self.combo_voz = QComboBox()
        self.combo_voz.addItem(
            "Feminina",
            "feminina",
        )
        self.combo_voz.addItem(
            "Masculina",
            "masculina",
        )

        if configuracoes_atuais.get("voz_genero") == "masculina":
            self.combo_voz.setCurrentIndex(1)

        # ====================================================
        # SENHA DE AUTENTICAÇÃO
        # ====================================================
        self.check_usar_senha = QCheckBox(
            "Pedir senha antes de liberar comandos"
        )
        self.check_usar_senha.setChecked(
            configuracoes_atuais.get(
                "senha_ativada",
                True,
            )
        )
        self.check_usar_senha.toggled.connect(
            self._alternar_campo_senha
        )

        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(
            QLineEdit.Password
        )
        self.campo_senha.setPlaceholderText(
            "Digite a senha que a assistente vai pedir"
        )
        self.campo_senha.setText(
            configuracoes_atuais.get("senha", "")
        )

        self.botao_confirmar = QPushButton(
            "Salvar"
        )
        self.botao_confirmar.clicked.connect(
            self._confirmar
        )

        layout.addWidget(titulo)
        layout.addWidget(instrucao)
        layout.addWidget(self.campo_chave)
        layout.addWidget(self.botao_mostrar_chave)
        layout.addSpacing(8)
        layout.addWidget(rotulo_nome)
        layout.addWidget(self.campo_nome)
        layout.addWidget(rotulo_voz)
        layout.addWidget(self.combo_voz)
        layout.addWidget(self.check_usar_senha)
        layout.addWidget(self.campo_senha)
        layout.addWidget(self.botao_confirmar)

        # Aplica o estado inicial do campo de senha conforme o checkbox.
        self._alternar_campo_senha(
            self.check_usar_senha.isChecked()
        )

        # Confirma também ao pressionar Enter em qualquer campo de texto.
        self.campo_chave.returnPressed.connect(self._confirmar)
        self.campo_nome.returnPressed.connect(self._confirmar)
        self.campo_senha.returnPressed.connect(self._confirmar)

        # Guarda as configurações confirmadas para serem lidas por
        # quem abriu esta janela.
        self.configuracoes_confirmadas = {}

    # Alterna entre esconder e revelar a chave digitada.
    def _alternar_visibilidade_chave(self, mostrar):
        self.campo_chave.setEchoMode(
            QLineEdit.Normal
            if mostrar
            else QLineEdit.Password
        )

        self.botao_mostrar_chave.setText(
            "Ocultar chave"
            if mostrar
            else "Mostrar chave"
        )

    # Habilita ou desabilita o campo de senha conforme o checkbox.
    def _alternar_campo_senha(self, usar_senha):
        self.campo_senha.setEnabled(
            usar_senha
        )

        self.campo_senha.setVisible(
            usar_senha
        )

    # Valida os campos e fecha a janela com sucesso quando tudo é válido.
    def _confirmar(self):
        chave = self.campo_chave.text().strip()

        if not chave:
            QMessageBox.warning(
                self,
                "Chave obrigatória",
                "Informe uma chave de API válida para continuar.",
            )
            return

        nome_assistente = self.campo_nome.text().strip() or "SOFTIA"

        usar_senha = self.check_usar_senha.isChecked()
        senha = self.campo_senha.text().strip()

        if usar_senha and not senha:
            QMessageBox.warning(
                self,
                "Senha obrigatória",
                "Informe a senha que a assistente vai pedir, "
                "ou desmarque a opção de usar senha.",
            )
            return

        self.configuracoes_confirmadas = {
            "gemini_api_key": chave,
            "nome_assistente": nome_assistente,
            "voz_genero": self.combo_voz.currentData(),
            "senha_ativada": usar_senha,
            "senha": senha,
        }

        self.accept()
