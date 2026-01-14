#!/bin/bash
# Automated data loading script for Tolkien Knowledge Graph

echo "========================================"
echo "Tolkien Knowledge Graph - Data Loader"
echo "========================================"

# Check if Fuseki is running
if ! curl -s http://localhost:3030/ > /dev/null; then
    echo "ERROR: Fuseki is not running on http://localhost:3030"
    echo "Start Fuseki first: ./start_fuseki.sh"
    exit 1
fi

# Run the Python loader
python3 load_data_to_fuseki.py

if [ $? -eq 0 ]; then
    echo ""
    echo "SUCCESS: Data loaded successfully!"
    echo ""
    echo "Access endpoints:"
    echo "  Web Interface: http://localhost:3030"
    echo "  Linked Data:   http://localhost:5000"
    echo "  SPARQL:        http://localhost:3030/tolkienKG/sparql"
    echo "  Final KG file: data/output/final_knowledge_graph.ttl"
else
    echo ""
    echo "ERROR: Data loading failed"
    exit 1
fi
