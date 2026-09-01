# Cómo colocar a funcionar el backend

## Instalar python

[Download Python | Python.org](https://www.python.org/downloads/)

## Crear la carpeta para el entorno virtual

```
python -m venv venv
```

## Activar el entorno virtual

```
venv\Scripts\activate
```

- Al inicio de la terminal verás **(venv)**, que inidica que estás dentro del entorno virtual.

## Instalar las depenendicas del proyecto

```
python -m pip install -r requirements.txt
```

## Descargar el modelo de IA que vaya a usar (Puede ser de huggingface)

[bartowski/Qwen2.5-72B-Instruct-GGUF at main](https://huggingface.co/bartowski/Qwen2.5-72B-Instruct-GGUF/tree/main)

## Configurar las variables de entorno para cargar el modelo (/.env)

```
MODEL_PATH=C:\Users\jk\UN\statistics-2\Code\models\qwen2.5-3b-instruct-q4_k_m.gguf
OLLAMA_URL=http://localhost:1143
GROQ_API_KEY='your_api_key'
LLM_EXTERNAL=false
```

## Correr el proyecto

```
python main.py
```
