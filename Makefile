# Makefile - Surf

# Variáveis com os caminhos relativos (sempre a partir da raiz)
TERRAFORM_DIR = infra
WORKER_DITTO_DIR = workers/ditto
WORKER_SCRAFTY_DIR = workers/scrafty

# Comandos 
PYTHON = python.exe
TERRAFORM = terraform

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
# TARGETS PARA PYTHON (workers)
# --------------------------------------------------------------

.PHONY: run-ditto run-scrafty

# Roda o formation.py do ditto
run-ditto:
	cd $(WORKER_DITTO_DIR) && $(PYTHON) formation.py

run-scrafty:
	cd $(WORKER_SCRAFTY_DIR) && $(PYTHON) koff.py

# --------------------------------------------------------------
# TARGET GENÉRICO PARA RODAR QUALQUER SCRIPT PYTHON
# --------------------------------------------------------------

.PHONY: run

run:
	@if [ -z "$(SCRIPT)" ]; then \
		echo "Uso: make run SCRIPT=workers/ditto/formation.py"; \
		exit 1; \
	fi
	@dir=$$(dirname $(SCRIPT)); \
	file=$$(basename $(SCRIPT)); \
	cd $$dir && $(PYTHON) $$file