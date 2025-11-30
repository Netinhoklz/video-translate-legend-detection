Aqui está a tradução completa para o português, mantendo a formatação Markdown, os links das imagens e os diagramas técnicos adaptados:

🎥 Serverless Video AI - Plataforma Inteligente de Processamento de Vídeo

![alt text](https://img.shields.io/badge/AWS-Serverless-orange)


![alt text](https://img.shields.io/badge/Python-3.9+-blue)


![alt text](https://img.shields.io/badge/Docker-Container-blue)


![alt text](https://img.shields.io/badge/License-MIT-green)

Serverless Video AI é uma aplicação nativa da nuvem de ponta, projetada para automatizar a análise e o aprimoramento de vídeos. Aproveitando o poder da arquitetura AWS Serverless, esta plataforma ingere vídeos enviados pelo usuário, transcreve automaticamente o áudio, traduz para o inglês, detecta objetos dentro dos quadros do vídeo e sobrepõe essas informações como legendas dinâmicas e caixas delimitadoras (bounding boxes).

Este projeto demonstra uma implementação robusta de pipelines de Arquitetura Orientada a Eventos, Visão Computacional e Processamento de Linguagem Natural (NLP) usando serviços gerenciados de nuvem.

🚀 Principais Recursos

Transcrição Automática: Utiliza o Amazon Transcribe para converter áudio em português para texto com alta precisão.

Tradução de Máquina Neural: Utiliza o Amazon Translate para traduzir perfeitamente a transcrição de português para inglês.

Detecção Inteligente de Objetos: Utiliza o Amazon Rekognition para identificar objetos no vídeo que correspondem às palavras-chave do texto traduzido.

Sobreposição Dinâmica de Vídeo: Grava automaticamente legendas e desenha caixas delimitadoras ao redor dos objetos detectados usando OpenCV.

Fusão Inteligente de Áudio: Reintegra o áudio original ao vídeo processado usando FFmpeg para uma experiência de visualização completa.

Resultados para Download: Gera um pacote ZIP contendo o vídeo processado e um arquivo CSV com as transcrições originais e traduzidas.

Serverless e Escalável: Construído sobre AWS Lambda e Docker, garantindo que a aplicação escale automaticamente com a demanda e tenha custo zero quando ociosa.

Interface Moderna: Apresenta uma interface web limpa, inspirada em glassmorphism, construída com Flask e HTML5/CSS3.

🏗️ Visão Geral da Arquitetura

A aplicação segue um fluxo de trabalho totalmente serverless:

Ingestão: O usuário envia um vídeo via Interface Web. O arquivo é armazenado no Amazon S3.

Orquestração: O app Flask (rodando no AWS Lambda) aciona trabalhos de IA paralelos.

Processamento de IA:

Amazon Transcribe gera a transcrição de texto.

Amazon Translate converte o texto para inglês.

Amazon Rekognition varre o vídeo em busca de rótulos/objetos.

Processamento de Vídeo: A função Lambda baixa o vídeo, usa OpenCV para sobrepor texto e caixas delimitadoras, e FFmpeg para mesclar o áudio.

Entrega: O vídeo final e os metadados são compactados e enviados de volta ao S3. URLs pré-assinadas são geradas para download seguro pelo usuário.

📊 Diagrama de Fluxo de Trabalho
code
Mermaid
download
content_copy
expand_less
sequenceDiagram
    participant User as 👤 Usuário
    participant WebApp as 🌐 Interface Web
    participant S3 as 📦 Amazon S3
    participant Lambda as ⚡ AWS Lambda
    participant AI as 🤖 Serviços AWS AI (Transcribe/Translate/Rekognition)
    
    User->>WebApp: Envia Vídeo
    WebApp->>S3: Faz Upload do Arquivo de Vídeo
    WebApp->>Lambda: Aciona Processamento
    activate Lambda
    Lambda->>S3: Baixa Vídeo
    
    par Pipeline de Processamento de IA
        Lambda->>AI: Transcrever Áudio (PT-BR)
        Lambda->>AI: Traduzir Texto (PT -> EN)
        Lambda->>AI: Detectar Objetos (Rekognition)
    end
    
    Lambda->>Lambda: Sobrepor Legendas e Caixas (OpenCV)
    Lambda->>Lambda: Mesclar Áudio (FFmpeg)
    Lambda->>S3: Envia Vídeo Processado e ZIP
    Lambda-->>WebApp: Retorna URLs de Download
    deactivate Lambda
    
    WebApp-->>User: Exibe Resultado e Links de Download
🧩 Arquitetura do Sistema
code
Mermaid
download
content_copy
expand_less
flowchart TD
    user([👤 Usuário])
    
    subgraph Frontend [Frontend]
        ui[🌐 Interface Web]
    end
    
    subgraph AWS [☁️ Nuvem AWS]
        direction TB
        s3[📦 Amazon S3]
        lambda[⚡ AWS Lambda]
        
        subgraph AI [🤖 Serviços de IA]
            transcribe[🗣️ Transcribe]
            translate[A↔️文 Translate]
            rekognition[👁️ Rekognition]
        end
    end

    user -->|Envia Vídeo| ui
    ui -->|Upload Direto| s3
    ui -->|Aciona Processamento| lambda
    lambda <-->|Lê/Grava Vídeo| s3
    lambda -->|Job Assíncrono| transcribe
    lambda -->|Traduz Texto| translate
    lambda -->|Detecta Rótulos| rekognition
    
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:white;
    classDef ai fill:#232F3E,stroke:#FF9900,stroke-width:2px,color:white;
    class s3,lambda aws;
    class transcribe,translate,rekognition ai;
🛠️ Stack Tecnológico

Framework de Backend: Python Flask (implantado via AWS Chalice/Lambda)

Conteinerização: Docker (para empacotamento das dependências do Lambda)

Provedor de Nuvem: Amazon Web Services (AWS)

Computação: AWS Lambda

Armazenamento: Amazon S3

IA/ML: Transcribe, Translate, Rekognition

Registro: Amazon ECR

Processamento de Vídeo: OpenCV (cv2), MoviePy, FFmpeg

Frontend: HTML5, CSS3, JavaScript

CI/CD: GitHub Actions

📸 Capturas de Tela
<div align="center">
<img src="https://s2.senseidownload.com/Api/V1/Download/Get/5f8c11e0-1404-4daf-8f5a-523facbcaa5c/c11aa087-dc80-49be-8dfc-da9b61b35f0b/639001078881485036?preview=true" alt="Captura de Tela da Aplicação" width="800" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
</div>

📋 Pré-requisitos

Antes de começar, certifique-se de ter o seguinte instalado:

Git: Para controle de versão.

Docker Desktop: Necessário para construir a imagem do contêiner Lambda.

AWS CLI: Configurado com suas credenciais (aws configure).

Python 3.9+: Para desenvolvimento local.

PowerShell: Para executar o script de implantação manual (Windows).

⚙️ Instalação e Implantação
Opção A: Implantação Automatizada (GitHub Actions) - Recomendado

Este projeto está configurado com GitHub Actions para Integração Contínua (CD).

Faça o Fork/Clone deste repositório.

Vá para as Settings do seu repositório -> Secrets and variables -> Actions.

Adicione os seguintes segredos (secrets) do repositório:

AWS_ACCESS_KEY_ID: Sua Chave de Acesso AWS.

AWS_SECRET_ACCESS_KEY: Sua Chave Secreta AWS.

S3_BUCKET: O nome do seu bucket S3 (ex: meu-bucket-video-app).

Faça um push de qualquer alteração para a branch main. O fluxo de trabalho irá automaticamente construir a imagem Docker, enviá-la para o ECR e atualizar a função Lambda.

Opção B: Implantação Manual (PowerShell)

Se você preferir implantar a partir de sua máquina local:

Clone o repositório:

code
Bash
download
content_copy
expand_less
git clone https://github.com/Netinhoklz/video-translate-legend-detection.git
cd video-translate-legend-detection

Configure o Ambiente:
Crie um arquivo .env no diretório raiz:

code
Env
download
content_copy
expand_less
AWS_ACCESS_KEY_ID=sua_access_key
AWS_SECRET_ACCESS_KEY=sua_secret_key
AWS_REGION=us-east-1
S3_BUCKET=nome-do-seu-bucket-s3

Execute o Script de Implantação:

code
Powershell
download
content_copy
expand_less
.\deploy.ps1

Este script irá:

Autenticar na AWS.

Criar/Configurar o Bucket S3 (CORS).

Criar o Repositório ECR.

Construir e enviar a Imagem Docker.

Atualizar a Função AWS Lambda.

💻 Desenvolvimento Local

Para rodar a aplicação Flask localmente para testes e desenvolvimento da interface:

Instale as Dependências:

code
Bash
download
content_copy
expand_less
pip install -r requirements.txt

Defina as Variáveis de Ambiente:
Certifique-se de que seu arquivo .env esteja configurado como mostrado acima.

Execute a Aplicação:

code
Bash
download
content_copy
expand_less
python app.py

Acesse o App:
Abra seu navegador e vá para http://localhost:8080.

> Nota: A execução local ainda requer credenciais AWS válidas para acessar o S3 e os serviços de IA.

📂 Estrutura do Projeto
code
Text
download
content_copy
expand_less
.
├── .github/workflows/   # Configurações do Pipeline CI/CD
├── static/              # CSS e ativos estáticos
├── templates/           # Templates HTML (Jinja2)
├── app.py               # Aplicação Flask principal e Lógica
├── deploy.ps1           # Script de automação de implantação manual
├── Dockerfile.lambda    # Configuração Docker para AWS Lambda
├── requirements.txt     # Dependências Python
└── README.md            # Documentação do projeto
🛡️ Licença

Este projeto é open-source e está disponível sob a Licença MIT.

<p align="center">
Feito com ❤️ por Netinho
</p>
