# Makefile - Surf

# Variáveis Terraform
TERRAFORM_DIR = infra
TERRAFORM = terraform

# Variáveis Obamasnow-runner
IMAGE_NAME = obamasnow-runner:latest
NETWORK_NAME = lakehouse_net
ENV_FILE = obamasnow/src/obamasnow/.env


# --------------------------------------------------------------
# TARGETS PARA TERRAFORM
# --------------------------------------------------------------

.PHONY: tf-init tf-plan tf-apply tf-destroy tf-output

tf-init:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) init -upgrade

tf-plan:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) plan

tf-apply:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) apply -auto-approve

tf-apply-debug:
	cd $(TERRAFORM_DIR) && TF_LOG=DEBUG $(TERRAFORM) apply -auto-approve

tf-destroy:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) destroy -auto-approve

tf-output:
	cd $(TERRAFORM_DIR) && $(TERRAFORM) output

# --------------------------------------------------------------
# TARGETS PARA Obamasnow-runner
# --------------------------------------------------------------
.PHONY: or-build-runner or-run-create-raw or-run-insert-logs

or-build-runner:
	@echo "Construindo a imagem Docker $(IMAGE_NAME)..."
	docker build -t $(IMAGE_NAME) obamasnow/.

or-run-create-raw:
	@echo "Executando raw_layer.py na rede $(NETWORK_NAME)..."
	docker run --rm \
		--network $(NETWORK_NAME) \
		--env-file $(ENV_FILE) \
		$(IMAGE_NAME) \
		python workers/create/raw_layer.py


or-run-insert-logs:
	@echo "Executando into_raw_replay_logs.py na rede $(NETWORK_NAME)..."
	docker run --rm \
		--network $(NETWORK_NAME) \
		--env-file $(ENV_FILE) \
		-e UV_EXTRAS="scraper,transformer" \
		$(IMAGE_NAME) \
		python workers/insert/into_raw_replay_logs.py