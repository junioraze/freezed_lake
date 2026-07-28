#!/bin/bash
# entrypoint_obamasnow.sh
set -e

if [ -n "$UV_EXTRAS" ]; then
    echo "Instalando pacotes da base com extras: $UV_EXTRAS"
    uv pip install --system -e ".[$UV_EXTRAS]"
else
    echo "Instalando pacotes da base"
    uv pip install --system -e .
fi

# Transfere o PID 1 para o comando passado pelo orquestrador/terminal
exec "$@"