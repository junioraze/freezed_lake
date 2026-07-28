# Freezed Lakehouse

Projeto para provisionamento de um **lakehouse local** utilizando **MinIO** (armazenamento S3-compatível) e **Apache Polaris** (catálogo Iceberg REST), orquestrado por **Terraform**. Os dados são ingeridos por workers Python que extraem replays do Pokémon Showdown e os armazenam no formato Iceberg.

Na versão 0.1.0, o projeto foi reestruturado utilizando um padrão de SDK interno (`obamasnow`) para garantir contratos de dados estritos durante a ingestão. As execuções foram padronizadas através de uma imagem Docker universal ("Runner") gerenciada pelo `uv`, preparando o terreno para a orquestração via DAGU.

> **Aviso de Segurança e Escopo (Projeto de Estudo)**
> Licença GNU em licenses/ ; a licença do MinIO vc precisa inserir apos se cadastrar para receber uma.
> Este projeto foi desenvolvido com fins estritamente didáticos e focado no aprendizado da engenharia de dados (arquitetura Lakehouse, Iceberg e orquestração). Por isso, ele possui **arquiteturas e falhas de segurança** que não devem ser replicadas em ambientes de produção:
> * **Bypass de Segurança do S3:** Estamos contornando o modelo padrão e seguro de nuvem (como o AWS STS - *Security Token Service*), conectando ao storage através de chaves de acesso estáticas e permissões amplas, em vez de assumir *roles* temporárias (Credential Vending). Nesse projeto o STS não será implementado, a não ser que me obriguem. 
> * **Gestão de Credenciais:** Senhas e tokens de API trafegam de forma explícita nas requisições e estão mapeadas em texto plano no ambiente (`.env`), sem a utilização de um cofre de segredos (Secret Manager). Esse ponto será implementado.
---

## Visão Geral

* **Infraestrutura** (Terraform): containers Docker do MinIO e Polaris, rede dedicada, volumes persistentes e criação automática de bucket e catálogo.


* **Base SDK (`obamasnow`)**: Biblioteca central que abstrai autenticação, logs padronizados e a conversão segura de dados para o formato PyArrow exigido pelo Iceberg.


* **Workers Python (Scripts de Domínio)**:
* `create/raw_layer.py`: cria *namespace* (`raw`) e *tabela* (`replay_logs`) no catálogo.


* `insert/into_raw_replay_logs.py`: extrai replays via scraper (Selenium *headless*), estrutura os dados com Polars e insere no Lakehouse utilizando a classe `LakehouseWorker`.




* **Makefile**: Atalhos automatizados para provisionar a infraestrutura e rodar a imagem efêmera dos workers diretamente na rede do banco (`lakehouse_net`).



---

## Pré‑requisitos

* **Docker** (essencial para executar a infraestrutura e a imagem do *Runner*).


* **Terraform** (>= 1.0).

* **Licença MinIO FREE incluida em licenses/

* **make** (para automatização dos comandos). (OPT)



---

## Configuração

### 1. Clone o repositório

```bash
git clone <url>
cd freezed-lakehouse

```

### 2. Defina as variáveis de ambiente do Terraform

Crie o arquivo `infra/terraform.tfvars` com as credenciais desejadas:
`algumas variáveis de infra ainda estão hardcoded no main.tf será futuramente revisado`
```hcl
minio_user     = "admin"
minio_pass     = "minio123"
minio_external_endpoint = "http://minio:9000"
polaris_user   = "polaris_admin"
polaris_pass   = "polaris123"
polaris_relm   = "default"
catalog_bucket = "my_catalog"

```

### 3. Configure o ambiente dos Workers

Crie um arquivo `.env` no caminho apontado pelo Makefile (`obamasnow/src/obamasnow/.env`) com as seguintes variáveis:

```bash
# Conexão com o lakehouse
POLARIS_ENDPOINT=http://polaris:8181
POLARIS_REALM=default
POLARIS_USER=polaris_admin
POLARIS_PASS=polaris123
MINIO_ENDPOINT=http://minio:9000
MINIO_USER=admin
MINIO_PASS=minio123
CATALOG_BUCKET=my_catalog

```

---

## Execução

### 1. Subir a infraestrutura (Terraform)

Execute os comandos para inicializar e aplicar os containers de armazenamento e catálogo:

```bash
make tf-init          # Inicializa o Terraform
make tf-apply         # Aplica o plano (cria containers, rede e volumes)

```

### 2. Construir a imagem base dos Workers (Runner)

A arquitetura utiliza uma única imagem Docker (Python 3.13-slim com Chromium instalado) que resolve dependências dinamicamente via `uv` no momento da execução. Para construí-la, rode:

```bash
make or-build-runner

```

### 3. Criar a Tabela Iceberg (DDL)

Acione o container efêmero na rede `lakehouse_net` para executar o script de criação da camada raw:

```bash
make or-run-create-raw

```

### 4. Ingerir Dados (Scraper e DML)

Execute o worker de extração. O *entrypoint* do container injetará as dependências extras (`scraper`, `transformer`) dinamicamente antes de iniciar o Selenium e enviar os dados para o MinIO:

```bash
make or-run-insert-logs

```

---

## Estrutura do Projeto

```text
.
├── infra/                         # Configuração Terraform
│   ├── main.tf
│   ├── providers.tf
│   ├── variables.tf
│   └── terraform.tfvars
├── obamasnow/                     # Base SDK do projeto
│   ├── Dockerfile                 # Imagem Runner com dependências do Chromium
│   ├── entrypoint_obamasnow.sh    # Script Bash de injeção dinâmica do UV
│   ├── pyproject.toml             # Configuração do pacote obamasnow
│   └── src/
│       └── obamasnow/
│           ├── .env               # Variáveis de ambiente
│           ├── telemetry.py       # Configuração de Logs
│           └── worker.py          # Classe LakehouseWorker e contratos de dados
├── workers/                       # Scripts de domínio isolados
│   ├── create/
│   │   └── raw_layer.py           # Criação de namespace e tabelas
│   └── insert/
│       └── into_raw_replay_logs.py # Lógica de Scraping (Selenium) e transformação (Polars)
├── Makefile                       # Atalhos de execução (Terraform e Docker Run)
└── README.md

```

---

## Melhorias Futuras

* **Orquestração com DAGU**: Integrar os comandos de `docker run` configurados no Makefile diretamente nos arquivos YAML do DAGU para agendamento e monitoramento de falhas.
* **Derivação**: Aplicar o processamento (Polars) em novos scripts na pasta `workers/derive/` para criar as camadas *Silver/Gold*.
* **Observabilidade**: Evoluir o `telemetry.py` conectando o logger padrão com provedores do OpenTelemetry.
* **Governança**: Refinar os controles de acesso e permissões (RBAC) simulados pelo Polaris para fins de estudo.