# ============================================================
# SOFTIA VISION - CONTROLE DA ÁREA DE TRABALHO
# ============================================================
#
# Este arquivo contém o código completo original com comentários
# didáticos adicionados para facilitar a explicação durante o curso.
#
# A lógica, a estrutura das funções e o funcionamento foram mantidos.
# Os comentários explicam as principais decisões e operações do código.
#
# ============================================================

# Path facilita a criação, combinação e validação de caminhos de arquivos e pastas.
# Ele é usado para localizar a Área de Trabalho e manipular os itens dentro dela.
from pathlib import Path
# shutil fornece funções para copiar, mover e organizar arquivos e pastas.
import shutil
# unicodedata permite remover acentos dos textos.
# Isso ajuda o SOFTIA a comparar nomes mesmo quando o usuário fala ou escreve sem acento.
import unicodedata


# Área de transferência interna do SOFTIA.
# Ela guarda somente a referência do item e a operação solicitada.
# Este dicionário funciona como uma área de transferência própria do SOFTIA.
# Ele não copia o conteúdo imediatamente: apenas guarda o caminho do item
# e registra se a operação escolhida foi copiar ou recortar.
_AREA_TRANSFERENCIA = {
    "origem": None,
    "operacao": None,
}


# Localiza a Área de Trabalho do usuário.
# A função testa caminhos comuns do Windows, incluindo instalações com OneDrive.
def area_de_trabalho():
    # Path.home() retorna a pasta principal do usuário atual.
    # Exemplo: C:\Users\Joao
    user = Path.home()

    # Lista com os caminhos mais comuns da Área de Trabalho
    # em computadores com Windows em português ou inglês.
    opcoes = [
        user / "OneDrive" / "Desktop",
        user / "OneDrive" / "Área de Trabalho",
        user / "Desktop",
        user / "Área de Trabalho",
    ]

    # Percorre todas as opções até encontrar uma pasta válida.
    for pasta in opcoes:
        if pasta.exists() and pasta.is_dir():
            # resolve() transforma o caminho em um caminho absoluto e normalizado.
            return pasta.resolve()

    raise FileNotFoundError(
        "Não foi possível localizar a Área de Trabalho."
    )


# Limpa nomes de arquivos e pastas antes de utilizá-los.
# Também remove caracteres proibidos pelo Windows.
def limpar_nome(nome):
    # Garante que o valor recebido seja realmente um texto.
    if not isinstance(nome, str):
        return ""

    # Caracteres que o Windows não permite em nomes de arquivos e pastas.
    proibidos = [
        "\\",
        "/",
        ":",
        "*",
        "?",
        '"',
        "<",
        ">",
        "|",
    ]

    # Remove cada caractere proibido que aparecer no nome.
    for caractere in proibidos:
        nome = nome.replace(caractere, "")

    # strip() remove espaços das extremidades.
    # rstrip(".") remove pontos no final do nome, que podem causar problemas no Windows.
    return nome.strip().rstrip(".")


# Padroniza um texto para facilitar comparações.
# Converte para minúsculas, remove espaços extras e retira acentos.
def _normalizar(texto):
    # Converte o valor para texto, remove espaços externos
    # e transforma todas as letras em minúsculas.
    texto = str(texto or "").strip().lower()
    # O modo NFD separa a letra do acento.
    # Exemplo: "á" passa a ser "a" + marca de acento.
    texto = unicodedata.normalize("NFD", texto)

    return "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )


# Verifica se um caminho está realmente dentro da Área de Trabalho.
# Essa validação impede que o SOFTIA altere arquivos fora da área permitida.
def _esta_dentro_da_area(caminho):
    # Obtém o caminho real da Área de Trabalho.
    desktop = area_de_trabalho()
    # Converte o caminho recebido para um caminho absoluto.
    caminho = Path(caminho).resolve()

    try:
        # relative_to() funciona somente se o caminho estiver dentro do desktop.
        # Se estiver fora, a função gera ValueError.
        caminho.relative_to(desktop)
        return True
    except ValueError:
        return False


# Transforma um caminho relativo, como "Projetos/Cliente A",
# em um caminho completo dentro da Área de Trabalho.
def _resolver_caminho_relativo(caminho_relativo=""):
    """
    Resolve um caminho sempre dentro da Área de Trabalho.

    Exemplos aceitos:
    - "" -> raiz da Área de Trabalho
    - "Projetos"
    - "Projetos/Cliente A"
    """

    # Obtém o caminho real da Área de Trabalho.
    desktop = area_de_trabalho()
    # Converte o caminho recebido para texto e remove espaços extras.
    caminho_relativo = str(caminho_relativo or "").strip()

    if not caminho_relativo:
        return desktop

    # Padroniza as barras para facilitar a separação das pastas.
    caminho_relativo = caminho_relativo.replace("\\", "/")

    # Divide o caminho em partes e limpa cada nome individualmente.
    partes = [
        limpar_nome(parte)
        for parte in caminho_relativo.split("/")
        if limpar_nome(parte)
    ]

    # Monta o caminho completo juntando a Área de Trabalho
    # com todas as partes do caminho relativo.
    caminho = desktop.joinpath(*partes).resolve()

    if not _esta_dentro_da_area(caminho):
        raise ValueError(
            "O caminho informado está fora da Área de Trabalho."
        )

    return caminho


# Procura um arquivo ou pasta dentro da Área de Trabalho.
# Primeiro tenta encontrar o nome exato; depois, uma correspondência parcial única.
def _localizar_item(nome, pasta_relativa=""):
    """
    Localiza um arquivo ou pasta dentro da pasta informada.

    Primeiro busca correspondência exata, ignorando maiúsculas e acentos.
    Depois aceita correspondência parcial somente quando houver um único
    resultado, evitando agir sobre o item errado.
    """

    # Garante que o nome seja texto e remove espaços externos.
    nome = str(nome or "").strip()

    if not nome:
        return None, "Informe o nome do arquivo ou pasta."

    # Resolve a pasta onde a busca será realizada.
    pasta = _resolver_caminho_relativo(pasta_relativa)

    if not pasta.exists() or not pasta.is_dir():
        return None, (
            f"A pasta de origem '{pasta_relativa}' não foi encontrada."
        )

    # Normaliza o nome procurado para ignorar maiúsculas e acentos.
    procurado = _normalizar(nome)
    # iterdir() retorna os arquivos e pastas existentes no local.
    itens = list(pasta.iterdir())

    # Lista todos os itens cujo nome normalizado é exatamente igual ao procurado.
    exatos = [
        item
        for item in itens
        if _normalizar(item.name) == procurado
    ]

    if len(exatos) == 1:
        return exatos[0], None

    # Caso não exista resultado exato, procura nomes que contenham o termo informado.
    parciais = [
        item
        for item in itens
        if procurado in _normalizar(item.name)
    ]

    if len(parciais) == 1:
        return parciais[0], None

    if len(parciais) > 1:
        opcoes = ", ".join(
            item.name
            for item in parciais[:8]
        )

        return None, (
            "Encontrei mais de um item parecido: "
            f"{opcoes}. Informe o nome completo."
        )

    return None, (
        f"Não encontrei '{nome}'"
        + (
            f" dentro de '{pasta_relativa}'."
            if pasta_relativa
            else " na Área de Trabalho."
        )
    )


# Cria uma nova pasta diretamente na Área de Trabalho.
def criar_pasta_area_trabalho(nome):
    # Limpa o nome antes de criar a pasta.
    nome = limpar_nome(nome)

    if not nome:
        return "Nome de pasta inválido."

    # Obtém o caminho real da Área de Trabalho.
    desktop = area_de_trabalho()
    # Monta o caminho final da nova pasta.
    caminho = desktop / nome

    if caminho.exists():
        return (
            f"A pasta '{nome}' já existe. "
            "Não alterei nada."
        )

    # mkdir() cria a pasta.
    # parents=True permite criar estruturas necessárias.
    # exist_ok=False impede substituir algo que já existe.
    caminho.mkdir(
        parents=True,
        exist_ok=False
    )

    return (
        f"Pasta '{nome}' criada com sucesso "
        "na área de trabalho."
    )


# Lista os arquivos e pastas presentes na Área de Trabalho.
def listar_area_de_trabalho():
    # Obtém o caminho real da Área de Trabalho.
    desktop = area_de_trabalho()

    # Cria uma lista contendo apenas o nome de cada item.
    itens = [
        item.name
        for item in desktop.iterdir()
    ]

    if not itens:
        return "A área de trabalho está vazia."

    return (
        "Itens na área de trabalho: "
        # Limita a resposta aos primeiros 50 itens para evitar uma mensagem muito grande.
        + ", ".join(itens[:50])
    )


# Organiza arquivos da Área de Trabalho por extensão.
# Pastas são ignoradas; apenas arquivos conhecidos são movimentados.
def organizar_area_de_trabalho_basico():
    # Obtém o caminho real da Área de Trabalho.
    desktop = area_de_trabalho()

    # Relaciona cada pasta de destino às extensões que pertencem a ela.
    pastas = {
        "Imagens": [
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        ],
        "PDFs": [
            ".pdf",
        ],
        "Documentos": [
            ".doc",
            ".docx",
            ".txt",
            ".xlsx",
            ".pptx",
        ],
        "Compactados": [
            ".zip",
            ".rar",
            ".7z",
        ],
    }

    # Guarda os nomes dos arquivos movidos para montar a resposta final.
    movidos = []

    # Percorre todos os itens da Área de Trabalho.
    for item in desktop.iterdir():
        # Ignora pastas para não mover estruturas inteiras por engano.
        if item.is_dir():
            continue

        # Verifica em qual categoria a extensão do arquivo se encaixa.
        for pasta, extensoes in pastas.items():
            if item.suffix.lower() in extensoes:
                destino_pasta = desktop / pasta

                # Cria a pasta de destino somente quando necessário.
                destino_pasta.mkdir(
                    exist_ok=True
                )

                destino = (
                    destino_pasta / item.name
                )

                if destino.exists():
                    continue

                # Move o arquivo para a pasta correspondente.
                shutil.move(
                    str(item),
                    str(destino)
                )

                movidos.append(
                    item.name
                )

                break

    if not movidos:
        return (
            "Não encontrei arquivos para organizar "
            "ou todos já estavam organizados."
        )

    return (
        "Organizei estes arquivos: "
        + ", ".join(movidos)
    )


# Prepara um arquivo ou pasta para ser copiado depois.
# Nenhuma cópia acontece aqui; a origem fica armazenada na área de transferência interna.
def copiar_item_area_trabalho(nome, pasta_origem=""):
    item, erro = _localizar_item(
        nome,
        pasta_origem,
    )

    if erro:
        return erro

    _AREA_TRANSFERENCIA["origem"] = str(
        item.resolve()
    )
    # Registra que a próxima operação de colar deve criar uma cópia.
    _AREA_TRANSFERENCIA["operacao"] = "copiar"

    return (
        f"'{item.name}' foi preparado para copiar. "
        "Agora informe onde deseja colar."
    )


# Prepara um arquivo ou pasta para ser movido.
# O item só será movimentado quando a função de colar for executada.
def recortar_item_area_trabalho(nome, pasta_origem=""):
    item, erro = _localizar_item(
        nome,
        pasta_origem,
    )

    if erro:
        return erro

    _AREA_TRANSFERENCIA["origem"] = str(
        item.resolve()
    )
    # Registra que a próxima operação de colar deve mover o item.
    _AREA_TRANSFERENCIA["operacao"] = "recortar"

    return (
        f"'{item.name}' foi preparado para mover. "
        "Agora informe onde deseja colar."
    )


# Cola o item anteriormente preparado.
# A função decide entre copiar ou mover de acordo com a operação registrada.
def colar_item_area_trabalho(pasta_destino=""):
    # Recupera o caminho do item guardado na área de transferência interna.
    origem_texto = _AREA_TRANSFERENCIA.get(
        "origem"
    )
    # Recupera se a ação escolhida foi copiar ou recortar.
    operacao = _AREA_TRANSFERENCIA.get(
        "operacao"
    )

    if not origem_texto or operacao not in (
        "copiar",
        "recortar",
    ):
        return (
            "Não há nenhum arquivo ou pasta preparado "
            "para copiar ou recortar."
        )

    # Converte o caminho salvo novamente para um objeto Path.
    origem = Path(origem_texto)

    if not origem.exists():
        # Limpa a referência quando a operação deixa de ser válida.
        _AREA_TRANSFERENCIA["origem"] = None
        _AREA_TRANSFERENCIA["operacao"] = None

        return (
            "O item preparado não existe mais. "
            "A operação foi cancelada."
        )

    if not _esta_dentro_da_area(origem):
        # Limpa a referência quando a operação deixa de ser válida.
        _AREA_TRANSFERENCIA["origem"] = None
        _AREA_TRANSFERENCIA["operacao"] = None

        return (
            "A operação foi bloqueada porque o item está "
            "fora da Área de Trabalho."
        )

    try:
        # Resolve a pasta de destino garantindo que ela esteja dentro da Área de Trabalho.
        destino_pasta = _resolver_caminho_relativo(
            pasta_destino
        )
    except ValueError as erro:
        return str(erro)

    if not destino_pasta.exists():
        return (
            f"A pasta de destino '{pasta_destino}' "
            "não foi encontrada."
        )

    if not destino_pasta.is_dir():
        return (
            f"'{pasta_destino}' não é uma pasta válida."
        )

    # Impede copiar ou mover uma pasta para dentro dela mesma.
    if origem.is_dir():
        try:
            destino_pasta.resolve().relative_to(
                origem.resolve()
            )
            return (
                "Não é possível colar uma pasta dentro dela mesma."
            )
        except ValueError:
            pass

    # Mantém o nome original do item ao montar o caminho de destino.
    destino = destino_pasta / origem.name

    if destino.exists():
        return (
            f"Já existe um item chamado '{origem.name}' "
            "no destino. Não sobrescrevi nada."
        )

    try:
        # Na operação de copiar, pastas e arquivos precisam de funções diferentes.
        if operacao == "copiar":
            if origem.is_dir():
                # copytree() copia uma pasta completa, incluindo seu conteúdo.
                shutil.copytree(
                    str(origem),
                    str(destino),
                )
            else:
                # copy2() copia o arquivo e preserva seus metadados quando possível.
                shutil.copy2(
                    str(origem),
                    str(destino),
                )

            return (
                f"'{origem.name}' foi copiado com sucesso"
                + (
                    f" para '{pasta_destino}'."
                    if pasta_destino
                    else " para a Área de Trabalho."
                )
            )

        # Na operação de recortar, move o item para o destino.
        shutil.move(
            str(origem),
            str(destino),
        )

        # Limpa a referência quando a operação deixa de ser válida.
        _AREA_TRANSFERENCIA["origem"] = None
        _AREA_TRANSFERENCIA["operacao"] = None

        return (
            f"'{origem.name}' foi movido com sucesso"
            + (
                f" para '{pasta_destino}'."
                if pasta_destino
                else " para a Área de Trabalho."
            )
        )

    except OSError as erro:
        return (
            "Não consegui concluir a operação. "
            f"Detalhes: {erro}"
        )


# Renomeia um arquivo ou pasta dentro da Área de Trabalho.
def renomear_item_area_trabalho(
    nome_atual,
    novo_nome,
    pasta_origem="",
):
    item, erro = _localizar_item(
        nome_atual,
        pasta_origem,
    )

    if erro:
        return erro

    # Limpa o novo nome para remover caracteres inválidos.
    novo_nome = limpar_nome(
        novo_nome
    )

    if not novo_nome:
        return (
            "O novo nome é inválido. "
            "Nenhuma alteração foi feita."
        )

    # Ao renomear arquivo sem extensão no novo nome,
    # preserva automaticamente a extensão original.
    # Se for um arquivo e o usuário não informar uma nova extensão,
    # o código mantém automaticamente a extensão original.
    if (
        item.is_file()
        and item.suffix
        and not Path(novo_nome).suffix
    ):
        novo_nome += item.suffix

    # Cria um novo caminho na mesma pasta, alterando apenas o nome.
    destino = item.with_name(
        novo_nome
    )

    if destino == item:
        return (
            f"O item já se chama '{item.name}'. "
            "Não alterei nada."
        )

    if destino.exists():
        return (
            f"Já existe um item chamado '{novo_nome}'. "
            "Não sobrescrevi nada."
        )

    try:
        # rename() realiza a alteração do nome no sistema de arquivos.
        item.rename(
            destino
        )

        # Atualiza a referência interna caso o item renomeado
        # estivesse preparado para copiar ou recortar.
        # Verifica se o item renomeado estava preparado para copiar ou recortar.
        origem_transferencia = _AREA_TRANSFERENCIA.get(
            "origem"
        )

        if (
            origem_transferencia
            and Path(origem_transferencia) == item.resolve()
        ):
            _AREA_TRANSFERENCIA["origem"] = str(
                destino.resolve()
            )

        return (
            f"'{item.name}' foi renomeado para "
            f"'{destino.name}' com sucesso."
        )

    except OSError as erro:
        return (
            "Não consegui renomear o item. "
            f"Detalhes: {erro}"
        )


# Cancela qualquer operação pendente de copiar ou recortar.
def cancelar_transferencia_area_trabalho():
    _AREA_TRANSFERENCIA["origem"] = None
    _AREA_TRANSFERENCIA["operacao"] = None

    return (
        "A operação de copiar ou recortar foi cancelada."
    )