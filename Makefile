# Variáveis Terraform
TERRAFORM_DIR = infra
TERRAFORM = terraform

# Variáveis Obamasnow Multi-Variant
IMAGE_BASE = obamasnow-base:latest
IMAGE_SCRAPER = obamasnow-scraper:latest
IMAGE_LAB = obamasnow-lab:latest
IMAGE_MARIMO = obamasnow-marimo:latest
NETWORK_NAME = lakehouse_net
ENV_FILE = obamasnow/src/obamasnow/.env

# --------------------------------------------------------------
# TARGETS PARA TERRAFORM
# --------------------------------------------------------------

.PHONY: tf-format tf-init tf-plan tf-validate tf-apply tf-destroy tf-output tf-full-start tf-full-start-debug

tf-format:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) fmt

tf-init:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) init -upgrade

tf-plan:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) plan

tf-validate:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) validate

tf-apply:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) apply -auto-approve

tf-apply-debug:
	cd $(TERRAFORM_DIR) && TF_LOG=DEBUG $(TERRAFORM) apply -auto-approve

tf-destroy:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) destroy -auto-approve

tf-output:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) output
tf-full-start: tf-init tf-destroy tf-apply
tf-full-start-debug: tf-init tf-destroy tf-apply-debug

# --------------------------------------------------------------
# TARGETS PARA Obamasnow-runner (Multi-Variant)
# --------------------------------------------------------------
.PHONY: or-build-all or-build-base or-build-transformer or-build-marimo or-run-marimo or-build-scraper or-run-create-bronze or-run-insert-logs

# Builds Individuais
or-build-base:
	@echo "[$(IMAGE_BASE)] Construindo a imagem Docker..."
	docker build --target base -t $(IMAGE_BASE) obamasnow/.
	@echo "[$(IMAGE_BASE)] Limpando imagens antigas..."
	docker image prune -f

or-build-scraper:
	@echo "[$(IMAGE_SCRAPER)] Construindo a imagem Docker..."
	docker build --target scraper -t $(IMAGE_SCRAPER) obamasnow/.
	@echo "[$(IMAGE_SCRAPER)] Limpando imagens antigas..."
	docker image prune -f

or-build-lab:
	@echo "Construindo a imagem JupyterLab..."
	docker build --target lab -t $(IMAGE_LAB) obamasnow/.	
	@echo "[$(IMAGE_LAB)] Limpando imagens antigas..."
	docker image prune -f

or-build-marimo:
	@echo "Construindo a imagem Marimo..."
	docker build --target marimo -t $(IMAGE_MARIMO) obamasnow/.	
	@echo "[$(IMAGE_MARIMO)] Limpando imagens antigas..."
	docker image prune -f

# Build de todas as imagens em sequência
or-build-all: or-build-base or-build-scraper or-build-lab

# Execuções
or-run-create-bronze:
	@echo "Executando raw_layer.py na rede $(NETWORK_NAME) com a imagem Base..."
	docker run --rm \
		--network $(NETWORK_NAME) \
		--env-file $(ENV_FILE) \
		$(IMAGE_BASE) \
		workers/create/raw_layer.py

or-run-insert-logs:
	@echo "Executando into_raw_replay_logs.py na rede $(NETWORK_NAME) com a imagem Scraper..."
	docker run --rm \
		--network $(NETWORK_NAME) \
		--env-file $(ENV_FILE) \
		$(IMAGE_SCRAPER) \
		workers/insert/into_raw_replay_logs.py

or-run-lab:
	@echo "Iniciando JupyterLab em http://localhost:8888"
	docker run --rm \
		--network $(NETWORK_NAME) \
		--env-file $(ENV_FILE) \
		-p 8888:8888 \
		-v $(PWD)/notebooks:/app/notebooks \
		-e JUPYTER_TOKEN=123lab \
		$(IMAGE_LAB)

or-run-marimo:
	@echo "Iniciando Marimo em http://localhost:2718"
	docker run --rm \
		--network $(NETWORK_NAME) \
		--env-file $(ENV_FILE) \
		-p 2718:2718 \
		-v $(PWD)/notebooks:/app/notebooks \
		$(IMAGE_MARIMO)
#persiste arquivos em /notebooks