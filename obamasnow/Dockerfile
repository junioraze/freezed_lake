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