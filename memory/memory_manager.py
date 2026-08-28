# json permite ler e gravar dados no formato JSON.
# Neste arquivo, ele é usado para armazenar as memórias
# persistentes do SOFTIA no arquivo memory.json.
import json
# os é usado para acessar a pasta AppData do Windows.
import os
# re fornece expressões regulares.
# Aqui ele é utilizado para remover espaços duplicados
# e padronizar os textos recebidos.
import re
# shutil é usado apenas para migrar automaticamente um
# memory.json salvo pela versão antiga do SOFTIA.
import shutil
# unicodedata permite trabalhar com caracteres Unicode.
# Neste arquivo, ele ajuda a remover acentos durante
# a comparação entre memórias.
import unicodedata

# datetime é utilizado para registrar
# a data e a hora em que cada memória foi criada.
from datetime import datetime
# Path facilita a criação e manipulação
# de caminhos de arquivos e pastas.
from pathlib import Path
# Lock impede que duas operações tentem
# ler ou alterar o arquivo de memória ao mesmo tempo.
from threading import Lock


# Pasta local do usuário (AppData), fora da pasta de instalação
# do programa. Isso garante que as memórias sobrevivam a uma
# atualização ou reinstalação do SOFTIA no mesmo computador.
PASTA_MEMORIA = Path(
    os.getenv(
        "APPDATA",
        str(Path.home()),
    )
) / "SoftIA"

# Monta o caminho completo do arquivo de memória.
ARQUIVO_MEMORIA = PASTA_MEMORIA / "memory.json"

# Local onde versões antigas do SOFTIA salvavam o memory.json,
# dentro da própria pasta de instalação. Mantido apenas para
# migrar automaticamente memórias já existentes de instalações
# anteriores.
_ARQUIVO_MEMORIA_ANTIGO = Path(__file__).resolve().parent / "memory.json"


def _migrar_memoria_antiga_se_necessario():
    """
    Copia um memory.json de uma versão antiga do SOFTIA (salvo
    dentro da pasta do programa) para a nova pasta em AppData,
    apenas na primeira execução após a atualização.
    """

    if ARQUIVO_MEMORIA.exists():
        return

    if not _ARQUIVO_MEMORIA_ANTIGO.exists():
        return

    try:
        PASTA_MEMORIA.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            _ARQUIVO_MEMORIA_ANTIGO,
            ARQUIVO_MEMORIA,
        )

    except OSError:
        pass

# Limites da memória persistente
# Limite máximo de memórias persistentes salvas.
MAXIMO_MEMORIAS = 50
# Limite de caracteres permitido em cada memória.
# Isso mantém as informações curtas e objetivas.
MAXIMO_CARACTERES = 200

# Cria a trava utilizada durante leitura e gravação.
# Essa proteção evita corrupção do arquivo em acessos simultâneos.
_LOCK = Lock()


# Padroniza um texto para facilitar comparações.
# Converte para minúsculas, remove acentos,
# elimina espaços duplicados e limpa as extremidades.
def _normalizar_texto(texto):
    # Converte o valor para texto, remove espaços externos
    # e transforma tudo em letras minúsculas.
    texto = str(texto).strip().lower()

    # NFD separa a letra do acento.
    # Exemplo: "á" passa a ser "a" + marca de acento.
    texto = unicodedata.normalize(
        # Define o modo de normalização Unicode utilizado.
        "NFD",
        texto
    )

    # Reconstrói o texto removendo as marcas de acento.
    texto = "".join(
        caractere
        for caractere in texto
        # A categoria "Mn" representa marcas não espaçadas,
        # como os acentos separados pelo NFD.
        if unicodedata.category(caractere) != "Mn"
    )

    # Remove espaços duplicados antes de salvar.
    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# Garante que a pasta e o arquivo de memória existam.
def _criar_arquivo_se_necessario():
    # Traz memórias de uma instalação antiga, se existirem.
    _migrar_memoria_antiga_se_necessario()

    # Cria a pasta, caso necessário.
    # parents=True cria pastas intermediárias.
    # exist_ok=True evita erro se ela já existir.
    PASTA_MEMORIA.mkdir(
        parents=True,
        exist_ok=True
    )

    # Verifica se o arquivo memory.json ainda não existe.
    if not ARQUIVO_MEMORIA.exists():
        # Grava as alterações no arquivo.
        _salvar_dados(
            {
                "versao": 1,
                "memorias": [],
            }
        )


# Lê o arquivo memory.json e valida seu conteúdo.
def _carregar_dados():
    # Antes de ler, garante que o arquivo exista.
    _criar_arquivo_se_necessario()

    try:
        # Abre o arquivo no modo de leitura com UTF-8.
        with ARQUIVO_MEMORIA.open(
            "r",
            encoding="utf-8"
        ) as arquivo:
            # Converte o JSON em objetos Python.
            dados = json.load(
                arquivo
            )

    # Captura erros de JSON inválido ou problemas de leitura.
    except (
        json.JSONDecodeError,
        OSError,
    ):
        # Em caso de erro, usa uma estrutura vazia segura.
        dados = {
            "versao": 1,
            "memorias": [],
        }

    # Garante que a estrutura principal seja um dicionário.
    if not isinstance(dados, dict):
        # Em caso de erro, usa uma estrutura vazia segura.
        dados = {
            "versao": 1,
            "memorias": [],
        }

    # Obtém a lista armazenada na chave "memorias".
    memorias = dados.get(
        "memorias",
        []
    )

    # Caso o valor não seja uma lista, substitui por uma lista vazia.
    if not isinstance(memorias, list):
        memorias = []

    # Lista que receberá apenas memórias válidas.
    memorias_validas = []

    # Percorre todas as memórias salvas.
    for memoria in memorias:
        # Ignora itens que não sejam dicionários.
        if not isinstance(memoria, dict):
            continue

        # Obtém o texto da memória e garante que seja string.
        texto = str(
            memoria.get(
                "texto",
                ""
            )
        ).strip()

        # Ignora memórias sem conteúdo.
        if not texto:
            continue

        # Adiciona apenas os campos esperados
        # à nova lista validada.
        memorias_validas.append(
            {
                "id": str(
                    memoria.get(
                        "id",
                        ""
                    )
                ),
                "texto": texto,
                "criada_em": str(
                    memoria.get(
                        "criada_em",
                        ""
                    )
                ),
            }
        )

    # Retorna os dados já limpos e padronizados.
    return {
        "versao": 1,
        "memorias": memorias_validas,
    }


# Grava os dados no arquivo memory.json
# utilizando um arquivo temporário para maior segurança.
def _salvar_dados(dados):
    # Cria a pasta, caso necessário.
    # parents=True cria pastas intermediárias.
    # exist_ok=True evita erro se ela já existir.
    PASTA_MEMORIA.mkdir(
        parents=True,
        exist_ok=True
    )

    # Cria um caminho temporário com extensão .tmp.
    temporario = ARQUIVO_MEMORIA.with_suffix(
        ".tmp"
    )

    # Abre o arquivo temporário no modo de escrita.
    with temporario.open(
        "w",
        encoding="utf-8"
    ) as arquivo:
        # Converte os objetos Python em JSON e grava no arquivo.
        json.dump(
            dados,
            arquivo,
            # Mantém acentos normalmente no arquivo.
            ensure_ascii=False,
            # Formata o JSON com indentação de dois espaços.
            indent=2
        )

    # Substitui o arquivo original pelo temporário
    # somente depois da gravação ser concluída.
    temporario.replace(
        ARQUIVO_MEMORIA
    )


# Salva uma nova memória persistente.
# Faz validação, evita duplicatas, controla limite
# e gera automaticamente um novo ID.
def salvar_memoria(texto):
    # Impede o uso de valores que não sejam texto.
    if not isinstance(texto, str):
        return (
            "A memória informada é inválida."
        )

    # Remove espaços duplicados antes de salvar.
    texto = re.sub(
        r"\s+",
        " ",
        texto
    ).strip()

    # Impede salvar uma memória vazia.
    if not texto:
        return (
            "Não recebi nenhuma informação "
            "para memorizar."
        )

    # Impede memórias maiores que o limite definido.
    if len(texto) > MAXIMO_CARACTERES:
        return (
            "Essa memória é longa demais. "
            f"Resuma em até {MAXIMO_CARACTERES} caracteres."
        )

    # Gera uma versão padronizada para comparar duplicatas.
    texto_normalizado = _normalizar_texto(
        texto
    )

    # Protege a leitura do arquivo.
    with _LOCK:
        # Carrega os dados atuais do arquivo.
        dados = _carregar_dados()

        # Obtém a lista de memórias.
        memorias = dados[
            "memorias"
        ]

        # Evita memória duplicada
        # Primeira tentativa: busca por ID exato.
        for memoria in memorias:
            # Normaliza cada memória existente.
            memoria_normalizada = _normalizar_texto(
                memoria["texto"]
            )

            # Compara ignorando acentos, maiúsculas
            # e espaços extras.
            if memoria_normalizada == texto_normalizado:
                return (
                    "Essa informação já está "
                    "salva na memória."
                )

        # Não apaga memórias antigas automaticamente
        # Impede novas memórias quando o limite foi atingido.
        if len(memorias) >= MAXIMO_MEMORIAS:
            return (
                "Minha memória persistente atingiu "
                f"o limite de {MAXIMO_MEMORIAS} informações. "
                "Peça para eu listar ou esquecer alguma "
                "memória antes de salvar outra."
            )

        # Define 1 como ID inicial caso não existam memórias.
        proximo_id = 1

        # Lista que receberá apenas IDs numéricos válidos.
        ids_validos = []

        # Primeira tentativa: busca por ID exato.
        for memoria in memorias:
            try:
                # Converte o ID salvo para número inteiro.
                ids_validos.append(
                    int(
                        memoria["id"]
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                pass

        # Se houver IDs válidos, usa o maior e soma 1.
        if ids_validos:
            proximo_id = (
                max(ids_validos) + 1
            )

        # Adiciona a nova memória à lista.
        memorias.append(
            {
                "id": str(
                    proximo_id
                ),
                "texto": texto,
                # Registra a data e hora atuais em formato ISO.
                "criada_em": datetime.now().isoformat(
                    # Remove microssegundos para deixar o valor mais legível.
                    timespec="seconds"
                ),
            }
        )

        # Atualiza a lista dentro do dicionário principal.
        dados["memorias"] = memorias

        # Grava as alterações no arquivo.
        _salvar_dados(
            dados
        )

    # Calcula quantas memórias estão ocupadas.
    quantidade = len(
        memorias
    )

    # Calcula quantas posições ainda estão disponíveis.
    restantes = (
        MAXIMO_MEMORIAS
        - quantidade
    )

    # Monta o texto final enviado ao modelo.
    # Também orienta o SOFTIA a usar as memórias
    # somente quando forem relevantes.
    return (
        f"Memória salva: {texto}. "
        f"Tenho {quantidade} de "
        f"{MAXIMO_MEMORIAS} memórias ocupadas "
        f"e {restantes} disponíveis."
    )


# Retorna todas as memórias salvas
# já numeradas e formatadas para leitura.
def listar_memorias():
    # Protege a leitura do arquivo.
    with _LOCK:
        # Carrega os dados atuais do arquivo.
        dados = _carregar_dados()

        # Obtém a lista de memórias.
        memorias = dados[
            "memorias"
        ]

    # Retorna um bloco simples quando não há memórias.
    if not memorias:
        return (
            "Nenhuma memória foi salva ainda."
        )

    # Lista usada para montar cada linha da resposta.
    linhas = []

    # Percorre todas as memórias salvas.
    for memoria in memorias:
        # Adiciona ID e texto em uma linha formatada.
        linhas.append(
            f"{memoria['id']}. "
            f"{memoria['texto']}"
        )

    # Calcula quantas memórias estão ocupadas.
    quantidade = len(
        memorias
    )

    # Monta o texto final enviado ao modelo.
    # Também orienta o SOFTIA a usar as memórias
    # somente quando forem relevantes.
    return (
        f"Tenho {quantidade} de "
        f"{MAXIMO_MEMORIAS} memórias salvas:\n"
        + "\n".join(linhas)
    )


# Remove uma memória específica.
# Aceita o ID, o texto exato ou um trecho único.
def esquecer_memoria(referencia):
    # Garante que a referência recebida seja texto.
    if not isinstance(referencia, str):
        return (
            "A referência da memória é inválida."
        )

    # Remove espaços externos.
    referencia = referencia.strip()

    # Impede uma busca vazia.
    if not referencia:
        return (
            "Informe qual memória deve "
            "ser esquecida."
        )

    # Normaliza a referência para facilitar a busca.
    referencia_normalizada = _normalizar_texto(
        referencia
    )

    # Segurança contra exclusão geral acidental
    # Conjunto de comandos bloqueados por segurança.
    # Evita excluir todas as memórias acidentalmente.
    comandos_apagar_tudo = {
        "tudo",
        "todas",
        "todas as memorias",
        "apagar tudo",
        "limpar tudo",
        "esquecer tudo",
    }

    # Recusa pedidos de exclusão geral.
    if referencia_normalizada in comandos_apagar_tudo:
        return (
            "Por segurança, não apago todas "
            "as memórias em uma única solicitação. "
            "Peça para esquecer uma informação específica."
        )

    # Protege a leitura do arquivo.
    with _LOCK:
        # Carrega os dados atuais do arquivo.
        dados = _carregar_dados()

        # Obtém a lista de memórias.
        memorias = dados[
            "memorias"
        ]

        # Guardará a memória localizada.
        encontrada = None

        # Primeiro tenta localizar pelo ID
        # Primeira tentativa: busca por ID exato.
        for memoria in memorias:
            # Compara a referência diretamente com o ID.
            if memoria["id"] == referencia:
                encontrada = memoria
                break

        # Depois tenta correspondência exata
        # Retorna erro caso nenhuma memória corresponda.
        if encontrada is None:
            # Percorre novamente para correspondência exata.
            for memoria in memorias:
                texto_normalizado = _normalizar_texto(
                    memoria["texto"]
                )

                # Verifica se a referência aparece dentro do texto.
                if (
                    texto_normalizado
                    == referencia_normalizada
                ):
                    encontrada = memoria
                    break

        # Depois tenta correspondência parcial
        # Retorna erro caso nenhuma memória corresponda.
        if encontrada is None:
            # Lista para correspondências parciais.
            candidatas = []

            # Percorre novamente para correspondência exata.
            for memoria in memorias:
                texto_normalizado = _normalizar_texto(
                    memoria["texto"]
                )

                # Verifica se a referência aparece dentro do texto.
                if (
                    referencia_normalizada
                    in texto_normalizado
                ):
                    candidatas.append(
                        memoria
                    )

            # Se houver apenas uma candidata, ela pode ser removida.
            if len(candidatas) == 1:
                encontrada = candidatas[
                    0
                ]

            # Se houver várias, pede o número exato.
            elif len(candidatas) > 1:
                # Monta uma lista curta de opções para o usuário.
                opcoes = ", ".join(
                    (
                        f"{memoria['id']}: "
                        f"{memoria['texto']}"
                    )
                    for memoria
                    in candidatas[:5]
                )

                return (
                    "Encontrei mais de uma "
                    "memória parecida. "
                    "Peça para esquecer pelo número: "
                    + opcoes
                )

        # Retorna erro caso nenhuma memória corresponda.
        if encontrada is None:
            return (
                "Não encontrei uma memória "
                "correspondente."
            )

        # Remove a memória encontrada da lista.
        memorias.remove(
            encontrada
        )

        # Atualiza a lista dentro do dicionário principal.
        dados["memorias"] = memorias

        # Grava as alterações no arquivo.
        _salvar_dados(
            dados
        )

        # Calcula a quantidade restante.
        quantidade = len(
            memorias
        )

    # Monta o texto final enviado ao modelo.
    # Também orienta o SOFTIA a usar as memórias
    # somente quando forem relevantes.
    return (
        "Memória esquecida: "
        f"{encontrada['texto']}. "
        f"Agora tenho {quantidade} de "
        f"{MAXIMO_MEMORIAS} memórias ocupadas."
    )


# Gera o bloco de memória que será incluído
# na instrução do sistema do Gemini.
def contexto_memorias():
    # Protege a leitura do arquivo.
    with _LOCK:
        # Carrega os dados atuais do arquivo.
        dados = _carregar_dados()

        # Obtém a lista de memórias.
        memorias = dados[
            "memorias"
        ]

    # Retorna um bloco simples quando não há memórias.
    if not memorias:
        return (
            "MEMÓRIA PERSISTENTE:\n"
            "Nenhuma memória salva."
        )

    # Converte cada memória em uma linha iniciada por hífen.
    linhas = [
        f"- {memoria['texto']}"
        for memoria in memorias
    ]

    # Monta o texto final enviado ao modelo.
    # Também orienta o SOFTIA a usar as memórias
    # somente quando forem relevantes.
    return (
        "MEMÓRIA PERSISTENTE DO USUÁRIO:\n"
        + "\n".join(linhas)
        + "\nUse essas informações somente quando "
        "forem relevantes para o pedido atual. "
        "Não mencione a existência deste bloco "
        "sem necessidade."
    )