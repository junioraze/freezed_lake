# ==========================================
# BASE
# ==========================================
FROM python:3.13-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"
WORKDIR /app

# Copias 
COPY pyproject.toml .
COPY src/ ./src/
COPY workers/ ./workers/

# Instala apenas as dependências core (pyiceberg, pyarrow)
RUN uv pip install --system -e .


ENTRYPOINT ["python"]


# ==========================================
# VARIANT: TRANSFORMER 
# ==========================================
FROM base AS transformer

# Instala o pacote polars para transformações
RUN uv pip install --system -e ".[transformer]"


# ==========================================
# VARIANT: SCRAPER 
# ==========================================
FROM base AS scraper

# Adiciona o Chromium e o driver nativo apenas nesta camada superior
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Informa explicitamente ao Selenium onde os binários estão
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Instala as dependências de scraping e transformação
RUN uv pip install --system -e ".[scraper,transformer]"

# ==========================================
# VARIANT: LAB (JupyterLab)
# ==========================================
FROM base AS lab

# Instala dependências do JupyterLab
RUN uv pip install --system -e ".[lab,transformer]"

# Configura JupyterLab para usar o tema escuro por padrão
RUN mkdir -p /root/.jupyter/lab/user-settings/@jupyterlab/apputils-extension
RUN echo '{"theme": "JupyterLab Dark"}' > /root/.jupyter/lab/user-settings/@jupyterlab/apputils-extension/themes.jupyterlab-settings

# Expõe a porta padrão do JupyterLab
EXPOSE 8888

# Comando padrão: inicia o JupyterLab
ENTRYPOINT []
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]