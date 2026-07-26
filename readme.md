# Freezed Lakehouse

Projeto para provisionamento de um **lakehouse local** utilizando **MinIO** (armazenamento S3-compatível) e **Apache Polaris** (catálogo Iceberg REST), orquestrado por **Terraform**. Os dados são ingeridos por workers Python que extraem replays do Pokémon Showdown e os armazenam no formato Iceberg.

> ⚠️ Projeto em desenvolvimento – estrutura dos workers será reorganizada e orquestrada com DAG em breve.

---

## Visão Geral

- **Infraestrutura** (Terraform): containers Docker do MinIO e Polaris, rede dedicada, volumes persistentes e criação automática de bucket e catálogo.
- **Workers Python**:
  - `ditto/formation.py`: cria *namespace* e *tabela* no catálogo.
  - `scrafty/koff.py`: extrai replays do site Pokémon Showdown com Selenium, estrutura os dados e insere na tabela Iceberg via PyIceberg.
- **Makefile**: atalhos para executar Terraform e os workers.

---

## Pré‑requisitos

- **Docker** (com compose opcional, mas usamos containers avulsos)
- **Terraform** (>= 1.0)
- **Python** 3.10+
- **make** (opcional, mas recomendado)
- **Google Chrome** / **Chromium** e **ChromeDriver** (para o Selenium)

---

## Configuração

### 1. Clone o repositório

```bash
git clone <url>
cd freezed-lakehouse
```

### 2. Defina as variáveis de ambiente do Terraform

Crie o arquivo `infra/terraform.tfvars` com as credenciais desejadas:

```hcl
minio_user     = "admin"
minio_pass     = "minio123"
polaris_user   = "polaris_admin"
polaris_pass   = "polaris123"
polaris_relm   = "default"
catalog_bucket = "my_catalog"
```

| Variável | Descrição |
|----------|-----------|
| `minio_user` / `minio_pass` | Credenciais root do MinIO |
| `polaris_user` / `polaris_pass` | Credenciais admin do Polaris |
| `polaris_relm` | Realm (tenant) do Polaris |
| `catalog_bucket` | Nome do bucket no MinIO e do catálogo no Polaris |

### 3. Configure o ambiente Python

Crie um arquivo `.env` na raiz do projeto (ou em cada worker) com as seguintes variáveis:

```bash
# Conexão com o lakehouse
POLARIS_ENDPOINT=http://localhost:8181
POLARIS_REALM=default
POLARIS_USER=polaris_admin
POLARIS_PASS=polaris123
MINIO_ENDPOINT=http://localhost:9000
MINIO_USER=admin
MINIO_PASS=minio123
CATALOG_BUCKET=my_catalog

# Para o worker scrafty (koff.py)
GEN=gen4ou               # Geração alvo
RANGE=30                 # Limite de replays por execução
LAKEHOUSE_TABLE=raw.replay_logs   # Tabela de destino
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

(O arquivo `requirements.txt` deve conter `pyiceberg`, `polars`, `selenium`, `python-dotenv`, etc.)

---

## Execução

### Subir a infraestrutura

```bash
make tf-init          # inicializa o Terraform
make tf-apply         # aplica o plano (cria containers, bucket e catálogo)
```

Ou manualmente:

```bash
cd infra
terraform init -upgrade
terraform apply -var-file=terraform.tfvars
```

Após a aplicação, os serviços estarão disponíveis em:

- **MinIO API**: `http://localhost:9000`
- **MinIO Console**: `http://localhost:9001`
- **Polaris API**: `http://localhost:8181`
- **Polaris Management**: `http://localhost:8182`

### Criar a tabela Iceberg

Execute o worker `ditto` para criar o namespace `raw` e a tabela `replay_logs`:

```bash
make run-ditto
```

Ou via Python:

```bash
python workers/ditto/formation.py
```

### Ingerir dados (scraper)

O worker `scrafty` acessa o site do Pokémon Showdown, extrai replays da geração definida (`GEN`) e insere na tabela:

```bash
make run-scrafty
```

Ou:

```bash
python workers/scrafty/koff.py
```

> 🔁 O script coleta até `RANGE` replays + excedentes na página, estrutura os dados (extrai metadados como geração, tier, timestamp) e adiciona à tabela Iceberg via `table.append()`.

---

## Estrutura do Projeto

```
.
├── infra/                     # Configuração Terraform
│   ├── main.tf
│   ├── providers.tf
│   ├── variables.tf
│   └── terraform.tfvars.example
├── workers/
│   ├── ditto/                 # Worker de formação
│   │   └── formation.py
│   └── scrafty/               # Worker de coleta
│       └── koff.py
├── lakehouse_worker.py        # Classe base (autenticação, catálogo)
├── requirements.txt
├── .env.example
├── Makefile
└── README.md
```

---

## Melhorias Futuras (em andamento)

- **Reorganização dos workers** – extrair lógica comum para um pacote compartilhado e padronizar interface.
- **Derivação** - Aplicar o polars como modulo de processamento. (depende do ponto acima)
- **Orquestração** – integrar com DAGU para agendamento e monitoramento (depende do ponto acima).
- **Observabilidade** – logs estruturados e métricas.
- **Governancia** - Complicar os acessos com algumas regras que me permitam estudar isso. 
---
