FROM python:3.13-slim

# Instala o Chromium, o driver nativo via apt-get, e o curl para puxar o UV
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Adiciona o UV ao PATH do sistema
ENV PATH="/root/.local/bin:$PATH"

# Informa explicitamente ao Selenium/OS onde os binários do Chromium estão localizados
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Define o diretório de trabalho padrão do container
WORKDIR /app

# Copia os metadados do pacote (pyproject.toml)
COPY pyproject.toml .

# Copia os códigos-fonte do SDK base e dos workers soltos
COPY src/ ./src/
COPY workers/ ./workers/

# Copia e garante permissão de execução do Entrypoint
COPY entrypoint_obamasnow.sh .
RUN chmod +x entrypoint_obamasnow.sh

# Define o script customizado como a porta de entrada imutável da imagem
ENTRYPOINT ["/app/entrypoint_obamasnow.sh"]