#!/bin/bash
# entrypoint-ollama.sh
# Starts the Ollama server, waits for it to be ready,
# then pulls the required models before handing off.

set -e

echo "🚀 Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Wait until the API is accepting connections
echo "⏳ Waiting for Ollama to be ready..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 1
done

echo "✅ Ollama is ready. Pulling models..."

# Pull the LLM model
echo "📥 Pulling llama3.2:1b..."
ollama pull llama3.2:1b

# Pull the embedding model
echo "📥 Pulling nomic-embed-text:latest..."
ollama pull nomic-embed-text:latest

echo "🎉 All models are ready!"

# Keep the server process in the foreground
wait $OLLAMA_PID
