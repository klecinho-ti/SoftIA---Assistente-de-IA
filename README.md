# SOFTIA — Assistente de IA para Desktop

SOFTIA é uma assistente de inteligência artificial com voz, para Windows, que conversa em tempo real, analisa a tela e a câmera, controla o mouse, abre programas, organiza arquivos, mantém agenda e memórias — tudo diretamente no computador do usuário, usando a API **Gemini Live** do Google.

## Funcionalidades

- **Conversa por voz em tempo real**, com áudio de entrada e saída via Gemini Live
- **Autenticação por palavra-chave** antes de liberar comandos e conversas
- **Visão computacional**: análise da tela e da webcam sob comando
- **Clique visual guiado por IA**: localiza um elemento na tela pela descrição e clica nele
- **Controle do mouse**: rolagem, cliques e movimento até coordenadas
- **Gestão de arquivos** na Área de Trabalho: criar pastas, listar, organizar por tipo, copiar/recortar/colar/renomear — nunca sobrescreve ou exclui nada
- **Abertura de aplicativos** e recursos do Windows (Explorador, Configurações, Painel de Controle, etc.)
- **Pesquisa no navegador** e reprodução de vídeos/músicas no YouTube
- **Pesquisa de informações atuais** (cotações, clima, notícias) de forma invisível, com filtro local que evita pesquisas desnecessárias
- **Escrita automática** no campo de texto ativo do Windows
- **Agenda local persistente** e **memórias persistentes** entre sessões
- **Consulta de hardware** real da máquina (CPU, RAM, disco, GPU)
- **Reconexão automática** sem perder o contexto da conversa (session resumption)

## Tecnologias

- Python 3
- [PySide6](https://doc.qt.io/qtforpython/) — interface gráfica (Qt)
- [google-genai](https://pypi.org/project/google-genai/) — SDK oficial da API Gemini Live
- [sounddevice](https://pypi.org/project/sounddevice/) — captura e reprodução de áudio
- [mss](https://pypi.org/project/mss/) + [Pillow](https://pypi.org/project/pillow/) — captura de tela
- [opencv-python](https://pypi.org/project/opencv-python/) — captura de webcam
- [psutil](https://pypi.org/project/psutil/) — informações de hardware
- [ddgs](https://pypi.org/project/ddgs/) — pesquisa invisível de informações atuais
- Bibliotecas nativas do Windows (`ctypes` / `user32.dll` / `kernel32.dll`) para mouse, teclado e área de transferência

## Requisitos

- **Windows 10 ou 11 (64 bits)** — o projeto usa recursos internos do Windows (mouse, teclado, área de transferência, abertura de aplicativos) e **não funciona em macOS ou Linux**
- Microfone (obrigatório para uso por voz)
- Webcam (opcional, apenas para a função de analisar a câmera)
- Conexão com a internet
- Uma chave de API gratuita do [Google Gemini](https://aistudio.google.com/apikey)

## Instalação (usuário final)

Para quem só quer usar o programa, sem mexer em código: veja o instalador pronto e o manual de instalação na pasta [`Setup/`](Setup/) deste repositório (`Setup/Instalador/SoftIA_Setup.exe` após a build, e `Setup/Manual de Instalação/`).

Na primeira execução, o SOFTIA pede a chave de API do Gemini e salva localmente em `%APPDATA%\SoftIA\`, sem precisar de nenhuma configuração manual de ambiente.

## Executando em modo desenvolvimento

```powershell
# Criar e ativar o ambiente virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instalar as dependências
pip install PySide6 google-genai sounddevice mss pillow opencv-python psutil python-dotenv ddgs

# Configurar a chave de API
# Crie um arquivo .env na raiz do projeto com o conteúdo:
# GEMINI_API_KEY=sua_chave_aqui

# Executar
python main.py
```

## Estrutura do projeto

```
SoftIA/
├── main.py                 # Ponto de entrada da aplicação
├── core/                   # Configuração e gerenciamento da chave de API
├── gemini/                 # Cliente da sessão Gemini Live (voz, ferramentas, reconexão)
├── ui/                     # Interface gráfica (janela principal e visualizador animado)
├── actions/                # Ações locais: arquivos, apps, navegador, mouse, texto, agenda, hardware
├── vision/                 # Captura de tela/câmera e localização visual de elementos
├── memory/                 # Memória persistente entre sessões
└── Setup/                  # Script do instalador (Inno Setup), ícones e manual de instalação
```

## Segurança

- Nunca exclui ou sobrescreve arquivos do usuário
- Confirmações e bloqueios antes de ações sensíveis (cliques em elementos de exclusão, compra, instalação, etc.)
- Cada instalação usa a própria chave de API do usuário — nunca compartilhada entre máquinas
- Autenticação por palavra-chave antes de executar qualquer comando

## Autor

Desenvolvido por **Klecio Mauricio**.
