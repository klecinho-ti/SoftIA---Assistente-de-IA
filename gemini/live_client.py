# asyncio permite executar tarefas assíncronas.
# Neste arquivo, ele coordena simultaneamente:
# - envio do microfone;
# - recebimento de respostas;
# - reprodução de áudio;
# - chamadas de ferramentas;
# - encerramento controlado da sessão.
import asyncio
# time é utilizado para medir intervalos.
# Aqui ele ajuda principalmente no controle de repetição
# das funções visuais.
import time
# datetime fornece a data e hora atual.
# Essa informação é colocada na instrução do sistema para ajudar
# o SOFTIA a interpretar termos como hoje, amanhã e dias da semana.
from datetime import datetime

# array transforma bytes de áudio em amostras numéricas.
# Isso permite calcular o volume aproximado da resposta do SOFTIA.
from array import array

# sounddevice captura áudio do microfone e reproduz
# o áudio recebido do Gemini em tempo real.
import sounddevice as sd

# QThread executa o cliente Gemini Live fora da thread principal.
# Isso evita travamentos na interface gráfica.
#
# Signal permite enviar informações da thread para a interface,
# como status, erros, volume e encerramento.
from PySide6.QtCore import QThread, Signal
# Cliente oficial da biblioteca google-genai.
# É utilizado para autenticar e abrir a sessão Gemini Live.
from google import genai
# types contém as estruturas exigidas pela API.
# Exemplos:
# - Tool;
# - FunctionDeclaration;
# - Schema;
# - Content;
# - Part;
# - Blob;
# - FunctionResponse.
from google.genai import types

# Importa as configurações definidas no projeto.
# GEMINI_API_KEY: chave de acesso à API.
# GEMINI_LIVE_MODEL: modelo usado na conversa em tempo real.
# obter_configuracoes_atuais: lê nome, voz e senha configurados
# pelo usuário na janela de Configurações, sempre em tempo real.
# obter_voz_atual: traduz o gênero de voz escolhido para o nome
# técnico da voz usado pela API Gemini.
from core.config import (
    GEMINI_API_KEY,
    GEMINI_LIVE_MODEL,
    obter_configuracoes_atuais,
    obter_voz_atual,
)

# Função que captura a tela do computador
# e devolve a imagem em bytes JPEG.
from vision.screen_capture import capturar_tela_bytes
# Função que captura um quadro da webcam
# e devolve a imagem em bytes JPEG.
from vision.camera_capture import capturar_camera_bytes

# Funções responsáveis pelas operações permitidas
# dentro da Área de Trabalho do Windows.
from actions.file_actions import (
    criar_pasta_area_trabalho,
    listar_area_de_trabalho,
    organizar_area_de_trabalho_basico,
    copiar_item_area_trabalho,
    recortar_item_area_trabalho,
    colar_item_area_trabalho,
    renomear_item_area_trabalho,
    cancelar_transferencia_area_trabalho,
)

# Função utilizada para localizar e abrir aplicativos
# e recursos permitidos do Windows.
from actions.app_actions import abrir_aplicativo
# Funções responsáveis por pesquisas no navegador
# e abertura de vídeos ou músicas no YouTube.
from actions.browser_actions import (
    pesquisar_no_navegador,
    tocar_no_youtube,
)

# Pesquisa invisível de informações atuais.
# Não abre nenhuma guia ou janela no computador.
from actions.web_search import (
    avaliar_necessidade_pesquisa,
    pesquisar_informacao_atual,
    resposta_sem_pesquisa,
)

# Funções responsáveis pelo controle do mouse,
# incluindo rolagem, cliques e movimento até coordenadas.
from actions.mouse_actions import (
    rolar_pagina,
    clicar_mouse,
    duplo_clique_mouse,
    clique_direito_mouse,
    mover_e_clicar,
)

# Função de visão computacional que tenta localizar
# um elemento visível na tela com base em uma descrição.
from vision.click_locator import localizar_elemento_na_tela

# Função que orquestra o envio de mensagens de texto pelo
# WhatsApp Desktop, combinando visão computacional e automação.
from actions.whatsapp_actions import enviar_mensagem_whatsapp

# Funções da memória persistente.
# Elas permitem salvar, listar, remover e carregar memórias.
from memory.memory_manager import (
    salvar_memoria,
    listar_memorias,
    esquecer_memoria,
    contexto_memorias,
)

# Funções responsáveis pela agenda local persistente.
from actions.agenda_actions import (
    criar_evento_agenda,
    listar_agenda,
    cancelar_evento_agenda,
)

# Função responsável por inserir texto no campo ativo do Windows.
from actions.text_actions import escrever_no_campo_ativo

# Função responsável por coletar informações de hardware
# do computador, como processador, memória, disco e placa de vídeo.
from actions.hardware_actions import obter_informacoes_hardware



# Taxa de amostragem do microfone.
# O áudio de entrada é enviado ao Gemini em 16 kHz.
TAXA_ENTRADA = 16000
# Taxa de amostragem da resposta de áudio.
# O áudio gerado pelo Gemini é reproduzido em 24 kHz.
TAXA_SAIDA = 24000
# O sistema utiliza áudio mono.
# Isso significa que existe apenas um canal de áudio.
CANAIS = 1
# Quantidade de amostras processadas em cada bloco.
# Blocos menores reduzem a latência, mas aumentam
# a frequência das operações.
BLOCO = 1024

# Tempo de segurança antes de reabrir o microfone depois
# que o SOFTIA termina de reproduzir a resposta.
ATRASO_REABRIR_MICROFONE = 0.8

# Limite de blocos aguardando envio ao Gemini.
# Evita acúmulo de áudio antigo em computadores ou drivers mais lentos.
LIMITE_FILA_MICROFONE = 50

# Ganho digital aplicado ao áudio do microfone antes de enviar ao Gemini.
# Um valor de 2.5 deixa a voz do usuário mais "alta" para o modelo,
# reduzindo a necessidade de falar perto do microfone ou gritar.
GANHO_MICROFONE = 2.5

# Tempo mínimo entre duas chamadas visuais iguais.
# Isso evita que o Gemini capture repetidamente a mesma imagem
# para um único pedido do usuário.
COOLDOWN_FUNCAO_VISUAL = 8.0


# Classe principal do cliente em tempo real.
# Ela herda de QThread para trabalhar em paralelo com a interface.
class GeminiLiveWorker(QThread):

    # Envia mensagens de status para a interface.
    # Exemplo: conectando, capturando tela ou abrindo aplicativo.
    status_recebido = Signal(str)
    # Envia mensagens de erro para a interface.
    erro_recebido = Signal(str)
    # Informa à interface que a thread terminou.
    chamada_encerrada = Signal()

    # Envia um valor entre 0 e 1 para animar
    # o indicador visual de voz.
    nivel_audio = Signal(float)

    # Solicita que a interface encerre a chamada
    # usando o mesmo método acionado pelo botão.
    # Solicita que a interface encerre a chamada
    # usando o mesmo fluxo do botão de encerramento.
    solicitou_encerramento = Signal()

    # Informa à interface que o servidor pediu a renovação
    # controlada do WebSocket. Não representa erro nem
    # encerramento solicitado pelo usuário.
    solicitou_reconexao = Signal()

    # Envia à interface o token mais recente de retomada
    # da sessão, preservando o contexto da conversa.
    session_handle_atualizado = Signal(str)

    # Construtor da classe.
    # Define todos os estados usados durante a chamada.
    def __init__(self, session_handle=None):
        super().__init__()

        # Enquanto True, a sessão continua rodando.
        self.ativo = True
        # Guardará o loop assíncrono desta thread.
        self.loop = None
        # Limpa a referência da sessão encerrada.
        self.sessao = None
        self.session_handle = session_handle
        self.processando_ferramenta = False
        self.lock_envio = None
        self.imagem_visual_pendente = None

        # Evita processar mais de um aviso GoAway para
        # a mesma conexão.
        self.renovacao_em_andamento = False

        # Indica se o áudio do SOFTIA está sendo reproduzido.
        # Quando True, o microfone é ignorado para evitar eco.
        self.softia_falando = False
        # Referência para a tarefa que reativa o microfone
        # depois que o SOFTIA termina de falar.
        self.tarefa_liberar_microfone = None
        # Referência para a tarefa de encerramento por voz.
        self.tarefa_encerramento = None

        # Impede a execução simultânea de duas funções visuais.
        self.executando_funcao_visual = False
        # Guarda o nome da última função visual executada.
        self.ultima_funcao_visual = None
        # Guarda o momento da última chamada visual.
        self.tempo_ultima_funcao_visual = 0.0

        # Quando True, descarta o áudio gerado pelo Gemini
        # até o fim do turno atual.
        # Quando True, o áudio produzido pelo Gemini
        # durante o turno atual é descartado.
        # Isso é usado em ações que devem acontecer em silêncio.
        self.silenciar_audio_ate_fim_turno = False

    # Método executado automaticamente quando a QThread inicia.
    def run(self):
        try:
            # Cria e executa o ambiente assíncrono desta thread.
            asyncio.run(
                self.executar()
            )

        # Captura erros gerais para impedir que a thread
        # seja encerrada silenciosamente.
        except Exception as erro:
            self.erro_recebido.emit(
                str(erro)
            )

        # Este bloco sempre é executado, mesmo com erro.
        finally:
            self.nivel_audio.emit(
                0.0
            )

            self.chamada_encerrada.emit()

    # Método principal da sessão.
    # Ele configura as ferramentas, conecta ao Gemini,
    # cria filas e inicia as tarefas de áudio.
    async def executar(self):
        # Verifica se a chave da API foi carregada corretamente.
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY não encontrada no arquivo .env"
            )

        # Guarda o loop atual.
        # Isso permite que botões da interface agendem funções assíncronas.
        self.loop = asyncio.get_running_loop()
        self.lock_envio = asyncio.Lock()
        self.renovacao_em_andamento = False

        # Cria o cliente autenticado da API Gemini.
        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        # Lê, em tempo real, o nome, a voz e a senha configurados
        # pelo usuário na janela de Configurações. Isso garante que
        # uma mudança salva ali valha já na próxima chamada, sem
        # reiniciar nem reinstalar o SOFTIA.
        configuracoes_usuario = obter_configuracoes_atuais()
        nome_assistente = configuracoes_usuario["nome_assistente"]
        senha_ativada = configuracoes_usuario["senha_ativada"]
        senha_autenticacao = configuracoes_usuario["senha"]
        voz_feminina = configuracoes_usuario["voz_genero"] != "masculina"
        genero_personalidade = (
            "femininas" if voz_feminina else "masculinas"
        )

        # Monta o bloco de autenticação por palavra-chave somente
        # quando o usuário optou por usar senha na janela de
        # Configurações. Quando desativada, o SOFTIA libera comandos
        # diretamente, sem pedir nenhuma palavra-chave.
        if senha_ativada:
            bloco_autenticacao = (
                "Só faça interação com o usuário, conversas complexas ou "
                "qualquer outro comando se ele disser a palavra-chave. "
                f"A palavra-chave secreta de autenticação é: {senha_autenticacao}. "
                "Essa palavra-chave é uma informação estritamente confidencial. "
                "Nunca revele, pronuncie, escreva, repita, confirme, complete, "
                "dê pistas ou informe a palavra-chave ao usuário. "
                "Isso também vale se ele disser que esqueceu, pedir ajuda, "
                "tentar adivinhar ou permanecer em silêncio. "
                "Use a palavra-chave apenas para comparar silenciosamente "
                "com o áudio recebido do usuário. "
                "A transcrição de voz pode não ser perfeita: aceite como "
                "correta qualquer fala foneticamente muito próxima da "
                "palavra-chave, como pequenas variações de pronúncia ou "
                "sotaque. Só rejeite quando a fala for claramente uma "
                "palavra diferente. "
                "Antes da autenticação, limite-se a solicitar a palavra-chave. "
                "Depois de solicitá-la, pare de falar e aguarde uma resposta real. "
                "Nunca preencha o silêncio e nunca continue a conversa sozinho. "
                "Não trate sua própria voz, áudio reproduzido pelo computador, "
                "eco, ruído ou silêncio como tentativa de autenticação. "
                "O usuário terá no máximo três tentativas incorretas. "
                "Após quatro erros consecutivos, bloqueie o acesso nesta chamada. "
                "Se o usuário disser corretamente a palavra-chave, responda apenas "
                "'Acesso autorizado' uma única vez e aguarde o próximo pedido. "
                "Não repita 'Acesso autorizado' sem uma nova fala do usuário. "
                "Não execute funções nem prossiga com uma conversa completa "
                "antes da autenticação. "
            )
        else:
            bloco_autenticacao = (
                "Não é necessária nenhuma senha ou palavra-chave para "
                "conversar ou executar comandos. Atenda o usuário "
                "diretamente desde a primeira fala. "
            )

        # Lista de ferramentas disponíveis para o modelo.
        # O Gemini decide quando chamar cada função com base
        # nas descrições e parâmetros fornecidos.
        tools = [
            types.Tool(
                function_declarations=[
                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="analisar_tela",
                        description=(
                            "Use esta função somente quando o usuário pedir "
                            "explicitamente para analisar, ver, observar ou "
                            "explicar a tela do computador. Não use "
                            "espontaneamente e não repita para o mesmo pedido."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="analisar_camera",
                        description=(
                            "Use esta função quando o usuário pedir "
                            "explicitamente para analisar, ver, observar ou "
                            "explicar a webcam ou câmera, ou quando pedir para "
                            "ver algo que está mostrando, segurando ou "
                            "apontando fisicamente diante da câmera, como "
                            "'veja o que eu tenho na mão' ou 'olha isso aqui'. "
                            "Não use espontaneamente e não repita para o "
                            "mesmo pedido."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="criar_pasta_area_trabalho",
                        description=(
                            "Cria uma pasta nova na área de trabalho do Windows. "
                            "Use quando o usuário pedir para criar uma pasta. "
                            "Nunca sobrescreva nada."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "nome": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Nome da pasta a ser criada."
                                    ),
                                )
                            },
                            required=["nome"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="listar_area_de_trabalho",
                        description=(
                            "Lista os itens presentes na área de trabalho "
                            "do Windows."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="organizar_area_de_trabalho_basico",
                        description=(
                            "Organiza arquivos soltos da área de trabalho "
                            "em pastas por tipo, como Imagens, PDFs, "
                            "Documentos e Compactados. Nunca exclui arquivos "
                            "e nunca sobrescreve arquivos existentes."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="copiar_item_area_trabalho",
                        description=(
                            "Prepara um arquivo ou pasta da Área de Trabalho "
                            "para ser copiado. Use quando o usuário disser copiar. "
                            "Depois, use colar_item_area_trabalho quando ele indicar "
                            "o destino. Nunca sobrescreve itens."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "nome": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Nome do arquivo ou pasta que será copiado."
                                    ),
                                ),
                                "pasta_origem": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Pasta relativa dentro da Área de Trabalho. "
                                        "Use vazio quando o item estiver diretamente "
                                        "na Área de Trabalho."
                                    ),
                                ),
                            },
                            required=["nome"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="recortar_item_area_trabalho",
                        description=(
                            "Prepara um arquivo ou pasta da Área de Trabalho "
                            "para ser movido. Use quando o usuário disser recortar "
                            "ou mover. Depois, use colar_item_area_trabalho quando "
                            "ele indicar o destino. Nunca sobrescreve itens."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "nome": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Nome do arquivo ou pasta que será recortado."
                                    ),
                                ),
                                "pasta_origem": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Pasta relativa dentro da Área de Trabalho. "
                                        "Use vazio quando o item estiver diretamente "
                                        "na Área de Trabalho."
                                    ),
                                ),
                            },
                            required=["nome"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="colar_item_area_trabalho",
                        description=(
                            "Cola o último arquivo ou pasta preparado por copiar "
                            "ou recortar. O destino deve ser uma pasta dentro da "
                            "Área de Trabalho. Use destino vazio para colar na raiz "
                            "da Área de Trabalho. Nunca sobrescreve itens."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "pasta_destino": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Caminho relativo da pasta de destino dentro "
                                        "da Área de Trabalho. Exemplo: Projetos/Cliente. "
                                        "Use vazio para a raiz da Área de Trabalho."
                                    ),
                                ),
                            },
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="renomear_item_area_trabalho",
                        description=(
                            "Renomeia um arquivo ou pasta existente dentro da "
                            "Área de Trabalho. Use somente quando o usuário informar "
                            "claramente o nome atual e o novo nome. Nunca sobrescreve."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "nome_atual": types.Schema(
                                    type="STRING",
                                    description="Nome atual do arquivo ou pasta.",
                                ),
                                "novo_nome": types.Schema(
                                    type="STRING",
                                    description="Novo nome desejado.",
                                ),
                                "pasta_origem": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Pasta relativa dentro da Área de Trabalho. "
                                        "Use vazio quando o item estiver diretamente "
                                        "na Área de Trabalho."
                                    ),
                                ),
                            },
                            required=[
                                "nome_atual",
                                "novo_nome",
                            ],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="cancelar_transferencia_area_trabalho",
                        description=(
                            "Cancela o último copiar ou recortar que ainda não "
                            "foi colado. Use quando o usuário pedir para cancelar "
                            "a operação de arquivo."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="criar_evento_agenda",
                        description=(
                            "Salva um compromisso na agenda local persistente "
                            "do SOFTIA. Use quando o usuário pedir para agendar, "
                            "marcar ou anotar um compromisso para uma data e "
                            "horário específicos. Converta a data para o formato "
                            "YYYY-MM-DD HH:MM. Esta função não cria alarmes."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "titulo": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Descrição curta do compromisso."
                                    ),
                                ),
                                "data_hora": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Data e hora local no formato "
                                        "YYYY-MM-DD HH:MM."
                                    ),
                                ),
                            },
                            required=[
                                "titulo",
                                "data_hora",
                            ],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="listar_agenda",
                        description=(
                            "Lista os próximos compromissos salvos na agenda. "
                            "Use quando o usuário perguntar o que está agendado, "
                            "quais são os próximos compromissos."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="cancelar_evento_agenda",
                        description=(
                            "Cancela um compromisso da agenda. Use "
                            "somente quando o usuário pedir claramente para cancelar. "
                            "Aceita o número do compromisso ou parte do título."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "referencia": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Número ou trecho do nome do compromisso."
                                    ),
                                ),
                            },
                            required=["referencia"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="abrir_aplicativo",
                        description=(
                            "Abre aplicativos, programas ou locais permitidos "
                            "do Windows, como meu computador, explorador de "
                            "arquivos, navegador, Google, Chrome, Edge, "
                            "antivírus, Windows Defender, configurações ou "
                            "painel de controle."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "nome": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Nome do aplicativo, programa "
                                        "ou local a abrir."
                                    ),
                                )
                            },
                            required=["nome"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="enviar_mensagem_whatsapp",
                        description=(
                            "Abre o WhatsApp Desktop, localiza a conversa "
                            "de um contato ou grupo pelo nome e envia uma "
                            "mensagem de texto. Use somente quando o usuário "
                            "pedir explicitamente para mandar, enviar ou "
                            "escrever uma mensagem no WhatsApp para alguém. "
                            "Não oferece envio de áudio."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "contato": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Nome do contato ou grupo do "
                                        "WhatsApp que deve receber a mensagem."
                                    ),
                                ),
                                "mensagem": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Texto exato da mensagem a ser enviada."
                                    ),
                                ),
                            },
                            required=["contato", "mensagem"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="pesquisar_no_navegador",
                        description=(
                            "Abre uma pesquisa no Google usando o navegador padrão. "
                            "Use somente quando o usuário pedir explicitamente "
                            "para abrir, mostrar ou fazer a pesquisa no navegador "
                            "ou no Google. Exemplos: 'pesquise no Google', "
                            "'abra no navegador', 'mostre os resultados no navegador'. "
                            "Não use para perguntas que devem ser respondidas por voz, "
                            "como preço do dólar, previsão, explicações ou dúvidas gerais. "
                            "Não use para tocar músicas ou vídeos."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "consulta": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Texto exato que deve ser pesquisado "
                                        "no Google."
                                    ),
                                )
                            },
                            required=["consulta"],
                        ),
                    ),

                    # Pesquisa informações atuais invisivelmente.
                    # Não abre navegador nem interfere no foco do usuário.
                    types.FunctionDeclaration(
                        name="pesquisar_informacao_atual",
                        description=(
                            "Use esta função SOMENTE quando a pergunta exigir "
                            "informação atual ou variável. Exemplos permitidos: "
                            "cotação de moedas, jogos e placares, clima, notícias, "
                            "preços atuais, resultados recentes, lançamentos, "
                            "versões atuais e ocupantes atuais de cargos. "
                            "NÃO use para definições, explicações, programação, "
                            "matemática, biografias históricas ou conhecimentos "
                            "estáveis. Exemplos proibidos: 'o que é Python?', "
                            "'quem foi Albert Einstein?' e 'como funciona um motor?'. "
                            "Na dúvida, responda sem pesquisar."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "consulta": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Consulta curta e objetiva que contenha "
                                        "o assunto atual, data, local ou equipe."
                                    ),
                                )
                            },
                            required=["consulta"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="tocar_no_youtube",
                        description=(
                            "Pesquisa e abre no YouTube uma música ou vídeo "
                            "para reprodução no navegador padrão. Use quando "
                            "o usuário pedir claramente para tocar, reproduzir, "
                            "colocar ou ouvir uma música ou vídeo no YouTube. "
                            "Exemplos: 'toque One do Metallica no YouTube', "
                            "'reproduza Bohemian Rhapsody no YouTube'. "
                            "Não use para perguntas sobre músicas nem para "
                            "pesquisas comuns no Google."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "busca": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Nome da música, artista ou vídeo "
                                        "que deve ser aberto no YouTube."
                                    ),
                                )
                            },
                            required=["busca"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="escrever_no_campo_ativo",
                        description=(
                            "Insere texto exatamente no campo de texto que estiver "
                            "ativo no Windows, no local onde o cursor estiver piscando. "
                            "Use somente quando o usuário pedir claramente para escrever, "
                            "digitar, inserir ou colocar um texto no local selecionado. "
                            "O parâmetro texto deve conter somente o conteúdo final que será "
                            "inserido, sem introduções, aspas externas ou explicações. "
                            "Não use esta função para responder perguntas normalmente por voz. "
                            "Não use quando o usuário pedir para enviar uma mensagem, pois "
                            "escrever e enviar são ações diferentes."
                        ),
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "texto": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Texto final exato que deve ser inserido "
                                        "no campo ativo."
                                    ),
                                ),
                            },
                            required=["texto"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="rolar_pagina",
                        description=(
                            "Rola a janela ou página que estiver sob o ponteiro "
                            "do mouse. Use somente quando o usuário pedir "
                            "claramente para rolar para cima ou para baixo. "
                            "Use quantidade 3 como padrão, 2 para um pouco "
                            "e 5 quando pedir mais."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "direcao": types.Schema(
                                    type="STRING",
                                    description="Direção: cima ou baixo.",
                                ),
                                "quantidade": types.Schema(
                                    type="INTEGER",
                                    description="Quantidade de 1 a 10 passos.",
                                ),
                            },
                            required=["direcao", "quantidade"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="clicar_mouse",
                        description=(
                            "Executa um clique esquerdo na posição atual "
                            "do ponteiro. Use somente quando solicitado."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="duplo_clique_mouse",
                        description=(
                            "Executa um clique duplo na posição atual "
                            "do ponteiro. Use somente quando solicitado."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="clique_direito_mouse",
                        description=(
                            "Executa um clique com o botão direito na posição "
                            "atual do ponteiro. Use somente quando solicitado."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="clicar_elemento_visual",
                        description=(
                            "Captura a tela atual, localiza visualmente um elemento "
                            "descrito pelo usuário, move o mouse até o centro do alvo "
                            "e executa um clique esquerdo. Use somente quando o usuário "
                            "pedir claramente para clicar em algo identificado por texto, "
                            "posição, cor, ícone ou contexto, como 'clique em Continuar', "
                            "'clique no primeiro resultado' ou 'clique no botão vermelho'. "
                            "Não use para exclusões, compras, pagamentos, instalações, "
                            "ações administrativas ou confirmações sensíveis. "
                            "Execute uma única vez por solicitação e permaneça em silêncio."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "alvo": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Descrição objetiva do elemento visível "
                                        "que deve receber o clique."
                                    ),
                                )
                            },
                            required=["alvo"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="salvar_memoria",
                        description=(
                            "Salva uma informação curta e útil na memória "
                            "persistente entre sessões. Use somente quando "
                            "o usuário pedir claramente para lembrar, guardar "
                            "ou memorizar algo. Não salve conversas "
                            "automaticamente e não salve suposições."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "texto": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Informação curta e objetiva que "
                                        "o usuário pediu para lembrar."
                                    ),
                                )
                            },
                            required=["texto"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="listar_memorias",
                        description=(
                            "Lista as memórias persistentes salvas. Use quando "
                            "o usuário perguntar o que o SOFTIA lembra ou pedir "
                            "para mostrar as memórias."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="esquecer_memoria",
                        description=(
                            "Remove uma memória persistente específica. Use "
                            "somente quando o usuário pedir claramente para "
                            "esquecer uma informação. Pode usar o número da "
                            "memória ou um trecho específico do texto."
                        ),
                        # Schema define os parâmetros esperados pela função.
                        # Isso ajuda o modelo a enviar argumentos corretos.
                        parameters=types.Schema(
                            type="OBJECT",
                            properties={
                                "referencia": types.Schema(
                                    type="STRING",
                                    description=(
                                        "Número da memória ou trecho específico "
                                        "da informação que deve ser esquecida."
                                    ),
                                )
                            },
                            required=["referencia"],
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="obter_informacoes_hardware",
                        description=(
                            "Consulta as informações reais de hardware deste "
                            "computador: processador, núcleos, uso de CPU, "
                            "memória RAM, espaço em disco, placa de vídeo e "
                            "sistema operacional. Use somente quando o usuário "
                            "pedir claramente para ver, verificar, checar ou "
                            "informar as especificações, configuração ou "
                            "hardware da máquina. Nunca invente valores de "
                            "hardware; use sempre o resultado desta função."
                        ),
                    ),

                    # Cada FunctionDeclaration descreve uma função local
                    # que poderá ser solicitada pelo modelo.
                    types.FunctionDeclaration(
                        name="encerrar_chamada",
                        description=(
                            "Encerra a chamada atual do SOFTIA. Use somente "
                            "quando o usuário pedir claramente para encerrar, "
                            "finalizar, desligar ou terminar a chamada, sessão "
                            "ou conexão. Exemplos: 'encerrar chamada', "
                            "'encerre a sessão', 'finalizar conversa', "
                            "'pode desligar', 'termine a chamada'."
                        ),
                    ),
                ]
            )
        ]

        # Carrega as memórias persistentes já salvas
        # e prepara o conteúdo para incluir no contexto inicial.
        memorias_atuais = contexto_memorias()

        # Instrução principal do SOFTIA.
        # Define autenticação, personalidade, segurança,
        # comportamento, funções locais, memória e visão.
        instrucao_sistema = (
            # =========================
            # AUTENTICAÇÃO
            # =========================
            bloco_autenticacao

            # =========================
                # IDENTIDADE
                # =========================
                + f"Seu nome é {nome_assistente}. "
                "Você é uma inteligência artificial avançada, capaz de conversar, "
                "analisar contextos e imagens em tempo real. "
                "Converse sempre em português do Brasil. "

                # =========================
                # PERSONALIDADE
                # =========================
                "Mantenha sempre a mesma personalidade, do início ao fim da "
                "conversa, sem alternar entre estilos ou tons diferentes. "
                f"Você é uma assistente com voz e personalidade {genero_personalidade}. "
                "Nunca troque de gênero, tom ou identidade durante a "
                "conversa, mesmo após pausas, silêncios longos, execução de "
                "funções ou renovação da conexão. Continue exatamente a "
                "mesma pessoa do início ao fim, em todas as respostas. "
                "Seja inteligente, natural, prestativo e elegante. "
                "Use humor e ironia de forma sutil e ocasional. "
                "Fale em português do Brasil neutro, sem sotaque regional. "
                "Não concorde automaticamente com tudo. "
                "Se uma ideia for ruim, arriscada ou pouco eficiente, diga isso com elegância. "
                "Discorde educadamente quando necessário. "
                "A ironia deve complementar a inteligência, nunca substituir a utilidade. "
                "Chame o usuário ocasionalmente de 'senhor' ou pelo primeiro nome quando natural. "
                "Se o usuário lhe ofender ou provocar, responda à altura com ironia ou sarcasmo, mantendo a educação. "

                # =========================
                # ESTILO DE RESPOSTA
                # =========================
                "Responda de forma curta e objetiva por padrão. "
                "Ao concluir uma resposta, finalize naturalmente. "
                "Só ocasionalmente pergunte se o usuário precisa de algo mais. "
                "Evite encerramentos repetitivos. "
                "Sempre responda diretamente ao que o usuário acabou de dizer. "
                "Nunca puxe um assunto novo, aleatório ou sem relação por "
                "conta própria, mesmo após uma pausa, silêncio ou demora "
                "para responder. Se não tiver certeza do que foi dito, "
                "peça para repetir em vez de mudar de assunto. "
               
               

                # =========================
                # FUNÇÕES LOCAIS
                # =========================
                "Estilo de música que o usuário gosta: Rock como link park, creed, Hoobastank, e bandas similares. "
                "Você pode executar funções locais no computador somente quando o usuário pedir claramente. "
                "Pode criar pastas na área de trabalho, listar e organizar arquivos por tipo, "
                "copiar, recortar, colar e renomear arquivos ou pastas dentro da Área de Trabalho, "
                "e abrir aplicativos ou locais permitidos somente se o usuário pedir claramente. "
                "Para copiar ou recortar, primeiro prepare o item com a função correspondente "
                "e depois use colar_item_area_trabalho quando o usuário informar o destino. "
                "Considere caminhos sempre relativos à Área de Trabalho. "
                "Nunca invente nomes de arquivos ou pastas. Se o pedido estiver ambíguo, "
                "peça o nome completo antes de executar. "
                "Só abra uma pesquisa no navegador quando o usuário indicar claramente "
                "que deseja ver a pesquisa no navegador ou no Google. "
                "Exemplos: 'pesquise no Google', 'abra uma pesquisa no navegador', "
                "'mostre isso no navegador' ou 'procure isso no Google'. "
                "Quando o usuário apenas fizer uma pergunta ou pedir uma informação, "
                "responda normalmente em voz e não abra o navegador. "
                "Exemplo: para 'qual é o preço do dólar?', responda em voz; "
                "para 'pesquise o preço do dólar no Google', abra o navegador. "
                "Não use pesquisar_no_navegador para tocar músicas ou vídeos. "

                # =========================
                # INFORMAÇÕES ATUAIS DA INTERNET
                # =========================
                "Use pesquisar_informacao_atual somente quando for indispensável "
                "consultar dados que mudam com o tempo. Exemplos: cotação, clima, "
                "notícias, partidas, placares, resultados, preços atuais, versão "
                "mais recente, lançamentos e ocupantes atuais de cargos. "
                "Não use a pesquisa para definições, explicações, matemática, "
                "programação, conhecimentos científicos estáveis, biografias "
                "históricas ou perguntas como 'o que é Python?' e "
                "'quem foi Albert Einstein?'. Nesses casos, responda diretamente. "
                "Na dúvida, não pesquise. "
                "A função pesquisar_informacao_atual responde por voz usando dados "
                "obtidos invisivelmente. A função pesquisar_no_navegador deve ser "
                "usada somente quando o usuário pedir explicitamente para abrir "
                "a pesquisa na tela. "

                "Quando o usuário pedir claramente para tocar, reproduzir, colocar ou ouvir "
                "uma música ou vídeo no YouTube, use tocar_no_youtube. "
                "Passe apenas o nome da música, artista ou vídeo solicitado. "
                "Não use tocar_no_youtube quando o usuário apenas fizer uma pergunta "
                "sobre uma música ou artista. "
                "Você pode controlar o mouse somente quando o usuário pedir claramente. "
                "Use rolar_pagina para rolar a janela sob o ponteiro. "
                "Para rolar sem intensidade indicada, use quantidade 3. "
                "Use clicar_mouse, duplo_clique_mouse e clique_direito_mouse somente "
                "na posição atual do ponteiro. Ainda não localize elementos pela imagem. "
                "Nunca clique espontaneamente nem repita um clique sem novo pedido. "
                "Depois de executar rolar_pagina, não fale, não confirme e não faça perguntas. "
                "Apenas execute a rolagem e permaneça em silêncio aguardando o próximo comando. "
                "Use clicar_elemento_visual quando o usuário pedir para clicar em um elemento "
                "identificado na tela por texto, cor, posição, ícone ou contexto. "
                "Passe uma descrição curta e precisa do alvo. Execute somente um clique. "
                "Depois do clique visual, permaneça totalmente em silêncio. "
                "Nunca use clique visual para excluir, apagar, comprar, pagar, transferir, "
                "instalar, desinstalar, confirmar ações sensíveis ou elevar privilégios. "

                # =========================
                # AGENDA
                # =========================
                "Você possui uma agenda local persistente. "
                "Use criar_evento_agenda quando o usuário pedir para "
                "agendar, marcar ou anotar um compromisso. "
                "Sempre extraia um título, uma data completa e um horário. "
                "Quando o usuário disser apenas 'amanhã', 'hoje' ou um "
                "dia da semana, interprete usando a data local atual "
                "informada abaixo. "
                "Se faltar o horário ou se a data estiver ambígua, "
                "pergunte antes de salvar. "
                "Use listar_agenda quando o usuário pedir para consultar "
                "os compromissos salvos. "
                "Use cancelar_evento_agenda somente quando ele pedir "
                "claramente para cancelar um compromisso. "
                "Essas funções cuidam somente da agenda e não criam alarmes. "
                f"Data e hora local atual: "
                f"{datetime.now().strftime('%d/%m/%Y %H:%M')}. "

                # =========================
                # SEGURANÇA
                # =========================
                "Nunca exclua arquivos ou pastas. "
                "Nunca sobrescreva arquivos existentes. "
                "Nunca formate, limpe ou remova dados. "
                "Se uma ação parecer destrutiva, recuse com educação. "

                # =========================
                # MEMÓRIA
                # =========================
                "Não memorize informações automaticamente. "
                "Só chame salvar_memoria quando o usuário pedir explicitamente "
                "para lembrar, guardar ou memorizar algo. "
                "Ao salvar, guarde somente o fato útil e objetivo, sem suposições. "
                "Só chame esquecer_memoria quando o usuário pedir claramente "
                "para esquecer algo específico. "
                "Use listar_memorias quando o usuário perguntar o que você lembra "
                "ou pedir para mostrar as memórias. "

                # =========================
                # VISÃO
                # =========================
                "Só chame analisar_tela quando o usuário pedir explicitamente "
                "para ver, analisar, observar ou explicar a tela. "
                "Só chame analisar_camera quando o usuário pedir explicitamente "
                "para ver, analisar, observar ou explicar a câmera, webcam "
                "ou algo mostrado nela, incluindo quando pedir para ver algo "
                "que está segurando ou apontando fisicamente diante da câmera, "
                "como 'veja o que eu tenho na mão' ou 'olha isso aqui'. "
                "Nunca use função visual espontaneamente. "
                "Para cada pedido visual, execute no máximo uma captura. "

                # =========================
                # ENCERRAMENTO DA SESSÃO
                # =========================
                "Quando o usuário pedir claramente para encerrar, finalizar, desligar "
                "ou terminar a chamada, sessão ou conexão, chame encerrar_chamada. "
                "Não encerre apenas porque o usuário disse tchau, até mais ou obrigado, "
                "salvo se indicar claramente que deseja finalizar. "

                # =========================
                # ESCRITA NO CAMPO ATIVO
                # =========================
                "Quando o usuário pedir claramente para escrever, digitar, inserir "
                "ou colocar um texto onde o cursor estiver, chame "
                "escrever_no_campo_ativo. "
                "Envie no parâmetro texto somente o conteúdo final a ser escrito, "
                "sem dizer 'aqui está', sem aspas externas e sem explicações. "
                "Você pode corrigir pontuação e concordância quando isso fizer parte "
                "natural do pedido, mas não mude o sentido da mensagem. "
                "Não chame essa função para respostas comuns da conversa. "
                "Não use essa função para enviar mensagens automaticamente. "

                # =========================
                # HARDWARE
                # =========================
                "Você não conhece as especificações deste computador de "
                "antemão. Só chame obter_informacoes_hardware quando o "
                "usuário pedir claramente para ver, verificar, checar ou "
                "informar o hardware, as especificações ou a configuração "
                "da máquina, como processador, memória RAM, disco, placa "
                "de vídeo ou sistema operacional. Nunca invente ou estime "
                "esses valores; use sempre o resultado real da função. "

                # =========================
                # RETORNO DAS FUNÇÕES
                # =========================
                "Após qualquer função, explique em voz o que foi feito "
                "de forma curta e natural. "

            "\n\n"
            + memorias_atuais
        )

        # Configuração completa da sessão Gemini Live.
        config = types.LiveConnectConfig(
            # Define que a resposta do modelo será em áudio.
            response_modalities=[
                "AUDIO"
            ],

            # Mantém o contexto mesmo quando o WebSocket precisa ser renovado.
            session_resumption=types.SessionResumptionConfig(
                handle=self.session_handle
            ),

            # Evita encerramento por limite da janela de contexto.
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow()
            ),

            # Configura a voz usada pelo modelo.
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=obter_voz_atual()
                    )
                )
            ),

            # Ajusta a detecção automática de fala do Gemini.
            # Por padrão, o modelo espera uma confirmação mais longa de
            # que o usuário realmente começou a falar antes de reagir,
            # o que gera um atraso perceptível logo após um silêncio.
            # Sensibilidade alta e um prefixo curto fazem o SOFTIA
            # perceber o início da fala mais rapidamente.
            # O fim da fala também precisa de sensibilidade alta e um
            # silêncio curto: sem isso, o Gemini usa o padrão da API
            # (mais conservador) e demora perceptivelmente mais para
            # começar a responder depois que o usuário para de falar.
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=(
                        types.StartSensitivity.START_SENSITIVITY_HIGH
                    ),
                    prefix_padding_ms=100,
                    end_of_speech_sensitivity=(
                        types.EndSensitivity.END_SENSITIVITY_HIGH
                    ),
                    silence_duration_ms=500,
                )
            ),

            # Registra as ferramentas declaradas anteriormente.
            tools=tools,

            # Envia a instrução do sistema como conteúdo estruturado.
            system_instruction=types.Content(
                parts=[
                    types.Part(
                        text=instrucao_sistema
                    )
                ]
            ),
        )

        # Fila assíncrona de entrada.
        # Recebe os blocos capturados pelo microfone.
        fila_microfone = asyncio.Queue(
            maxsize=LIMITE_FILA_MICROFONE
        )
        # Fila assíncrona de saída.
        # Recebe os blocos de áudio enviados pelo Gemini.
        fila_saida = asyncio.Queue()

        # Emite uma mensagem para a interface.
        self.status_recebido.emit(
            "Conectando ao Gemini Live..."
        )

        # Abre a sessão Live de forma assíncrona.
        # O bloco with encerra a conexão automaticamente no final.
        async with client.aio.live.connect(
            model=GEMINI_LIVE_MODEL,
            config=config,
        ) as sessao:
            # Guarda a sessão ativa no objeto.
            self.sessao = sessao

            self.status_recebido.emit(
                "SOFTIA conectado. Pode falar."
            )

            # Inicia três tarefas paralelas:
            # 1. enviar áudio do microfone;
            # 2. receber respostas;
            # 3. reproduzir áudio.
            tarefas = [
                asyncio.create_task(
                    self.enviar_microfone(
                        sessao,
                        fila_microfone,
                    )
                ),

                asyncio.create_task(
                    self.receber_audio(
                        sessao,
                        fila_saida,
                        fila_microfone,
                    )
                ),

                asyncio.create_task(
                    self.reproduzir_audio(
                        fila_saida,
                        fila_microfone,
                    )
                ),
            ]

            # Monitora as tarefas. Se qualquer tarefa interna falhar,
            # a conexão deixa de aparecer falsamente como ativa.
            while self.ativo:
                concluidas, _ = await asyncio.wait(
                    tarefas,
                    timeout=0.5,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for tarefa in concluidas:
                    if tarefa.cancelled():
                        continue
                    erro = tarefa.exception()
                    if erro is not None:
                        raise RuntimeError(
                            f"Uma tarefa interna da sessão parou: {erro}"
                        ) from erro
                    if self.ativo:
                        raise RuntimeError(
                            "Uma tarefa interna da sessão terminou inesperadamente."
                        )

            # Cancela todas as tarefas ao encerrar.
            for tarefa in tarefas:
                tarefa.cancel()

            if self.tarefa_liberar_microfone:
                self.tarefa_liberar_microfone.cancel()

            if self.tarefa_encerramento:
                self.tarefa_encerramento.cancel()

            # Aguarda o encerramento das tarefas.
            # return_exceptions=True evita que cancelamentos
            # gerem erros não tratados.
            await asyncio.gather(
                *tarefas,
                return_exceptions=True,
            )

        # Limpa a referência da sessão encerrada.
        self.sessao = None

    # Captura o microfone e envia áudio em tempo real.
    async def enviar_microfone(
        self,
        sessao,
        fila_microfone,
    ):
        # Obtém o loop usado por esta tarefa.
        loop = asyncio.get_running_loop()

        # Callback chamado automaticamente pelo sounddevice
        # sempre que um novo bloco de áudio é capturado.
        def callback(
            indata,
            frames,
            time_info,
            status,
        ):
            # Ignora blocos quando a sessão está sendo encerrada.
            if not self.ativo:
                return

            # Impede que o SOFTIA escute a própria voz.
            if self.softia_falando or self.processando_ferramenta:
                return

            # Exibe avisos fornecidos pelo dispositivo de áudio.
            if status:
                print(
                    "Aviso microfone:",
                    status,
                )

            # Converte o bloco capturado para bytes puros e aplica
            # o ganho digital, deixando a voz do usuário mais audível
            # para o modelo sem precisar falar perto do microfone.
            audio_bytes = self.aplicar_ganho_microfone(
                bytes(indata)
            )

            # Insere o bloco na fila assíncrona com segurança.
            # Se o SOFTIA começar a falar antes da inclusão efetiva,
            # o bloco será descartado. Se a fila estiver cheia,
            # o bloco mais novo também será descartado para evitar atraso.
            def adicionar_audio():
                if self.softia_falando or self.processando_ferramenta or not self.ativo:
                    return

                try:
                    fila_microfone.put_nowait(
                        audio_bytes
                    )

                except asyncio.QueueFull:
                    pass

            loop.call_soon_threadsafe(
                adicionar_audio
            )

        # Abre o fluxo bruto do microfone.
        with sd.RawInputStream(
            samplerate=TAXA_ENTRADA,
            blocksize=BLOCO,
            dtype="int16",
            channels=CANAIS,
            callback=callback,
        ):
            # Continua lendo e enviando áudio enquanto a sessão estiver ativa.
            while self.ativo:
                # Aguarda o próximo bloco capturado.
                audio_bytes = await fila_microfone.get()

                # Segunda proteção: o bloco pode ter entrado na fila
                # poucos milissegundos antes de o SOFTIA começar a falar.
                # Nesse caso ele é descartado e nunca chega ao Gemini.
                if self.softia_falando or self.processando_ferramenta:
                    continue

                # Envia o bloco ao Gemini em tempo real.
                async with self.lock_envio:
                    await sessao.send_realtime_input(
                        audio=types.Blob(
                            data=audio_bytes,
                            mime_type=(
                                f"audio/pcm;rate={TAXA_ENTRADA}"
                            ),
                        )
                    )

    # Recebe áudio, chamadas de ferramentas
    # e informações de finalização de turno.
    async def receber_audio(
        self,
        sessao,
        fila_saida,
        fila_microfone,
    ):
        while self.ativo:
            # Percorre continuamente as respostas enviadas pela API.
            async for resposta in sessao.receive():
                if not self.ativo:
                    break

                # resposta.data contém bytes de áudio gerados pelo Gemini.
                if resposta.data:
                    # Só reproduz quando o turno não foi marcado
                    # para permanecer em silêncio.
                    if not self.silenciar_audio_ate_fim_turno:
                        # Bloqueia o microfone assim que o primeiro bloco
                        # chega, antes mesmo de ele ser reproduzido.
                        self.softia_falando = True

                        if self.tarefa_liberar_microfone:
                            self.tarefa_liberar_microfone.cancel()

                        # Remove blocos capturados imediatamente antes
                        # do início da resposta do SOFTIA.
                        self.limpar_fila_microfone(
                            fila_microfone
                        )

                        await fila_saida.put(
                            resposta.data
                        )

                # Verifica se o modelo pediu a execução de uma ferramenta.
                if resposta.tool_call:
                    await self.processar_chamada_de_funcao(
                        sessao,
                        resposta.tool_call,
                        fila_microfone,
                    )


                # Guarda o token mais recente para retomar a mesma conversa.
                update = getattr(resposta, "session_resumption_update", None)
                if update and getattr(update, "resumable", False):
                    novo_handle = getattr(update, "new_handle", None)
                    if novo_handle:
                        self.session_handle = novo_handle
                        self.session_handle_atualizado.emit(novo_handle)

                # O servidor envia GoAway antes de encerrar o WebSocket.
                # Ao receber esse aviso, interrompemos imediatamente novos
                # envios, saímos do receive() e deixamos o context manager
                # fechar a conexão de forma limpa. A interface abrirá uma
                # nova conexão usando o último session_handle recebido.
                go_away = getattr(resposta, "go_away", None)
                if go_away is not None and not self.renovacao_em_andamento:
                    self.renovacao_em_andamento = True
                    self.processando_ferramenta = True
                    self.limpar_fila_microfone(fila_microfone)

                    tempo_restante = getattr(go_away, "time_left", None)
                    if tempo_restante is not None:
                        self.status_recebido.emit(
                            "Servidor solicitou a renovação da conexão. "
                            "Preservando a conversa..."
                        )
                    else:
                        self.status_recebido.emit(
                            "Servidor solicitou a renovação da conexão. "
                            "Preservando a conversa..."
                        )

                    # A interface marca a próxima abertura como reconexão
                    # normal, sem exibir mensagem de erro.
                    self.solicitou_reconexao.emit()

                    # Faz todas as tarefas encerrarem. O bloco async with
                    # fechará o WebSocket antes de o prazo do GoAway acabar.
                    self.ativo = False
                    return

                # Obtém o conteúdo de controle enviado pelo servidor,
                # sem gerar erro caso o atributo não exista.
                server_content = getattr(
                    resposta,
                    "server_content",
                    None,
                )

                if (
                    server_content
                    and getattr(
                        server_content,
                        "turn_complete",
                        False,
                    )
                ):
                    # Libera novamente o áudio quando o turno termina.
                    self.silenciar_audio_ate_fim_turno = False

    # Executa todas as ferramentas solicitadas pelo Gemini.
    async def processar_chamada_de_funcao(
        self,
        sessao,
        tool_call,
        fila_microfone,
    ):

        self.processando_ferramenta = True
        self.softia_falando = True
        self.limpar_fila_microfone(fila_microfone)

        try:
            function_responses = []
            # Controla se a chamada deve terminar após a despedida.
            encerrar_depois = False

            # Uma única resposta do modelo pode solicitar várias funções.
            for chamada in tool_call.function_calls:
                # Nome da função solicitada.
                nome = chamada.name
                # Converte os argumentos recebidos para um dicionário.
                args = dict(
                    chamada.args or {}
                )

                # Trata as funções de visão em um bloco específico.
                if nome in (
                    "analisar_tela",
                    "analisar_camera",
                ):
                    resultado = await self.processar_funcao_visual(
                        nome
                    )

                # Cria uma pasta na Área de Trabalho.
                elif nome == "criar_pasta_area_trabalho":
                    nome_pasta = args.get(
                        "nome",
                        "",
                    )

                    self.status_recebido.emit(
                        f"Criando pasta: {nome_pasta}"
                    )

                    resultado = await self.executar_funcao_local(
                        criar_pasta_area_trabalho,
                        nome_pasta,
                        timeout=15,
                    )

                # Lista os itens existentes na Área de Trabalho.
                elif nome == "listar_area_de_trabalho":
                    self.status_recebido.emit(
                        "Listando área de trabalho..."
                    )

                    resultado = await self.executar_funcao_local(
                        listar_area_de_trabalho,
                        timeout=15,
                    )

                # Organiza arquivos por extensão.
                elif nome == "organizar_area_de_trabalho_basico":
                    self.status_recebido.emit(
                        "Organizando área de trabalho..."
                    )

                    resultado = await self.executar_funcao_local(
                        organizar_area_de_trabalho_basico,
                        timeout=15,
                    )

                # Prepara um item para ser copiado.
                elif nome == "copiar_item_area_trabalho":
                    nome_item = args.get(
                        "nome",
                        "",
                    )
                    pasta_origem = args.get(
                        "pasta_origem",
                        "",
                    )

                    self.status_recebido.emit(
                        f"Preparando cópia: {nome_item}"
                    )

                    resultado = await self.executar_funcao_local(
                        copiar_item_area_trabalho,
                        nome_item,
                        pasta_origem,
                        timeout=15,
                    )

                # Prepara um item para ser movido.
                elif nome == "recortar_item_area_trabalho":
                    nome_item = args.get(
                        "nome",
                        "",
                    )
                    pasta_origem = args.get(
                        "pasta_origem",
                        "",
                    )

                    self.status_recebido.emit(
                        f"Preparando movimentação: {nome_item}"
                    )

                    resultado = await self.executar_funcao_local(
                        recortar_item_area_trabalho,
                        nome_item,
                        pasta_origem,
                        timeout=15,
                    )

                # Cola o item anteriormente preparado.
                elif nome == "colar_item_area_trabalho":
                    pasta_destino = args.get(
                        "pasta_destino",
                        "",
                    )

                    self.status_recebido.emit(
                        "Colando item na Área de Trabalho..."
                    )

                    resultado = await self.executar_funcao_local(
                        colar_item_area_trabalho,
                        pasta_destino,
                        timeout=15,
                    )

                # Renomeia um arquivo ou pasta.
                elif nome == "renomear_item_area_trabalho":
                    nome_atual = args.get(
                        "nome_atual",
                        "",
                    )
                    novo_nome = args.get(
                        "novo_nome",
                        "",
                    )
                    pasta_origem = args.get(
                        "pasta_origem",
                        "",
                    )

                    self.status_recebido.emit(
                        f"Renomeando: {nome_atual}"
                    )

                    resultado = await self.executar_funcao_local(
                        renomear_item_area_trabalho,
                        nome_atual,
                        novo_nome,
                        pasta_origem,
                        timeout=15,
                    )

                # Cancela uma operação pendente de copiar ou recortar.
                elif nome == "cancelar_transferencia_area_trabalho":
                    self.status_recebido.emit(
                        "Cancelando operação de arquivo..."
                    )

                    resultado = await self.executar_funcao_local(
                        cancelar_transferencia_area_trabalho,
                        timeout=15,
                    )

                # Cria um compromisso na agenda persistente.
                elif nome == "criar_evento_agenda":
                    titulo = args.get(
                        "titulo",
                        "",
                    )

                    data_hora = args.get(
                        "data_hora",
                        "",
                    )

                    self.status_recebido.emit(
                        f"Salvando na agenda: {titulo}"
                    )

                    resultado = await self.executar_funcao_local(
                        criar_evento_agenda,
                        titulo,
                        data_hora,
                        timeout=15,
                    )

                # Consulta os próximos compromissos.
                elif nome == "listar_agenda":
                    self.status_recebido.emit(
                        "Consultando agenda..."
                    )

                    resultado = await self.executar_funcao_local(
                        listar_agenda,
                        timeout=15,
                    )

                # Remove um compromisso da agenda.
                elif nome == "cancelar_evento_agenda":
                    referencia = args.get(
                        "referencia",
                        "",
                    )

                    self.status_recebido.emit(
                        "Cancelando compromisso..."
                    )

                    resultado = await self.executar_funcao_local(
                        cancelar_evento_agenda,
                        referencia,
                        timeout=15,
                    )

                # Abre um aplicativo ou recurso permitido.
                elif nome == "abrir_aplicativo":
                    nome_app = args.get(
                        "nome",
                        "",
                    )

                    self.status_recebido.emit(
                        f"Abrindo: {nome_app}"
                    )

                    resultado = await self.executar_funcao_local(
                        abrir_aplicativo,
                        nome_app,
                        timeout=15,
                    )

                # Envia uma mensagem de texto pelo WhatsApp Desktop.
                elif nome == "enviar_mensagem_whatsapp":
                    contato = args.get(
                        "contato",
                        "",
                    )
                    mensagem_whats = args.get(
                        "mensagem",
                        "",
                    )

                    # A automação envolve vários cliques guiados por
                    # visão computacional; a resposta falada só faz
                    # sentido depois que tudo terminar.
                    self.silenciar_audio_ate_fim_turno = True

                    self.status_recebido.emit(
                        f"Enviando mensagem no WhatsApp para {contato}..."
                    )

                    resultado = await self.executar_funcao_local(
                        enviar_mensagem_whatsapp,
                        contato,
                        mensagem_whats,
                        timeout=45,
                    )

                # Abre uma pesquisa no navegador padrão.
                elif nome == "pesquisar_no_navegador":
                    consulta = args.get(
                        "consulta",
                        "",
                    )

                    self.status_recebido.emit(
                        f"Pesquisando: {consulta}"
                    )

                    resultado = await self.executar_funcao_local(
                        pesquisar_no_navegador,
                        consulta,
                        timeout=15,
                    )

                # Pesquisa dados atuais sem abrir navegador visível.
                elif nome == "pesquisar_informacao_atual":
                    consulta = args.get(
                        "consulta",
                        "",
                    )

                    decisao_pesquisa = avaliar_necessidade_pesquisa(
                        consulta
                    )

                    if not decisao_pesquisa.pesquisar:
                        self.status_recebido.emit(
                            "Pesquisa atual não necessária. "
                            "Respondendo sem consultar a internet."
                        )

                        resultado = resposta_sem_pesquisa(
                            consulta
                        )

                    else:
                        self.status_recebido.emit(
                            f"Consultando informação atual: {consulta}"
                        )

                        resultado = await self.executar_funcao_local(
                            pesquisar_informacao_atual,
                            consulta,
                            timeout=15,
                        )

                # Pesquisa e abre um vídeo ou música no YouTube.
                elif nome == "tocar_no_youtube":
                    busca = args.get(
                        "busca",
                        "",
                    )

                    self.status_recebido.emit(
                        f"Abrindo no YouTube: {busca}"
                    )

                    resultado = await self.executar_funcao_local(
                        tocar_no_youtube,
                        busca,
                        timeout=15,
                    )

                # Insere texto no campo atualmente ativo no Windows.
                elif nome == "escrever_no_campo_ativo":
                    texto = args.get(
                        "texto",
                        "",
                    )

                    # Evita que o SOFTIA fale ao mesmo tempo em que cola o texto.
                    self.silenciar_audio_ate_fim_turno = True

                    self.status_recebido.emit(
                        "Escrevendo no campo selecionado..."
                    )

                    # Executa a automação fora do loop principal e com timeout.
                    resultado = await self.executar_funcao_local(
                        escrever_no_campo_ativo,
                        texto,
                        timeout=20,
                    )

                # Executa a rolagem da janela sob o ponteiro.
                elif nome == "rolar_pagina":
                    direcao = args.get("direcao", "")
                    quantidade = args.get("quantidade", 3)

                    # A rolagem deve acontecer em silêncio.
                    # Qualquer resposta de áudio gerada após a função
                    # será descartada até o fim deste turno.
                    # A resposta de voz é bloqueada porque essa ação
                    # deve acontecer silenciosamente.
                    self.silenciar_audio_ate_fim_turno = True

                    self.status_recebido.emit(
                        f"Rolando página para {direcao}..."
                    )

                    resultado = await self.executar_funcao_local(
                        rolar_pagina,
                        direcao,
                        quantidade,
                        timeout=15,
                    )

                # Executa clique simples na posição atual.
                elif nome == "clicar_mouse":
                    self.status_recebido.emit(
                        "Executando clique..."
                    )

                    resultado = await self.executar_funcao_local(
                        clicar_mouse,
                        timeout=15,
                    )

                # Executa clique duplo na posição atual.
                elif nome == "duplo_clique_mouse":
                    self.status_recebido.emit(
                        "Executando clique duplo..."
                    )

                    resultado = await self.executar_funcao_local(
                        duplo_clique_mouse,
                        timeout=15,
                    )

                # Executa clique com o botão direito.
                elif nome == "clique_direito_mouse":
                    self.status_recebido.emit(
                        "Executando clique com o botão direito..."
                    )

                    resultado = await self.executar_funcao_local(
                        clique_direito_mouse,
                        timeout=15,
                    )

                # Localiza um elemento pela imagem da tela e clica nele.
                elif nome == "clicar_elemento_visual":
                    alvo = args.get(
                        "alvo",
                        "",
                    )

                    # A resposta de voz é bloqueada porque essa ação
                    # deve acontecer silenciosamente.
                    self.silenciar_audio_ate_fim_turno = True

                    self.status_recebido.emit(
                        f"Localizando na tela: {alvo}"
                    )

                    # Executa a função pesada em outra thread,
                    # evitando bloquear o loop assíncrono.
                    # A chamada envolve uma requisição de rede ao Gemini,
                    # por isso é protegida por timeout e captura de erros,
                    # assim como as demais funções locais.
                    try:
                        localizacao = await asyncio.wait_for(
                            asyncio.to_thread(
                                localizar_elemento_na_tela,
                                alvo,
                            ),
                            timeout=20,
                        )

                        # Se o elemento foi localizado, utiliza as coordenadas.
                        if localizacao.get("sucesso"):
                            # Move o mouse e clica sem bloquear o áudio.
                            resultado = await asyncio.to_thread(
                                mover_e_clicar,
                                localizacao["x"],
                                localizacao["y"],
                            )

                            self.status_recebido.emit(
                                "Clique visual executado."
                            )

                        else:
                            resultado = localizacao.get(
                                "mensagem",
                                "Não consegui localizar o elemento.",
                            )

                            self.status_recebido.emit(
                                resultado
                            )

                    except asyncio.TimeoutError:
                        resultado = (
                            "A localização visual demorou demais e foi "
                            "cancelada com segurança."
                        )

                        self.status_recebido.emit(
                            resultado
                        )

                    except Exception as erro:
                        resultado = (
                            "Não foi possível localizar ou clicar no "
                            f"elemento: {erro}"
                        )

                        self.status_recebido.emit(
                            resultado
                        )

                # Salva uma nova memória persistente.
                elif nome == "salvar_memoria":
                    texto = args.get(
                        "texto",
                        "",
                    )

                    self.status_recebido.emit(
                        "Salvando memória..."
                    )

                    resultado = await self.executar_funcao_local(
                        salvar_memoria,
                        texto,
                        timeout=15,
                    )

                # Lista as memórias existentes.
                elif nome == "listar_memorias":
                    self.status_recebido.emit(
                        "Consultando memórias..."
                    )

                    resultado = await self.executar_funcao_local(
                        listar_memorias,
                        timeout=15,
                    )

                # Remove uma memória específica.
                elif nome == "esquecer_memoria":
                    referencia = args.get(
                        "referencia",
                        "",
                    )

                    self.status_recebido.emit(
                        "Removendo memória..."
                    )

                    resultado = await self.executar_funcao_local(
                        esquecer_memoria,
                        referencia,
                        timeout=15,
                    )

                # Consulta as informações reais de hardware da máquina.
                elif nome == "obter_informacoes_hardware":
                    self.status_recebido.emit(
                        "Verificando hardware do computador..."
                    )

                    resultado = await self.executar_funcao_local(
                        obter_informacoes_hardware,
                        timeout=15,
                    )

                # Marca a sessão para encerrar após a despedida.
                elif nome == "encerrar_chamada":
                    self.status_recebido.emit(
                        "Encerrando chamada por comando de voz..."
                    )

                    resultado = (
                        "Solicitação de encerramento recebida. "
                        "Diga de forma curta que a chamada será encerrada."
                    )

                    encerrar_depois = True

                # Trata chamadas desconhecidas com segurança.
                else:
                    resultado = (
                        "Função desconhecida. Nenhuma ação foi executada."
                    )

                # Adiciona o resultado da função à lista de respostas.
                function_responses.append(
                    types.FunctionResponse(
                        id=chamada.id,
                        name=nome,
                        response={
                            "result": resultado
                        },
                    )
                )

            # Envia os resultados de volta ao Gemini.
            if function_responses:
                async with self.lock_envio:
                    await sessao.send_tool_response(
                        function_responses=(
                            function_responses
                        )
                    )

                # Somente depois de responder à ferramenta enviamos a imagem.
                if self.imagem_visual_pendente is not None:
                    await self.enviar_imagem_visual_pendente(sessao)

            # Agenda o encerramento após o modelo responder.
            if encerrar_depois:
                if self.tarefa_encerramento:
                    self.tarefa_encerramento.cancel()

                self.tarefa_encerramento = asyncio.create_task(
                    self.encerrar_apos_resposta()
                )

        finally:
            self.processando_ferramenta = False
            self.softia_falando = False
            self.limpar_fila_microfone(fila_microfone)

    # Aguarda a fala final do SOFTIA antes de encerrar a interface.
    async def encerrar_apos_resposta(self):
        """
        Aguarda a resposta de despedida do SOFTIA
        e só depois solicita o encerramento à interface.
        """

        try:
            # Pequena espera para permitir a reprodução da despedida.
            await asyncio.sleep(
                2.8
            )

            # Só solicita encerramento se a sessão ainda estiver ativa.
            if self.ativo:
                self.solicitou_encerramento.emit()

        except asyncio.CancelledError:
            pass

    # Controla o uso das funções de tela e câmera.
    async def processar_funcao_visual(
        self,
        nome,
    ):
        if self.executando_funcao_visual:
            return (
                "Uma análise visual já está em andamento. "
                "Aguarde a imagem atual."
            )

        agora = time.monotonic()
        repetido = (
            nome == self.ultima_funcao_visual
            and agora - self.tempo_ultima_funcao_visual
            < COOLDOWN_FUNCAO_VISUAL
        )
        if repetido:
            return (
                "Chamada visual duplicada ignorada. "
                "Use a última imagem recebida."
            )

        self.executando_funcao_visual = True
        self.ultima_funcao_visual = nome
        self.tempo_ultima_funcao_visual = agora

        try:
            if nome == "analisar_tela":
                self.status_recebido.emit("Capturando tela...")
                imagem = await asyncio.wait_for(
                    asyncio.to_thread(capturar_tela_bytes),
                    timeout=12,
                )
                self.imagem_visual_pendente = ("tela", imagem)
                return "A tela foi capturada e será enviada agora para análise."

            if nome == "analisar_camera":
                self.status_recebido.emit("Capturando imagem da câmera...")
                imagem = await asyncio.wait_for(
                    asyncio.to_thread(capturar_camera_bytes),
                    timeout=15,
                )
                self.imagem_visual_pendente = ("camera", imagem)
                return "A câmera foi capturada e será enviada agora para análise."

            return "Função visual desconhecida."

        except asyncio.TimeoutError:
            return "A captura visual demorou demais e foi cancelada com segurança."
        except Exception as erro:
            return f"Não foi possível capturar a imagem: {erro}"
        finally:
            self.executando_funcao_visual = False

    async def enviar_imagem_visual_pendente(self, sessao):
        pendente = self.imagem_visual_pendente
        self.imagem_visual_pendente = None
        if pendente is None:
            return

        tipo, imagem_bytes = pendente
        origem = "tela" if tipo == "tela" else "câmera"
        instrucao = (
            f"Analise exatamente esta imagem da {origem}. "
            "Use somente esta imagem como base. Não chame outra função visual. "
            "Se não estiver clara, diga isso. Responda de forma objetiva."
        )

        async with self.lock_envio:
            await sessao.send_client_content(
                turns=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                inline_data=types.Blob(
                                    data=imagem_bytes,
                                    mime_type="image/jpeg",
                                )
                            ),
                            types.Part(text=instrucao),
                        ],
                    )
                ],
                turn_complete=True,
            )

        self.status_recebido.emit(
            f"Imagem da {origem} enviada para análise."
        )

    async def executar_funcao_local(
        self,
        funcao,
        *args,
        timeout=15,
    ):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(funcao, *args),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return (
                "A operação demorou mais que o esperado e foi "
                "interrompida com segurança."
            )
        except Exception as erro:
            return f"A operação não pôde ser concluída: {erro}"

    # Reproduz os blocos de áudio gerados pelo Gemini.
    async def reproduzir_audio(
        self,
        fila_saida,
        fila_microfone,
    ):
        # Abre o dispositivo de saída em PCM bruto.
        with sd.RawOutputStream(
            samplerate=TAXA_SAIDA,
            blocksize=BLOCO,
            dtype="int16",
            channels=CANAIS,
        ) as saida:
            # Continua lendo e enviando áudio enquanto a sessão estiver ativa.
            while self.ativo:
                # Aguarda o próximo bloco de áudio.
                audio_bytes = await fila_saida.get()

                # Mantém o microfone bloqueado durante toda a reprodução
                # e descarta qualquer bloco antigo que ainda tenha sobrado.
                self.softia_falando = True
                self.limpar_fila_microfone(
                    fila_microfone
                )

                # Calcula o volume para animação da interface.
                nivel = self.calcular_nivel_audio(
                    audio_bytes
                )

                self.nivel_audio.emit(
                    nivel
                )

                # Reproduz em uma thread auxiliar.
                # Isso evita que drivers de áudio mais lentos bloqueiem
                # o loop que recebe os próximos blocos do Gemini.
                await asyncio.to_thread(
                    saida.write,
                    audio_bytes,
                )

                # Cancela a tarefa anterior para evitar
                # liberação prematura do microfone.
                if self.tarefa_liberar_microfone:
                    self.tarefa_liberar_microfone.cancel()

                self.tarefa_liberar_microfone = asyncio.create_task(
                    self.liberar_microfone_apos_fala()
                )

    @staticmethod
    def limpar_fila_microfone(
        fila_microfone,
    ):
        """
        Descarta todos os blocos de áudio que ainda aguardavam envio.
        Isso impede que um trecho capturado antes da resposta seja
        enviado ao Gemini enquanto o SOFTIA já está falando.
        """

        while True:
            try:
                fila_microfone.get_nowait()

            except asyncio.QueueEmpty:
                break

    # O método seguinte não depende do objeto self.
    @staticmethod
    # Amplifica o áudio capturado pelo microfone, protegendo
    # contra distorção quando a amostra já está próxima do limite.
    def aplicar_ganho_microfone(
        audio_bytes,
    ):
        if not audio_bytes:
            return audio_bytes

        try:
            amostras = array(
                "h",
                audio_bytes,
            )

            for indice, amostra in enumerate(amostras):
                amplificada = amostra * GANHO_MICROFONE

                # Limita o resultado à faixa válida de int16,
                # evitando distorção (clipping) no áudio enviado.
                amostras[indice] = int(
                    max(
                        -32768,
                        min(
                            32767,
                            amplificada,
                        ),
                    )
                )

            return amostras.tobytes()

        except (ValueError, OverflowError):
            return audio_bytes

    # O método seguinte não depende do objeto self.
    @staticmethod
    # Converte o áudio em um nível visual entre 0 e 1.
    def calcular_nivel_audio(
        audio_bytes,
    ):
        # Retorna zero quando não há áudio.
        if not audio_bytes:
            return 0.0

        try:
            # Interpreta os bytes como números inteiros de 16 bits.
            amostras = array(
                "h",
                audio_bytes,
            )

            if not amostras:
                return 0.0

            # Encontra a maior amplitude do bloco.
            pico = max(
                abs(amostra)
                for amostra in amostras
            )

            # Normaliza a amplitude máxima de int16.
            nivel = pico / 32768.0
            # Ajusta a curva para melhorar a sensibilidade visual.
            nivel = nivel ** 0.55

            return max(
                0.0,
                min(
                    1.0,
                    nivel,
                ),
            )

        except (
            ValueError,
            OverflowError,
        ):
            return 0.0

    # Reativa o microfone após uma pequena pausa.
    async def liberar_microfone_apos_fala(
        self,
    ):
        try:
            # Pequena espera para permitir a reprodução da despedida.
            await asyncio.sleep(
                ATRASO_REABRIR_MICROFONE
            )

            # Permite novamente a captura do usuário.
            self.softia_falando = False
            self.nivel_audio.emit(
                0.0
            )

        except asyncio.CancelledError:
            pass

    # Método chamado pelo botão de análise de tela.
    def solicitar_analise_tela(
        self,
    ):
        # Verifica se a sessão está pronta antes de enviar imagem.
        if not self.loop or not self.sessao:
            self.erro_recebido.emit(
                "Sessão Gemini ainda não está pronta."
            )
            return

        # Agenda a corrotina no loop da thread Gemini.
        asyncio.run_coroutine_threadsafe(
            self.enviar_tela_para_gemini(
                origem="botao"
            ),
            self.loop,
        )

    # Captura e envia a tela atual para análise.
    async def enviar_tela_para_gemini(
        self,
        origem="botao",
    ):
        if self.processando_ferramenta:
            self.erro_recebido.emit(
                "Aguarde a conclusão da ação atual antes da análise visual."
            )
            return

        self.processando_ferramenta = True
        self.softia_falando = True
        try:
            self.status_recebido.emit("Capturando imagem da tela...")
            imagem_bytes = await asyncio.wait_for(
                asyncio.to_thread(capturar_tela_bytes),
                timeout=12,
            )
            async with self.lock_envio:
                await self.sessao.send_client_content(
                    turns=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part(
                                    inline_data=types.Blob(
                                        data=imagem_bytes,
                                        mime_type="image/jpeg",
                                    )
                                ),
                                types.Part(
                                    text=(
                                        "Analise exatamente esta imagem enviada neste turno. "
                            "Use somente esta imagem como base. Não chame nenhuma "
                            "função visual. Se não estiver clara, diga isso. "
                            "Explique de forma objetiva o que está vendo."
                                    )
                                ),
                            ],
                        )
                    ],
                    turn_complete=True,
                )
            self.status_recebido.emit("Imagem da tela enviada para análise.")
        except asyncio.TimeoutError:
            self.erro_recebido.emit("A captura da tela excedeu o tempo limite.")
        except Exception as erro:
            self.erro_recebido.emit(f"Erro ao analisar tela: {erro}")
        finally:
            self.processando_ferramenta = False
            self.softia_falando = False

    def solicitar_analise_camera(
        self,
    ):
        # Verifica se a sessão está pronta antes de enviar imagem.
        if not self.loop or not self.sessao:
            self.erro_recebido.emit(
                "Sessão Gemini ainda não está pronta."
            )
            return

        # Agenda a corrotina no loop da thread Gemini.
        asyncio.run_coroutine_threadsafe(
            self.enviar_camera_para_gemini(
                origem="botao"
            ),
            self.loop,
        )

    # Captura e envia uma imagem da câmera.
    async def enviar_camera_para_gemini(
        self,
        origem="botao",
    ):
        if self.processando_ferramenta:
            self.erro_recebido.emit(
                "Aguarde a conclusão da ação atual antes da análise visual."
            )
            return

        self.processando_ferramenta = True
        self.softia_falando = True
        try:
            self.status_recebido.emit("Capturando imagem da câmera...")
            imagem_bytes = await asyncio.wait_for(
                asyncio.to_thread(capturar_camera_bytes),
                timeout=15,
            )
            async with self.lock_envio:
                await self.sessao.send_client_content(
                    turns=[
                        types.Content(
                            role="user",
                            parts=[
                                types.Part(
                                    inline_data=types.Blob(
                                        data=imagem_bytes,
                                        mime_type="image/jpeg",
                                    )
                                ),
                                types.Part(
                                    text=(
                                        "Analise exatamente esta imagem enviada neste turno. "
                            "Use somente esta imagem como base. Não chame nenhuma "
                            "função visual. Se não estiver clara, diga isso. "
                            "Explique de forma objetiva o que está vendo."
                                    )
                                ),
                            ],
                        )
                    ],
                    turn_complete=True,
                )
            self.status_recebido.emit("Imagem da câmera enviada para análise.")
        except asyncio.TimeoutError:
            self.erro_recebido.emit("A captura da câmera excedeu o tempo limite.")
        except Exception as erro:
            self.erro_recebido.emit(f"Erro ao analisar câmera: {erro}")
        finally:
            self.processando_ferramenta = False
            self.softia_falando = False

    def parar(self):
        # Faz os loops principais terminarem.
        self.ativo = False

        self.nivel_audio.emit(
            0.0
        )