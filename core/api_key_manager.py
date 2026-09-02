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

# Valores usados quando o usuário ainda não configurou estas opções
# (instalações novas) ou quando o config.json é de uma versão anterior
# do SOFTIA que ainda não tinha estes campos (instalações antigas).
NOME_ASSISTENTE_PADRAO = "SOFTIA"
VOZ_GENERO_PADRAO = "feminina"
SENHA_PADRAO = "Romeu"


def _ler_config_bruto():
    """
    Lê o conteúdo bruto do config.json salvo localmente.

    Retorna um dicionário vazio caso o arquivo não exista,
    esteja corrompido ou não contenha um objeto JSON válido.
    """

    if not ARQUIVO_CONFIG.exists():
        return {}

    try:
        conteudo = ARQUIVO_CONFIG.read_text(
            encoding="utf-8"
        )
        dados = json.loads(
            conteudo
        )

    except (OSError, json.JSONDecodeError):
        return {}

    return dados if isinstance(dados, dict) else {}


def carregar_configuracoes():
    """
    Lê todas as configurações do SOFTIA salvas neste computador:
    chave de API, nome da assistente, gênero da voz e senha de
    autenticação.

    Aplica valores padrão para qualquer campo ausente, o que também
    mantém instalações antigas (de antes destas opções existirem)
    funcionando exatamente como antes, sem pedir reconfiguração.
    """

    dados = _ler_config_bruto()

    voz_genero = dados.get("voz_genero")
    if voz_genero not in ("feminina", "masculina"):
        voz_genero = VOZ_GENERO_PADRAO

    return {
        "gemini_api_key": str(
            dados.get("gemini_api_key", "")
        ).strip(),
        "nome_assistente": str(
            dados.get("nome_assistente", "")
        ).strip() or NOME_ASSISTENTE_PADRAO,
        "voz_genero": voz_genero,
        "senha_ativada": bool(
            dados.get("senha_ativada", True)
        ),
        "senha": str(
            dados.get("senha", "")
        ).strip() or SENHA_PADRAO,
    }


def salvar_configuracoes(novas_configuracoes):
    """
    Salva as configurações informadas neste computador, mesclando com
    o que já estava salvo (para não apagar campos não enviados desta vez).

    Retorna o dicionário completo já salvo, com os padrões aplicados.
    """

    atuais = carregar_configuracoes()

    atuais.update(
        {
            chave: valor
            for chave, valor in novas_configuracoes.items()
            if valor is not None
        }
    )

    PASTA_CONFIG.mkdir(
        parents=True,
        exist_ok=True,
    )

    ARQUIVO_CONFIG.write_text(
        json.dumps(
            atuais,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return atuais


def garantir_chave_api():
    """
    Garante que GEMINI_API_KEY esteja disponível antes de qualquer
    outro módulo do SOFTIA ser carregado.

    Ordem de prioridade:
    1. Variável de ambiente já definida (ex: .env usado em desenvolvimento);
    2. Chave salva localmente em uma execução anterior deste instalador;
    3. Nenhuma chave encontrada — quem chamou esta função deve pedir
       a chave ao usuário e, em seguida, chamar salvar_configuracoes().

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

    chave_salva = carregar_configuracoes()["gemini_api_key"]

    if chave_salva:
        # Disponibiliza a chave para os demais módulos do SOFTIA,
        # que leem GEMINI_API_KEY diretamente do ambiente.
        os.environ["GEMINI_API_KEY"] = chave_salva
        return chave_salva

    return ""
