"""
Pesquisa invisível e seletiva de informações atuais para o SOFTIA.

O módulo possui duas etapas:

1. Filtro local extremamente rápido:
   decide se a pergunta realmente depende de dados atuais.

2. Pesquisa invisível:
   acessa resultados atuais somente quando necessário.

Não abre abas, não exibe janelas e não interfere no foco do usuário.
"""

from __future__ import annotations

import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Any


# ============================================================
# CONFIGURAÇÕES
# ============================================================

MAXIMO_RESULTADOS = 5
MAXIMO_CARACTERES = 5000
TEMPO_CACHE_SEGUNDOS = 60
REGIAO_PADRAO = "br-pt"

# "auto" permite que a biblioteca escolha um mecanismo disponível.
MECANISMO_PESQUISA = "auto"

_LOCK_CACHE = threading.Lock()
_CACHE: dict[str, tuple[float, str]] = {}


# ============================================================
# REGRAS DO FILTRO HÍBRIDO
# ============================================================

# Termos que normalmente indicam necessidade de informação atual.
MARCADORES_ATUALIDADE = (
    "hoje",
    "agora",
    "neste momento",
    "nesse momento",
    "atualmente",
    "atual",
    "atualizado",
    "atualizada",
    "recentemente",
    "recente",
    "ontem",
    "amanha",
    "esta semana",
    "nesta semana",
    "este mes",
    "neste mes",
    "este ano",
    "neste ano",
    "ultimas horas",
    "ultimos dias",
    "ultima noticia",
    "ultimas noticias",
    "mais recente",
    "ao vivo",
)

# Assuntos que mudam frequentemente e geralmente exigem consulta,
# mesmo quando o usuário não fala explicitamente "hoje".
ASSUNTOS_DINAMICOS = (
    "cotacao",
    "dolar",
    "euro",
    "bitcoin",
    "criptomoeda",
    "bolsa de valores",
    "acao da",
    "acoes da",
    "preco da gasolina",
    "preco do combustivel",
    "previsao do tempo",
    "temperatura em",
    "clima em",
    "noticia",
    "noticias",
    "placar",
    "resultado do jogo",
    "proximo jogo",
    "proxima partida",
    "quando joga",
    "vai jogar",
    "joga hoje",
    "classificacao do campeonato",
    "tabela do campeonato",
    "horario do jogo",
    "lancamento",
    "ultima versao",
    "versao mais recente",
)

# Cargos ou posições que podem mudar.
CARGOS_ATUAIS = (
    "presidente do brasil",
    "presidente dos estados unidos",
    "presidente da",
    "governador de",
    "prefeito de",
    "primeiro ministro",
    "ministro da",
    "ministro do",
    "ceo da",
    "ceo do",
    "diretor da",
    "tecnico do",
    "treinador do",
)

# Perguntas tipicamente estáveis. Elas não devem pesquisar,
# a menos que também tragam um marcador atual explícito.
PADROES_ESTAVEIS = (
    "o que e ",
    "o que significa ",
    "explique ",
    "me explique ",
    "como funciona ",
    "quem foi ",
    "historia de ",
    "definicao de ",
    "conceito de ",
    "para que serve ",
    "qual a diferenca entre ",
    "como aprender ",
    "como criar ",
    "linguagem de programacao",
)


@dataclass(frozen=True)
class ResultadoPesquisa:
    titulo: str
    descricao: str
    url: str


@dataclass(frozen=True)
class DecisaoPesquisa:
    pesquisar: bool
    motivo: str


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def _normalizar_consulta(consulta: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(consulta or ""),
    ).strip()


def _normalizar_para_comparacao(texto: str) -> str:
    texto = _normalizar_consulta(
        texto
    ).casefold()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(
            caractere
        ) != "Mn"
    )

    return texto


# ============================================================
# FILTRO LOCAL
# ============================================================

def avaliar_necessidade_pesquisa(
    consulta: str,
) -> DecisaoPesquisa:
    """
    Decide em microssegundos se uma consulta precisa da internet.

    A ordem é importante:
    1. marcadores atuais explícitos;
    2. assuntos dinâmicos;
    3. cargos atuais;
    4. perguntas estáveis;
    5. caso ambíguo: não pesquisar automaticamente.
    """

    consulta_limpa = _normalizar_consulta(
        consulta
    )

    if not consulta_limpa:
        return DecisaoPesquisa(
            pesquisar=False,
            motivo="consulta vazia",
        )

    texto = _normalizar_para_comparacao(
        consulta_limpa
    )

    for marcador in MARCADORES_ATUALIDADE:
        if marcador in texto:
            return DecisaoPesquisa(
                pesquisar=True,
                motivo=(
                    f"marcador de atualidade detectado: {marcador}"
                ),
            )

    for assunto in ASSUNTOS_DINAMICOS:
        if assunto in texto:
            return DecisaoPesquisa(
                pesquisar=True,
                motivo=(
                    f"assunto dinâmico detectado: {assunto}"
                ),
            )

    for cargo in CARGOS_ATUAIS:
        if cargo in texto:
            return DecisaoPesquisa(
                pesquisar=True,
                motivo=(
                    f"cargo atual detectado: {cargo}"
                ),
            )

    for padrao in PADROES_ESTAVEIS:
        if texto.startswith(padrao) or padrao in texto:
            return DecisaoPesquisa(
                pesquisar=False,
                motivo=(
                    f"pergunta de conhecimento estável: {padrao.strip()}"
                ),
            )

    return DecisaoPesquisa(
        pesquisar=False,
        motivo=(
            "não há indicação suficiente de que a informação "
            "dependa de dados atuais"
        ),
    )


def precisa_pesquisar(
    consulta: str,
) -> bool:
    """
    Atalho booleano usado pelo live_client.py.
    """

    return avaliar_necessidade_pesquisa(
        consulta
    ).pesquisar


def resposta_sem_pesquisa(
    consulta: str,
) -> str:
    """
    Resposta devolvida ao Gemini quando ele chama a ferramenta
    desnecessariamente.
    """

    decisao = avaliar_necessidade_pesquisa(
        consulta
    )

    return (
        "PESQUISA NA INTERNET NÃO NECESSÁRIA. "
        f"Motivo: {decisao.motivo}. "
        "Responda diretamente usando seu conhecimento interno, "
        "sem chamar novamente esta ferramenta para o mesmo pedido."
    )


# ============================================================
# CACHE
# ============================================================

def _chave_cache(consulta: str) -> str:
    return _normalizar_para_comparacao(
        consulta
    )


def _ler_cache(consulta: str) -> str | None:
    chave = _chave_cache(
        consulta
    )
    agora = time.monotonic()

    with _LOCK_CACHE:
        item = _CACHE.get(
            chave
        )

        if item is None:
            return None

        criado_em, resultado = item

        if (
            agora - criado_em
            > TEMPO_CACHE_SEGUNDOS
        ):
            _CACHE.pop(
                chave,
                None,
            )
            return None

        return resultado


def _salvar_cache(
    consulta: str,
    resultado: str,
) -> None:
    chave = _chave_cache(
        consulta
    )

    with _LOCK_CACHE:
        _CACHE[chave] = (
            time.monotonic(),
            resultado,
        )

        if len(_CACHE) > 50:
            mais_antigos = sorted(
                _CACHE.items(),
                key=lambda item: item[1][0],
            )[:10]

            for chave_antiga, _ in mais_antigos:
                _CACHE.pop(
                    chave_antiga,
                    None,
                )


# ============================================================
# CONVERSÃO DOS RESULTADOS
# ============================================================

def _limpar_campo(valor: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(valor or ""),
    ).strip()


def _converter_resultados(
    resultados_brutos: list[dict[str, Any]],
) -> list[ResultadoPesquisa]:
    resultados: list[ResultadoPesquisa] = []

    for item in resultados_brutos:
        if not isinstance(item, dict):
            continue

        titulo = _limpar_campo(
            item.get("title")
        )

        descricao = _limpar_campo(
            item.get("body")
            or item.get("description")
            or item.get("snippet")
        )

        url = _limpar_campo(
            item.get("href")
            or item.get("url")
        )

        if not titulo and not descricao:
            continue

        resultados.append(
            ResultadoPesquisa(
                titulo=(
                    titulo
                    or "Resultado sem título"
                ),
                descricao=(
                    descricao
                    or "Sem descrição disponível."
                ),
                url=url,
            )
        )

        if (
            len(resultados)
            >= MAXIMO_RESULTADOS
        ):
            break

    return resultados


def _formatar_resultados(
    consulta: str,
    resultados: list[ResultadoPesquisa],
) -> str:
    if not resultados:
        return (
            "Não encontrei resultados suficientes para confirmar "
            f"a informação atual sobre: {consulta}. "
            "Diga ao usuário que não foi possível confirmar o dado."
        )

    linhas = [
        f"RESULTADOS ATUAIS DA INTERNET PARA: {consulta}",
        (
            "Use os resultados abaixo como fonte atual. "
            "Compare datas, horários e fontes antes de responder. "
            "Não invente informações que não estejam nos resultados."
        ),
        "",
    ]

    for indice, resultado in enumerate(
        resultados,
        start=1,
    ):
        linhas.append(
            f"{indice}. {resultado.titulo}"
        )
        linhas.append(
            f"Resumo: {resultado.descricao}"
        )

        if resultado.url:
            linhas.append(
                f"Fonte: {resultado.url}"
            )

        linhas.append("")

    texto = "\n".join(
        linhas
    ).strip()

    return texto[
        :MAXIMO_CARACTERES
    ]


# ============================================================
# PESQUISA PRINCIPAL
# ============================================================

def pesquisar_informacao_atual(
    consulta: str,
) -> str:
    """
    Pesquisa apenas quando o filtro local confirmar
    que a pergunta depende de informação atual.
    """

    consulta = _normalizar_consulta(
        consulta
    )

    if not consulta:
        return (
            "A pesquisa não foi realizada porque "
            "nenhuma consulta foi informada."
        )

    decisao = avaliar_necessidade_pesquisa(
        consulta
    )

    if not decisao.pesquisar:
        return resposta_sem_pesquisa(
            consulta
        )

    resultado_cache = _ler_cache(
        consulta
    )

    if resultado_cache is not None:
        return (
            resultado_cache
            + "\n\nResultado reutilizado do cache local recente."
        )

    try:
        from ddgs import DDGS

    except ImportError:
        return (
            "O módulo de pesquisa ainda não está instalado. "
            "No terminal do ambiente virtual, execute: "
            "python -m pip install ddgs"
        )

    argumentos = {
        "region": REGIAO_PADRAO,
        "safesearch": "moderate",
        "max_results": MAXIMO_RESULTADOS,
    }

    # Algumas versões da biblioteca aceitam backend="auto";
    # outras já usam o modo automático por padrão.
    if MECANISMO_PESQUISA != "auto":
        argumentos["backend"] = MECANISMO_PESQUISA

    try:
        resultados_brutos = list(
            DDGS().text(
                consulta,
                **argumentos,
            )
        )

    except Exception as erro:
        return (
            "Não foi possível consultar informações atuais neste momento. "
            f"Detalhes técnicos: {type(erro).__name__}: {erro}"
        )

    resultados = _converter_resultados(
        resultados_brutos
    )

    texto = _formatar_resultados(
        consulta,
        resultados,
    )

    _salvar_cache(
        consulta,
        texto,
    )

    return texto