#!/bin/bash

echo "🔧 Testing Vector Ingestion Fix"
echo "================================"
echo ""

# Check if server is running
if ! lsof -i :8000 > /dev/null 2>&1; then
    echo "❌ FastAPI server not running on port 8000"
    echo "   Run: make run (in another terminal)"
    exit 1
fi

echo "✅ FastAPI server is running"
echo ""

# Check current vector count
echo "📊 Current vector count:"
curl -s http://localhost:6333/collections/bas_docs 2>/dev/null | jq '{points: .result.points_count}' || echo "Collection doesn't exist yet"
echo ""

# Run ingestion
echo "📥 Running ingestion..."
response=$(curl -s -X POST http://localhost:8000/ingest)
echo "$response" | jq . || echo "$response"
echo ""

# Wait a moment for indexing to complete
echo "⏳ Waiting 3 seconds for indexing..."
sleep 3
echo ""

# Check new vector count
echo "📊 New vector count:"
curl -s http://localhost:6333/collections/bas_docs | jq '{points: .result.points_count, vectors: .result.indexed_vectors_count}'
echo ""

# Test retrieval
echo "🔍 Testing retrieval..."
curl -s -X POST http://localhost:8000/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"q":"What is Ciper 30?","k":2}' | jq '{count: .count, first_score: .results[0].score}'
echo ""

echo "✅ Test complete!"
