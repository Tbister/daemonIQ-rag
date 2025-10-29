# Performance Guide

## Problem: Slow LLM Responses (25+ minutes)

Your Mac with `llama3.1:8b` takes **25+ minutes** per query. This is unusable for demos.

## Solutions (from fastest to best quality)

### 🚀 Option 1: Ultra-Fast Model (1-3 seconds)

```bash
# Pull and switch to qwen2.5:0.5b
ollama pull qwen2.5:0.5b

# Update .env
sed -i '' 's/OLLAMA_MODEL=.*/OLLAMA_MODEL=qwen2.5:0.5b/' .env

# Restart server
# (Ctrl+C the current server, then:)
make run

# Test (should respond in 1-3 seconds!)
make ask Q="What is Ciper 30?"
```

### ⚡ Option 2: Balanced Speed (5-10 seconds)

```bash
# Pull phi3:mini - good balance of speed and quality
ollama pull phi3:mini

# Update .env
sed -i '' 's/OLLAMA_MODEL=.*/OLLAMA_MODEL=phi3:mini/' .env

# Restart and test
make run
make ask Q="What is Ciper 30?"
```

### 📊 Option 3: Retrieval Only (Instant)

Don't need LLM generation? Just get the relevant chunks:

```bash
# Returns matching document chunks in < 1 second
make retrieve Q="What is Ciper 30?"
```

### 🌊 Option 4: Streaming (Better UX)

See results as they generate (even if slow):

```bash
# Streams response word-by-word
make stream Q="What is Ciper 30?"
```

## New Makefile Commands

```bash
make retrieve Q="your question"  # Fast retrieval only
make stream Q="your question"    # Streaming response
make ask Q="your question"       # Full RAG (original)
```

## Model Comparison

| Model | Size | Speed | Quality | Recommended For |
|-------|------|-------|---------|-----------------|
| **qwen2.5:0.5b** | 0.5B | 1-3s | ⭐⭐⭐ | Demos, testing, development |
| **phi3:mini** | 3.8B | 5-10s | ⭐⭐⭐⭐ | Production demos |
| **gemma2:2b** | 2B | 5-15s | ⭐⭐⭐⭐ | Balanced production |
| **llama3.1:8b** | 8B | 25min+ | ⭐⭐⭐⭐⭐ | Not usable on Mac |

## What Changed in the Code

1. **Reduced context**: Queries now use max 2 chunks (was 4)
2. **Shorter prompts**: Simplified QA template for faster generation
3. **Streaming endpoint**: `/chat-stream` for real-time feedback
4. **Retrieval endpoint**: `/retrieve` for instant results without LLM
5. **Better logging**: See exactly what's slow

## Quick Test After Switching Models

```bash
# 1. Switch to fast model
ollama pull qwen2.5:0.5b
sed -i '' 's/OLLAMA_MODEL=.*/OLLAMA_MODEL=qwen2.5:0.5b/' .env

# 2. Restart (Ctrl+C then:)
make run

# 3. Test all endpoints
curl http://localhost:8000/health
make retrieve Q="What is Ciper 30?"  # Should be instant
make ask Q="What is Ciper 30?"       # Should be 1-3 seconds
```

## Still Slow?

If even small models are slow:

1. **Check CPU**: `top` - is ollama using 100%+ CPU?
2. **Check RAM**: Models need 2-8GB free RAM
3. **Try metal acceleration**: Ollama should use Metal on Mac automatically
4. **Reduce k value**: Use `k=1` for single chunk retrieval

```bash
# Minimal context for fastest response
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"q":"What is Ciper 30?","k":1}'
```
