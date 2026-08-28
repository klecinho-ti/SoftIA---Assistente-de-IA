# Biblioteca utilizada para trabalhar com dados no formato JSON.
#
# Neste arquivo ela está importada, mas não é utilizada diretamente
# nas funções atuais. Ela pode ter sido mantida para compatibilidade
# ou para futuras funções de pesquisa.
import json

# Biblioteca usada para trabalhar com expressões regulares.
#
# Neste arquivo ela é utilizada para localizar os identificadores
# dos vídeos dentro do código HTML retornado pelo YouTube.
import re

# Biblioteca padrão do Python usada para abrir páginas
# no navegador padrão do computador.
import webbrowser


# unescape converte códigos HTML em caracteres normais.
#
# Exemplo:
# &amp; passa a ser &
#
# Nesta versão do arquivo, ela ainda não é utilizada diretamente,
# mas foi mantida sem alterações.
from html import unescape

# URLError representa erros relacionados a conexões com endereços da internet.
from urllib.error import URLError

# quote_plus prepara um texto para ser utilizado dentro de uma URL.
#
# Exemplo:
# "música relaxante" passa a ser "m%C3%BAsica+relaxante".
from urllib.parse import quote_plus

# Request permite montar uma requisição HTTP com cabeçalhos personalizados.
#
# urlopen realiza a conexão com o endereço informado.
from urllib.request import Request, urlopen


# Cabeçalhos enviados ao acessar páginas da internet.
#
# Alguns sites podem recusar requisições que não pareçam
# ter sido feitas por um navegador comum.
CABECALHOS_NAVEGADOR = {
    # User-Agent identifica o tipo de navegador e sistema operacional.
    #
    # Neste caso, a requisição se apresenta como se tivesse sido
    # realizada pelo Google Chrome no Windows.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),

    # Informa ao site que o idioma preferencial é português do Brasil.
    #
    # Os valores "q" indicam a prioridade de cada idioma.
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _limpar_texto(texto):
    """
    Limpa e organiza o texto recebido.

    A função:
    - verifica se o valor é realmente uma string;
    - remove espaços duplicados;
    - remove quebras de linha e tabulações extras;
    - remove espaços do início e do final.

    O caractere "_" no início do nome indica que esta função
    foi criada para uso interno deste arquivo.
    """

    # Caso o valor não seja um texto, retorna uma string vazia.
    if not isinstance(texto, str):
        return ""

    # split() separa o texto usando qualquer quantidade
    # de espaços, tabulações ou quebras de linha.
    #
    # " ".join() junta novamente as palavras utilizando
    # somente um espaço entre elas.
    #
    # strip() remove espaços no início e no final.
    return " ".join(
        texto.split()
    ).strip()


def pesquisar_no_navegador(consulta):
    """
    Abre uma pesquisa no Google usando o navegador padrão.

    Use somente quando o usuário pedir explicitamente
    para abrir a pesquisa no navegador ou no Google.
    """

    # Limpa a consulta antes de montar o endereço da pesquisa.
    consulta = _limpar_texto(
        consulta
    )

    # Impede que uma pesquisa vazia seja aberta.
    if not consulta:
        return (
            "Informe o que deseja pesquisar "
            "no navegador."
        )

    # Monta a URL da pesquisa no Google.
    #
    # quote_plus converte espaços e caracteres especiais
    # para um formato válido dentro de endereços da internet.
    url = (
        "https://www.google.com/search?q="
        + quote_plus(
            consulta
        )
    )

    # Abre a URL no navegador padrão.
    #
    # new=2 solicita que o endereço seja aberto
    # em uma nova aba, quando possível.
    #
    # webbrowser.open retorna True quando consegue solicitar
    # a abertura da página e False quando não consegue.
    abriu = webbrowser.open(
        url,
        new=2,
    )

    # Retorna uma mensagem de erro caso o navegador
    # não possa ser aberto.
    if not abriu:
        return (
            "Não consegui abrir o navegador padrão "
            "para realizar a pesquisa."
        )

    # Retorna uma confirmação para o SOFTIA falar
    # ou exibir na interface.
    return (
        f"Abri no navegador uma pesquisa por: "
        f"{consulta}."
    )


def _obter_html_youtube(busca):
    """
    Acessa a página de resultados do YouTube e retorna seu HTML.

    Em vez de abrir imediatamente a página no navegador,
    essa função lê o conteúdo da página para que o sistema
    tente encontrar automaticamente o primeiro vídeo.
    """

    # Monta o endereço da pesquisa no YouTube.
    url = (
        "https://www.youtube.com/results?search_query="
        + quote_plus(
            busca
        )
    )

    # Cria uma requisição HTTP.
    #
    # Os cabeçalhos fazem a requisição parecer uma navegação
    # realizada por um navegador comum.
    requisicao = Request(
        url,
        headers=CABECALHOS_NAVEGADOR,
    )

    # Abre a conexão com o YouTube.
    #
    # timeout=12 limita o tempo de espera a 12 segundos.
    #
    # O bloco "with" fecha automaticamente a conexão
    # quando a leitura terminar.
    with urlopen(
        requisicao,
        timeout=12,
    ) as resposta:

        # read() lê os dados recebidos da página.
        #
        # decode("utf-8") transforma os dados binários em texto.
        #
        # errors="ignore" ignora caracteres que eventualmente
        # não possam ser interpretados.
        return resposta.read().decode(
            "utf-8",
            errors="ignore",
        )


def _extrair_video_id(html):
    """
    Procura IDs de vídeos nos dados retornados pelo YouTube.

    O primeiro resultado comum costuma aparecer como:
    "videoId":"XXXXXXXXXXX"
    """

    # re.findall procura todas as partes do texto
    # que correspondam à expressão regular.
    #
    # Um ID de vídeo do YouTube normalmente possui 11 caracteres.
    #
    # Os caracteres permitidos são:
    # - letras maiúsculas;
    # - letras minúsculas;
    # - números;
    # - underline;
    # - hífen.
    ids = re.findall(
        r'"videoId":"([a-zA-Z0-9_-]{11})"',
        html,
    )

    # Retorna None caso nenhum ID seja encontrado.
    if not ids:
        return None

    # Cria um conjunto para registrar os IDs que já apareceram.
    #
    # Isso é necessário porque o mesmo vídeo pode aparecer
    # diversas vezes dentro do HTML da página.
    vistos = set()

    # Percorre os IDs na mesma ordem em que foram encontrados.
    for video_id in ids:

        # Ignora IDs repetidos.
        if video_id in vistos:
            continue

        # Registra o ID como já verificado.
        vistos.add(
            video_id
        )

        # Retorna o primeiro ID único encontrado.
        #
        # Como o return encerra a função, os demais IDs
        # não precisam ser analisados.
        return video_id

    # Retorno de segurança caso nenhum ID válido seja encontrado.
    return None


def tocar_no_youtube(busca):
    """
    Pesquisa uma música ou vídeo no YouTube e abre
    diretamente um resultado no navegador padrão.

    Não usa PyWhatKit, Playwright, Selenium ou PyAutoGUI.
    """

    # Limpa o texto informado antes de realizar a pesquisa.
    busca = _limpar_texto(
        busca
    )

    # Impede a execução caso nenhuma música ou vídeo
    # tenha sido informado.
    if not busca:
        return (
            "Informe qual música ou vídeo "
            "deseja reproduzir."
        )

    # Acrescenta termos que ajudam a priorizar resultados oficiais.
    #
    # Por exemplo:
    #
    # "Imagine Dragons Believer"
    #
    # passa a ser pesquisado como:
    #
    # "Imagine Dragons Believer official audio official video"
    termo_busca = (
        busca
        + " official audio official video"
    )

    try:
        # Obtém o HTML da página de resultados do YouTube.
        html = _obter_html_youtube(
            termo_busca
        )

        # Tenta localizar o primeiro identificador de vídeo.
        video_id = _extrair_video_id(
            html
        )

        # Caso nenhum ID seja identificado automaticamente,
        # abre a página normal de resultados do YouTube.
        if not video_id:
            url_resultados = (
                "https://www.youtube.com/results?search_query="
                + quote_plus(
                    termo_busca
                )
            )

            # Abre os resultados em uma nova aba.
            webbrowser.open(
                url_resultados,
                new=2,
            )

            # Informa que não foi possível abrir diretamente
            # um vídeo específico.
            return (
                "Não consegui identificar automaticamente "
                "o primeiro vídeo. Abri os resultados "
                f"do YouTube para: {busca}."
            )

        # Monta o endereço direto do vídeo usando
        # o identificador encontrado.
        #
        # O parâmetro autoplay=1 solicita que o YouTube
        # tente iniciar a reprodução automaticamente.
        #
        # A reprodução automática também depende das permissões
        # e configurações do navegador do usuário.
        url_video = (
            "https://www.youtube.com/watch?v="
            + video_id
            + "&autoplay=1"
        )

        # Abre o vídeo no navegador padrão.
        abriu = webbrowser.open(
            url_video,
            new=2,
        )

        # Caso o navegador não consiga ser aberto,
        # retorna uma mensagem informativa.
        if not abriu:
            return (
                "Encontrei o vídeo, mas não consegui "
                "abrir o navegador padrão."
            )

        # Retorna a confirmação quando o endereço
        # do vídeo é aberto corretamente.
        return (
            f"Abrindo no YouTube: {busca}."
        )

    except (
        URLError,
        TimeoutError,
        OSError,
    ) as erro:
        # Este bloco é executado caso aconteça algum problema, como:
        #
        # - falta de internet;
        # - endereço indisponível;
        # - tempo de conexão excedido;
        # - erro do sistema operacional.
        #
        # Mesmo com o erro, o sistema tenta abrir a página
        # comum de resultados do YouTube.
        url_resultados = (
            "https://www.youtube.com/results?search_query="
            + quote_plus(
                termo_busca
            )
        )

        # Abre os resultados no navegador padrão.
        webbrowser.open(
            url_resultados,
            new=2,
        )

        # Retorna a mensagem informando que a abertura direta
        # não funcionou, mas que os resultados foram abertos.
        return (
            "Não consegui abrir o vídeo diretamente. "
            "Abri os resultados do YouTube para você. "
            f"Detalhes: {erro}"
        )