# json permite salvar e ler a chave de API em um arquivo local.
import json
# os é usado para acessar variáveis de ambiente,
# como a pasta AppData do Windows.
import os
# Path facilita a criação e manipulação de caminhos de arquivos e pastas.
from pathlib import Path

# load_dotenv permite que desenvolvedores continuem usando um arquivo
# .env na pasta do projeto durante os testes, sem precisar passar
# pela janela de configuração a cada execução.
from dotenv import load_dotenv


# Pasta onde a chave de cada usuário fica salva neste computador.
# Usar AppData evita depender de permissão de escrita dentro da
# pasta de instalação do programa (ex: Arquivos de Programas).
PASTA_CONFIG = Path(
    os.getenv(
        "APPDATA",
        str(Path.home()),
    )
) / "SoftIA"

ARQUIVO_CONFIG = PASTA_CONFIG / "config.json"


def carregar_chave_salva():
    """
    Lê a chave de API salva localmente em uma execução anterior.

    Retorna uma string vazia caso o arquivo não exista,
    esteja corrompido ou não contenha uma chave válida.
    """

    if not ARQUIVO_CONFIG.exists():
        return ""

    try:
        conteudo = ARQUIVO_CONFIG.read_text(
            encoding="utf-8"
        )
        dados = json.loads(
            conteudo
        )

    except (OSError, json.JSONDecodeError):
        return ""

    if not isinstance(dados, dict):
        return ""

    return str(
        dados.get(
            "gemini_api_key",
            "",
        )
    ).strip()


def salvar_chave(chave):
    """
    Salva a chave de API informada pelo usuário neste computador,
    para que ele não precise digitá-la novamente nas próximas vezes.
    """

    chave = str(chave or "").strip()

    PASTA_CONFIG.mkdir(
        parents=True,
        exist_ok=True,
    )

    ARQUIVO_CONFIG.write_text(
        json.dumps(
            {
                "gemini_api_key": chave,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def garantir_chave_api():
    """
    Garante que GEMINI_API_KEY esteja disponível antes de qualquer
    outro módulo do SOFTIA ser carregado.

    Ordem de prioridade:
    1. Variável de ambiente já definida (ex: .env usado em desenvolvimento);
    2. Chave salva localmente em uma execução anterior deste instalador;
    3. Nenhuma chave encontrada — quem chamou esta função deve pedir
       a chave ao usuário e, em seguida, chamar salvar_chave().

    Retorna a chave encontrada, ou uma string vazia se nenhuma existir.
    """

    # Permite que o .env do ambiente de desenvolvimento continue
    # funcionando normalmente, sem exibir a janela de configuração.
    load_dotenv()

    chave_ambiente = os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()

    if chave_ambiente:
        return chave_ambiente

    chave_salva = carregar_chave_salva()

    if chave_salva:
        # Disponibiliza a chave para os demais módulos do SOFTIA,
        # que leem GEMINI_API_KEY diretamente do ambiente.
        os.environ["GEMINI_API_KEY"] = chave_salva
        return chave_salva

    return ""
