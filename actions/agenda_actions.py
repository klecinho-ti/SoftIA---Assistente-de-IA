import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from threading import Lock


# Pasta local do usuário (AppData), fora da pasta de instalação
# do programa. Isso garante que a agenda sobreviva a uma
# atualização ou reinstalação do SOFTIA no mesmo computador.
PASTA_MEMORIA = Path(
    os.getenv(
        "APPDATA",
        str(Path.home()),
    )
) / "SoftIA"

ARQUIVO_AGENDA = PASTA_MEMORIA / "agenda.json"

# Local onde versões antigas do SOFTIA salvavam o agenda.json,
# dentro da própria pasta de instalação. Mantido apenas para
# migrar automaticamente compromissos já existentes.
_ARQUIVO_AGENDA_ANTIGO = (
    Path(__file__).resolve().parent.parent / "memory" / "agenda.json"
)

MAXIMO_EVENTOS = 20

_LOCK = Lock()


def _migrar_agenda_antiga_se_necessario():
    """
    Copia um agenda.json de uma versão antiga do SOFTIA (salvo
    dentro da pasta do programa) para a nova pasta em AppData,
    apenas na primeira execução após a atualização.
    """

    if ARQUIVO_AGENDA.exists():
        return

    if not _ARQUIVO_AGENDA_ANTIGO.exists():
        return

    try:
        PASTA_MEMORIA.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            _ARQUIVO_AGENDA_ANTIGO,
            ARQUIVO_AGENDA,
        )

    except OSError:
        pass


def _dados_vazios():
    return {
        "versao": 1,
        "eventos": [],
    }


def _interpretar_data_hora(valor):
    valor = re.sub(
        r"\s+",
        " ",
        str(valor or ""),
    ).strip()

    formatos = (
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
    )

    for formato in formatos:
        try:
            return datetime.strptime(
                valor,
                formato,
            )
        except ValueError:
            continue

    return None


def _salvar_dados(dados):
    """
    Grava agenda.json de forma segura.

    A gravação é feita primeiro em agenda.tmp.
    Somente depois o temporário substitui o JSON principal.
    """

    PASTA_MEMORIA.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporario = ARQUIVO_AGENDA.with_suffix(
        ".tmp"
    )

    try:
        with temporario.open(
            "w",
            encoding="utf-8",
        ) as arquivo:
            json.dump(
                dados,
                arquivo,
                ensure_ascii=False,
                indent=2,
            )

            arquivo.flush()

            try:
                import os
                os.fsync(
                    arquivo.fileno()
                )
            except OSError:
                pass

        temporario.replace(
            ARQUIVO_AGENDA
        )

    except OSError as erro:
        if temporario.exists():
            try:
                temporario.unlink()
            except OSError:
                pass

        raise OSError(
            f"Não foi possível salvar a agenda em: {ARQUIVO_AGENDA}"
        ) from erro


def _criar_arquivo_se_necessario():
    """
    Cria automaticamente a pasta memory e o agenda.json.

    Também corrige automaticamente:
    - arquivo vazio;
    - JSON inválido;
    - estrutura que não seja um dicionário;
    - chave eventos ausente ou inválida.
    """

    # Traz compromissos de uma instalação antiga, se existirem.
    _migrar_agenda_antiga_se_necessario()

    PASTA_MEMORIA.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not ARQUIVO_AGENDA.exists():
        _salvar_dados(
            _dados_vazios()
        )
        return

    try:
        conteudo = ARQUIVO_AGENDA.read_text(
            encoding="utf-8"
        ).strip()
    except OSError as erro:
        raise OSError(
            f"Não foi possível ler a agenda em: {ARQUIVO_AGENDA}"
        ) from erro

    if not conteudo:
        _salvar_dados(
            _dados_vazios()
        )
        return

    try:
        dados = json.loads(
            conteudo
        )
    except json.JSONDecodeError:
        _salvar_dados(
            _dados_vazios()
        )
        return

    if not isinstance(dados, dict):
        _salvar_dados(
            _dados_vazios()
        )
        return

    if not isinstance(
        dados.get("eventos"),
        list,
    ):
        dados = _dados_vazios()
        _salvar_dados(
            dados
        )


def _carregar_dados():
    """
    Carrega e valida os compromissos.

    Caso o arquivo esteja ausente, vazio ou inválido,
    ele é recriado automaticamente.
    """

    _criar_arquivo_se_necessario()

    try:
        with ARQUIVO_AGENDA.open(
            "r",
            encoding="utf-8",
        ) as arquivo:
            dados = json.load(
                arquivo
            )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        dados = _dados_vazios()
        _salvar_dados(
            dados
        )

    if not isinstance(dados, dict):
        dados = _dados_vazios()

    eventos = dados.get(
        "eventos",
        [],
    )

    if not isinstance(eventos, list):
        eventos = []

    eventos_validos = []

    for evento in eventos:
        if not isinstance(evento, dict):
            continue

        titulo = re.sub(
            r"\s+",
            " ",
            str(
                evento.get(
                    "titulo",
                    "",
                )
            ),
        ).strip()

        data_hora = str(
            evento.get(
                "data_hora",
                "",
            )
        ).strip()

        momento = _interpretar_data_hora(
            data_hora
        )

        if not titulo or momento is None:
            continue

        eventos_validos.append(
            {
                "id": str(
                    evento.get(
                        "id",
                        "",
                    )
                ).strip(),
                "titulo": titulo,
                "data_hora": momento.strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "criado_em": str(
                    evento.get(
                        "criado_em",
                        "",
                    )
                ).strip(),
            }
        )

    dados_tratados = {
        "versao": 1,
        "eventos": eventos_validos[
            -MAXIMO_EVENTOS:
        ],
    }

    # Mantém o arquivo sempre com a estrutura correta.
    if dados != dados_tratados:
        _salvar_dados(
            dados_tratados
        )

    return dados_tratados


def _proximo_id(eventos):
    ids_validos = []

    for evento in eventos:
        try:
            ids_validos.append(
                int(
                    evento.get(
                        "id",
                        0,
                    )
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

    return str(
        max(
            ids_validos,
            default=0,
        ) + 1
    )


def criar_evento_agenda(
    titulo,
    data_hora,
    alarme=False,
):
    """
    Salva um compromisso na agenda local.

    O argumento alarme é mantido apenas por compatibilidade.
    """

    titulo = re.sub(
        r"\s+",
        " ",
        str(titulo or ""),
    ).strip()

    momento = _interpretar_data_hora(
        data_hora
    )

    if not titulo:
        return "Informe o título do compromisso."

    if momento is None:
        return (
            "A data e o horário são inválidos. "
            "Use dia, mês, ano, hora e minuto."
        )

    if momento <= datetime.now():
        return (
            "A data e o horário precisam estar no futuro. "
            "Nenhum compromisso foi salvo."
        )

    data_normalizada = momento.strftime(
        "%Y-%m-%d %H:%M"
    )

    with _LOCK:
        dados = _carregar_dados()
        eventos = dados["eventos"]

        for evento in eventos:
            if (
                evento["titulo"].casefold()
                == titulo.casefold()
                and evento["data_hora"]
                == data_normalizada
            ):
                return (
                    "Esse compromisso já está salvo "
                    "na agenda."
                )

        novo_evento = {
            "id": _proximo_id(
                eventos
            ),
            "titulo": titulo,
            "data_hora": data_normalizada,
            "criado_em": datetime.now().isoformat(
                timespec="seconds"
            ),
        }

        eventos.append(
            novo_evento
        )

        if len(eventos) > MAXIMO_EVENTOS:
            eventos = eventos[
                -MAXIMO_EVENTOS:
            ]

        dados["eventos"] = eventos
        _salvar_dados(
            dados
        )

        quantidade = len(
            eventos
        )

    return (
        f"Compromisso '{titulo}' salvo para "
        f"{momento.strftime('%d/%m/%Y às %H:%M')}. "
        f"A agenda possui {quantidade} de "
        f"{MAXIMO_EVENTOS} compromissos salvos."
    )


def listar_agenda():
    agora = datetime.now()

    with _LOCK:
        dados = _carregar_dados()

    futuros = []

    for evento in dados["eventos"]:
        momento = _interpretar_data_hora(
            evento["data_hora"]
        )

        if momento is None or momento < agora:
            continue

        futuros.append(
            (
                momento,
                evento,
            )
        )

    futuros.sort(
        key=lambda item: item[0]
    )

    if not futuros:
        return "Não há compromissos futuros na agenda."

    linhas = []

    for momento, evento in futuros:
        linhas.append(
            f"{evento['id']}. "
            f"{momento.strftime('%d/%m/%Y às %H:%M')} - "
            f"{evento['titulo']}"
        )

    return (
        "Próximos compromissos:\n"
        + "\n".join(
            linhas
        )
    )


def cancelar_evento_agenda(referencia):
    referencia = re.sub(
        r"\s+",
        " ",
        str(referencia or ""),
    ).strip()

    if not referencia:
        return (
            "Informe o número ou o nome do compromisso "
            "que deseja cancelar."
        )

    with _LOCK:
        dados = _carregar_dados()
        eventos = dados["eventos"]
        candidatos = []

        for evento in eventos:
            if evento["id"] == referencia:
                candidatos = [
                    evento
                ]
                break

            if (
                referencia.casefold()
                in evento["titulo"].casefold()
            ):
                candidatos.append(
                    evento
                )

        if not candidatos:
            return (
                "Não encontrei esse compromisso "
                "na agenda."
            )

        if len(candidatos) > 1:
            opcoes = ", ".join(
                f"{evento['id']} - {evento['titulo']}"
                for evento in candidatos[:8]
            )

            return (
                "Encontrei mais de um compromisso parecido: "
                f"{opcoes}. Informe o número."
            )

        evento_removido = candidatos[0]

        dados["eventos"] = [
            evento
            for evento in eventos
            if evento["id"]
            != evento_removido["id"]
        ]

        _salvar_dados(
            dados
        )

    return (
        f"O compromisso '{evento_removido['titulo']}' "
        "foi cancelado e removido da agenda."
    )


# Inicializa o arquivo automaticamente assim que o módulo é importado.
_criar_arquivo_se_necessario()