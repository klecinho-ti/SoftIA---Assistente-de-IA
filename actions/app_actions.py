# Biblioteca usada para trabalhar com dados no formato JSON.
#
# Neste arquivo, ela é utilizada para interpretar a resposta
# gerada pelo comando PowerShell Get-StartApps.
import json

# Biblioteca que oferece recursos relacionados ao sistema operacional.
#
# Aqui ela é utilizada para:
# - acessar variáveis de ambiente;
# - abrir arquivos, pastas e recursos do Windows;
# - localizar caminhos do sistema.
import os

# Biblioteca utilizada para operações com arquivos e executáveis.
#
# Neste arquivo, shutil.which verifica se determinado programa
# pode ser localizado pelo sistema.
import shutil

# Biblioteca usada para executar comandos e programas externos.
#
# Ela permite abrir aplicativos e também executar comandos
# do PowerShell.
import subprocess

# Biblioteca utilizada para trabalhar com caracteres Unicode.
#
# Neste arquivo, ela ajuda a remover acentos dos textos,
# facilitando a comparação entre comandos.
import unicodedata

# Biblioteca padrão do Python para abrir endereços no navegador.
import webbrowser

# Path facilita a criação e manipulação de caminhos
# de arquivos e pastas.
from pathlib import Path


def normalizar_texto(texto):
    """
    Padroniza um texto para facilitar comparações.

    A função:
    - transforma o valor em texto;
    - converte tudo para letras minúsculas;
    - remove espaços do começo e do final;
    - remove acentos.

    Exemplo:

    "Configurações" passa a ser "configuracoes".
    """

    # Converte o valor recebido para texto.
    #
    # lower() transforma todas as letras em minúsculas.
    # strip() remove espaços no início e no final.
    texto = str(texto).lower().strip()

    # NFD separa os caracteres acentuados em duas partes:
    #
    # "á" passa a ser representado como:
    # - letra "a";
    # - marca de acento.
    #
    # Isso permite remover apenas o acento na próxima etapa.
    texto = unicodedata.normalize("NFD", texto)

    # Monta um novo texto contendo apenas os caracteres
    # que não pertencem à categoria "Mn".
    #
    # "Mn" representa marcas Unicode não espaçadas,
    # como os acentos separados pelo NFD.
    return "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )


def executar_comando(comando):
    """
    Executa um programa ou comando externo.

    subprocess.Popen inicia o processo sem bloquear
    a execução principal do SOFTIA.
    """

    subprocess.Popen(
        comando,

        # shell=False executa diretamente o programa informado,
        # sem utilizar o interpretador de comandos do Windows.
        #
        # Isso torna a execução mais previsível e segura.
        shell=False
    )


def abrir_url(url):
    """
    Abre um endereço no navegador padrão do computador.
    """

    webbrowser.open(url)


def localizar_pasta_usuario(nomes):
    """
    Procura uma pasta pessoal do usuário.

    A busca é realizada em dois possíveis locais:

    1. Diretamente na pasta do usuário;
    2. Dentro da pasta do OneDrive.

    O argumento "nomes" recebe possíveis nomes da pasta,
    considerando diferenças entre Windows em português e inglês.
    """

    # Path.home() retorna a pasta principal do usuário atual.
    #
    # Exemplo:
    # C:\\Users\\Joao
    usuario = Path.home()

    # Tenta obter o caminho do OneDrive por meio
    # da variável de ambiente "OneDrive".
    #
    # Caso a variável não exista, utiliza como alternativa:
    # C:\\Users\\Joao\\OneDrive
    onedrive = Path(
        os.getenv(
            "OneDrive",
            usuario / "OneDrive"
        )
    )

    # Define os locais onde as pastas serão procuradas.
    bases = [
        usuario,
        onedrive,
    ]

    # Percorre cada pasta base.
    for base in bases:

        # Percorre todos os possíveis nomes recebidos.
        for nome in nomes:

            # Monta o caminho completo da pasta.
            caminho = base / nome

            # Verifica se o caminho existe e se realmente
            # representa uma pasta.
            if caminho.exists() and caminho.is_dir():
                return caminho

    # Retorna None caso nenhuma pasta seja encontrada.
    return None


def abrir_pasta_usuario(tipo):
    """
    Abre uma das pastas pessoais do usuário.

    Tipos aceitos:
    - documentos;
    - downloads;
    - videos;
    - musicas.
    """

    # Dicionário que relaciona o tipo recebido
    # aos possíveis nomes da pasta no Windows.
    #
    # Alguns computadores usam nomes em português,
    # enquanto outros mantêm os nomes em inglês.
    pastas = {
        "documentos": [
            "Documents",
            "Documentos",
        ],
        "downloads": [
            "Downloads",
        ],
        "videos": [
            "Videos",
            "Vídeos",
        ],
        "musicas": [
            "Music",
            "Músicas",
        ],
    }

    # Procura a lista de nomes relacionada ao tipo informado.
    nomes = pastas.get(tipo)

    # Retorna False caso o tipo não exista no dicionário.
    if not nomes:
        return False

    # Procura a pasta correspondente no computador.
    caminho = localizar_pasta_usuario(nomes)

    # Retorna False caso a pasta não seja encontrada.
    if not caminho:
        return False

    # os.startfile abre a pasta usando o Explorador de Arquivos.
    os.startfile(str(caminho))

    # Informa que a pasta foi aberta com sucesso.
    return True


def pastas_menu_iniciar():
    """
    Localiza as pastas do Menu Iniciar do Windows.

    O Windows normalmente possui dois locais:

    1. Menu Iniciar exclusivo do usuário atual;
    2. Menu Iniciar compartilhado entre todos os usuários.
    """

    # Lista que receberá os caminhos encontrados.
    caminhos = []

    # APPDATA normalmente aponta para:
    #
    # C:\\Users\\Usuario\\AppData\\Roaming
    appdata = os.getenv("APPDATA")

    # PROGRAMDATA normalmente aponta para:
    #
    # C:\\ProgramData
    programdata = os.getenv("PROGRAMDATA")

    # Verifica se a variável APPDATA foi encontrada.
    if appdata:
        caminhos.append(
            Path(appdata)
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
        )

    # Verifica se a variável PROGRAMDATA foi encontrada.
    if programdata:
        caminhos.append(
            Path(programdata)
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
        )

    # Retorna somente os caminhos que realmente existem.
    return [
        caminho
        for caminho in caminhos
        if caminho.exists()
    ]


def procurar_atalho_menu_iniciar(nome):
    """
    Procura um aplicativo pelos atalhos do Menu Iniciar.

    A busca considera arquivos:

    - .lnk, que são atalhos comuns do Windows;
    - .url, que são atalhos para endereços ou aplicações.

    A função primeiro procura correspondências exatas.
    Caso não encontre, utiliza correspondências parciais.
    """

    # Normaliza o nome informado para facilitar a comparação.
    procurado = normalizar_texto(nome)

    # Lista de correspondências exatas.
    exatos = []

    # Lista de correspondências parciais.
    parciais = []

    # Percorre todas as pastas válidas do Menu Iniciar.
    for pasta in pastas_menu_iniciar():

        # Procura atalhos com as extensões .lnk e .url.
        for extensao in ("*.lnk", "*.url"):

            # rglob realiza uma busca recursiva,
            # incluindo todas as subpastas.
            for atalho in pasta.rglob(extensao):

                # atalho.stem representa o nome do arquivo
                # sem sua extensão.
                #
                # Exemplo:
                # Google Chrome.lnk → Google Chrome
                nome_atalho = normalizar_texto(
                    atalho.stem
                )

                # Verifica se o nome é exatamente igual
                # ao nome procurado.
                if nome_atalho == procurado:
                    exatos.append(atalho)

                # Caso não seja exato, verifica se o termo
                # procurado aparece dentro do nome do atalho.
                elif procurado in nome_atalho:
                    parciais.append(atalho)

    # Prioriza resultados exatos.
    #
    # Caso a lista "exatos" esteja vazia,
    # utiliza os resultados parciais.
    candidatos = exatos or parciais

    # Retorna None caso nenhum candidato seja encontrado.
    if not candidatos:
        return None

    # Ordena os candidatos pelo tamanho do nome.
    #
    # Isso ajuda a escolher o resultado mais curto
    # e provavelmente mais próximo do nome solicitado.
    candidatos.sort(
        key=lambda item: len(item.stem)
    )

    # Retorna o primeiro candidato após a ordenação.
    return candidatos[0]


def listar_aplicativos_windows():
    """
    Obtém a lista de aplicativos registrados no Windows.

    Essa função utiliza o comando PowerShell Get-StartApps,
    que retorna os aplicativos disponíveis no Menu Iniciar,
    incluindo aplicativos tradicionais e aplicativos da Microsoft Store.
    """

    # Comando PowerShell dividido em três etapas:
    #
    # Get-StartApps:
    # obtém os aplicativos registrados no Menu Iniciar.
    #
    # Select-Object Name, AppID:
    # mantém somente o nome e o identificador de cada aplicativo.
    #
    # ConvertTo-Json -Compress:
    # transforma a saída em JSON compacto.
    comando = (
        "Get-StartApps | "
        "Select-Object Name, AppID | "
        "ConvertTo-Json -Compress"
    )

    try:
        # Executa o PowerShell e aguarda o resultado.
        resultado = subprocess.run(
            [
                "powershell",

                # Evita o carregamento do perfil pessoal
                # do PowerShell, tornando a execução mais rápida.
                "-NoProfile",

                # Informa que o próximo item é um comando.
                "-Command",

                comando,
            ],

            # Guarda a saída e os erros dentro do objeto resultado.
            capture_output=True,

            # Converte a saída diretamente para texto.
            text=True,

            # Define UTF-8 para permitir acentos.
            encoding="utf-8",

            # Ignora caracteres que eventualmente não possam
            # ser interpretados pelo UTF-8.
            errors="ignore",

            # Cancela a execução se ela durar mais de 10 segundos.
            timeout=10,

            # Não gera automaticamente uma exceção caso
            # o PowerShell retorne um código de erro.
            check=False,
        )

        # Código diferente de zero normalmente indica erro.
        if resultado.returncode != 0:
            return []

        # Obtém a saída gerada pelo PowerShell
        # e remove espaços extras.
        texto = resultado.stdout.strip()

        # Retorna uma lista vazia se não houver conteúdo.
        if not texto:
            return []

        # Converte o texto JSON para objetos Python.
        dados = json.loads(texto)

        # Quando o PowerShell retorna apenas um aplicativo,
        # o JSON pode ser convertido em um único dicionário
        # em vez de uma lista.
        #
        # Nesse caso, transformamos esse dicionário em uma lista.
        if isinstance(dados, dict):
            dados = [dados]

        # Retorna a lista de aplicativos.
        return dados

    except (
        subprocess.SubprocessError,
        json.JSONDecodeError,
        OSError,
    ):
        # Retorna uma lista vazia caso aconteça:
        #
        # - erro durante o comando;
        # - resposta JSON inválida;
        # - erro do sistema operacional.
        return []


def procurar_app_windows(nome):
    """
    Procura um aplicativo registrado pelo Windows.

    Esta busca é útil principalmente para aplicativos
    da Microsoft Store ou aplicativos que não possuem
    um atalho tradicional facilmente acessível.
    """

    # Normaliza o nome solicitado pelo usuário.
    procurado = normalizar_texto(nome)

    # Resultados que possuem nome exatamente igual.
    exatos = []

    # Resultados cujo nome contém o texto procurado.
    parciais = []

    # Percorre os aplicativos retornados pelo Windows.
    for app in listar_aplicativos_windows():

        # Obtém o nome visível do aplicativo.
        nome_app = app.get("Name", "")

        # Obtém o identificador interno do aplicativo.
        app_id = app.get("AppID", "")

        # Ignora aplicativos sem nome ou sem identificador.
        if not nome_app or not app_id:
            continue

        # Normaliza o nome do aplicativo.
        nome_normalizado = normalizar_texto(
            nome_app
        )

        # Adiciona aos resultados exatos caso
        # os nomes sejam iguais.
        if nome_normalizado == procurado:
            exatos.append(
                (nome_app, app_id)
            )

        # Caso contrário, verifica se o termo procurado
        # está dentro do nome do aplicativo.
        elif procurado in nome_normalizado:
            parciais.append(
                (nome_app, app_id)
            )

    # Prioriza resultados exatos.
    candidatos = exatos or parciais

    # Retorna None caso nenhum aplicativo seja encontrado.
    if not candidatos:
        return None

    # Ordena os candidatos pelo tamanho do nome.
    candidatos.sort(
        key=lambda item: len(item[0])
    )

    # Retorna uma tupla contendo:
    #
    # - nome do aplicativo;
    # - AppID do aplicativo.
    return candidatos[0]


def abrir_app_windows(nome):
    """
    Abre um aplicativo utilizando seu AppID do Windows.
    """

    # Procura o aplicativo registrado pelo sistema.
    encontrado = procurar_app_windows(
        nome
    )

    # Retorna None caso o aplicativo não seja encontrado.
    if not encontrado:
        return None

    # Separa os dois valores da tupla retornada.
    nome_app, app_id = encontrado

    # Usa o Explorer e o endereço especial shell:AppsFolder
    # para abrir o aplicativo por meio do AppID.
    executar_comando(
        [
            "explorer.exe",
            f"shell:AppsFolder\\{app_id}",
        ]
    )

    # Retorna o nome real do aplicativo aberto.
    return nome_app


def abrir_executavel_conhecido(nome):
    """
    Tenta abrir programas conhecidos diretamente pelo executável.

    Esta é uma alternativa usada quando o aplicativo
    não foi localizado pelos atalhos ou pelo Get-StartApps.
    """

    # Dicionário com nomes que o usuário pode falar
    # e os executáveis correspondentes.
    executaveis = {
        "chrome": [
            "chrome.exe",
            "chrome",
        ],
        "google chrome": [
            "chrome.exe",
            "chrome",
        ],
        "edge": [
            "msedge.exe",
            "msedge",
        ],
        "microsoft edge": [
            "msedge.exe",
            "msedge",
        ],
        "word": [
            "winword.exe",
            "winword",
        ],
        "microsoft word": [
            "winword.exe",
            "winword",
        ],
        "excel": [
            "excel.exe",
            "excel",
        ],
        "microsoft excel": [
            "excel.exe",
            "excel",
        ],
        "steam": [
            "steam.exe",
            "steam",
        ],
    }

    # Normaliza o nome informado.
    procurado = normalizar_texto(nome)

    # Obtém a lista de possíveis executáveis.
    #
    # Caso o programa não esteja no dicionário,
    # utiliza uma lista vazia.
    candidatos = executaveis.get(
        procurado,
        []
    )

    # Percorre os possíveis nomes de executável.
    for executavel in candidatos:

        # shutil.which procura o executável nos caminhos
        # reconhecidos pelo sistema.
        caminho = shutil.which(
            executavel
        )

        # Caso encontre o executável, abre o programa.
        if caminho:
            executar_comando(
                [caminho]
            )

            return True

    # Retorna False caso nenhum executável seja encontrado.
    return False


def abrir_especial(nome):
    """
    Abre recursos especiais do Windows.

    Esta função trata comandos que não precisam passar
    pela busca comum de aplicativos, como:

    - Meu Computador;
    - Explorador de Arquivos;
    - Configurações;
    - Calculadora;
    - Prompt de Comando;
    - pastas pessoais;
    - entre outros.
    """

    # Normaliza o comando recebido.
    nome = normalizar_texto(nome)

    # Relaciona diferentes formas de pedir um recurso
    # a uma ação interna padronizada.
    aliases = {
        "meu computador": "meu_computador",
        "este computador": "meu_computador",
        "computador": "meu_computador",

        "explorador de arquivos": "explorador",
        "explorador": "explorador",

        "navegador": "navegador",
        "google": "navegador",

        "antivirus": "defender",
        "anti virus": "defender",
        "windows defender": "defender",
        "seguranca do windows": "defender",

        "configuracoes": "configuracoes",

        "calculadora": "calculadora",

        "relogio": "relogio",
        "alarme": "relogio",
        "relogio e alarmes": "relogio",

        "cmd": "cmd",
        "prompt de comando": "cmd",

        "powershell": "powershell",
        "power shell": "powershell",

        "bloco de notas": "notepad",
        "notepad": "notepad",

        "paint": "paint",

        "painel de controle": "painel",

        "meus documentos": "documentos",
        "documentos": "documentos",

        "meus downloads": "downloads",
        "downloads": "downloads",

        "meus videos": "videos",
        "videos": "videos",

        "minhas musicas": "musicas",
        "musicas": "musicas",
    }

    # Ordena os apelidos do maior para o menor.
    #
    # Isso é importante para que termos mais específicos,
    # como "explorador de arquivos", sejam testados antes
    # de termos menores, como "explorador".
    for apelido in sorted(
        aliases,
        key=len,
        reverse=True
    ):

        # Verifica se o apelido aparece dentro
        # do comando informado.
        if apelido in nome:

            # Obtém o nome interno da ação.
            acao = aliases[apelido]

            # Abre a área "Este Computador".
            if acao == "meu_computador":
                executar_comando(
                    [
                        "explorer.exe",
                        "shell:MyComputerFolder",
                    ]
                )
                return "Abrindo Meu Computador."

            # Abre uma janela comum do Explorador de Arquivos.
            if acao == "explorador":
                executar_comando(
                    ["explorer.exe"]
                )
                return "Abrindo o Explorador de Arquivos."

            # Abre a página inicial do Google
            # no navegador padrão.
            if acao == "navegador":
                abrir_url(
                    "https://www.google.com"
                )
                return "Abrindo o navegador."

            # Abre o aplicativo Segurança do Windows.
            #
            # windowsdefender: é um protocolo especial do sistema.
            if acao == "defender":
                os.startfile(
                    "windowsdefender:"
                )
                return "Abrindo a Segurança do Windows."

            # Abre as Configurações do Windows.
            #
            # ms-settings: é um protocolo especial do sistema.
            if acao == "configuracoes":
                os.startfile(
                    "ms-settings:"
                )
                return "Abrindo as Configurações."

            # Abre a calculadora do Windows.
            if acao == "calculadora":
                executar_comando(
                    ["calc.exe"]
                )
                return "Abrindo a Calculadora."

            # Abre o aplicativo Relógio do Windows.
            #
            # ms-clock: é um protocolo registrado pelo sistema.
            if acao == "relogio":
                os.startfile(
                    "ms-clock:"
                )
                return "Abrindo o Relógio."

            # Abre o Prompt de Comando.
            if acao == "cmd":
                executar_comando(
                    ["cmd.exe"]
                )
                return "Abrindo o Prompt de Comando."

            # Abre o PowerShell.
            if acao == "powershell":
                executar_comando(
                    ["powershell.exe"]
                )
                return "Abrindo o PowerShell."

            # Abre o Bloco de Notas.
            if acao == "notepad":
                executar_comando(
                    ["notepad.exe"]
                )
                return "Abrindo o Bloco de Notas."

            # Abre o Paint.
            if acao == "paint":
                executar_comando(
                    ["mspaint.exe"]
                )
                return "Abrindo o Paint."

            # Abre o Painel de Controle.
            if acao == "painel":
                executar_comando(
                    ["control.exe"]
                )
                return "Abrindo o Painel de Controle."

            # Trata as pastas pessoais do usuário.
            if acao in (
                "documentos",
                "downloads",
                "videos",
                "musicas",
            ):

                # Tenta localizar e abrir a pasta.
                abriu = abrir_pasta_usuario(
                    acao
                )

                # Retorna confirmação caso a pasta tenha sido aberta.
                if abriu:
                    return (
                        f"Abrindo a pasta {acao}."
                    )

                # Retorna uma mensagem caso a pasta
                # não tenha sido encontrada.
                return (
                    f"Não encontrei a pasta {acao} "
                    "neste computador."
                )

    # Retorna None quando o comando não corresponde
    # a nenhum recurso especial.
    return None


def abrir_aplicativo(nome):
    """
    Função principal responsável por abrir aplicativos e recursos.

    A busca acontece na seguinte ordem:

    1. Recursos especiais do Windows;
    2. Atalhos do Menu Iniciar;
    3. Aplicativos registrados pelo Get-StartApps;
    4. Executáveis conhecidos.

    Caso nenhuma opção funcione, retorna uma mensagem de erro.
    """

    # Verifica se o nome recebido é realmente um texto.
    if not isinstance(nome, str):
        return "Nome do aplicativo inválido."

    # Remove espaços do início e do final.
    nome = nome.strip()

    # Impede uma busca com nome vazio.
    if not nome:
        return "Informe o nome do aplicativo que deseja abrir."

    try:
        # Primeiro tenta identificar recursos especiais,
        # como Calculadora, Configurações ou Meu Computador.
        resposta_especial = abrir_especial(
            nome
        )

        # Se a função retornar uma mensagem,
        # significa que o recurso foi identificado e aberto.
        if resposta_especial:
            return resposta_especial

    except OSError as erro:
        # Retorna uma mensagem detalhada caso aconteça
        # um erro ao abrir um recurso do Windows.
        return (
            "Não consegui abrir esse recurso do Windows. "
            f"Detalhes: {erro}"
        )

    try:
        # Caso não seja um recurso especial,
        # procura um atalho no Menu Iniciar.
        atalho = procurar_atalho_menu_iniciar(
            nome
        )

        # Se encontrar um atalho, abre o arquivo .lnk ou .url.
        if atalho:
            os.startfile(str(atalho))

            return (
                f"Abrindo {atalho.stem}."
            )

    except OSError:
        # Caso aconteça erro nesta etapa,
        # o sistema continua para a próxima forma de busca.
        pass

    try:
        # Procura o aplicativo por meio do Get-StartApps
        # e tenta abri-lo usando o AppID.
        nome_app = abrir_app_windows(
            nome
        )

        # Retorna a confirmação quando o aplicativo é aberto.
        if nome_app:
            return (
                f"Abrindo {nome_app}."
            )

    except OSError:
        # Caso esta tentativa falhe,
        # continua para a busca por executável.
        pass

    try:
        # Tenta abrir diretamente programas conhecidos,
        # como Chrome, Edge, Word, Excel e Steam.
        if abrir_executavel_conhecido(
            nome
        ):
            return (
                f"Abrindo {nome}."
            )

    except OSError:
        # Ignora o erro para permitir o retorno
        # da mensagem final de aplicativo não encontrado.
        pass

    # Mensagem retornada quando todas as formas
    # de localizar o aplicativo falham.
    return (
        f"Não consegui localizar '{nome}' neste computador. "
        "Verifique se o aplicativo está instalado ou se aparece "
        "no Menu Iniciar do Windows."
    )