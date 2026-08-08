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
RUN uv pip install --system -e ".[scraper]"

# ==========================================
# VARIANT: LAB (JupyterLab)
# ==========================================
FROM base AS lab

RUN apt-get update && apt-get install -y nodejs npm && apt-get clean

RUN uv pip install --system -e ".[lab]"

RUN jupyter labextension install jupyter-cytoscape \
    && jupyter lab build

RUN mkdir -p /root/.jupyter/lab/user-settings/@jupyterlab/apputils-extension
RUN echo '{"theme": "JupyterLab Dark"}' > /root/.jupyter/lab/user-settings/@jupyterlab/apputils-extension/themes.jupyterlab-settings

EXPOSE 8888

ENTRYPOINT []
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]

# ==========================================
# VARIANT: MARIMO
# ==========================================
FROM base AS marimo

RUN uv pip install --system -e ".[marimo]"

EXPOSE 2718

ENTRYPOINT []
CMD ["marimo", "edit", "--host", "0.0.0.0", "--port", "2718", "/app/notebooks"]