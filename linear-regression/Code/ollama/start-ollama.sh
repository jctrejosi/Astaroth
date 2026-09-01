#!/bin/sh
# iniciar servidor en background
ollama serve &
# esperar a que el servidor esté listo
sleep 10
# descargar modelo
ollama pull qwen2.5:3b
# mantener el servidor en foreground
wait
