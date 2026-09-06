#!/bin/bash
# MEAI Evaluation Runner (Linux/macOS)
# Builds and runs the MEAI evaluation with Copilot SDK integration

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MEAI_DIR="$REPO_ROOT/evals/eval_dotnet"

REPETITIONS=1
OUTPUT="meai_results.json"
MODEL="gpt-4.1"
NO_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --repetitions)
            REPETITIONS="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --no-build)
            NO_BUILD=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "MEAI Evaluation Runner"
echo "Repository root: $REPO_ROOT"
echo ""

# Set environment variables
export COPILOT_MODEL="$MODEL"
export PYTHONPATH="$REPO_ROOT/src"

echo "Configuration:"
echo "  Model: $COPILOT_MODEL"
echo "  Python path: $PYTHONPATH"
echo "  Repetitions: $REPETITIONS"
echo "  Output: $OUTPUT"
echo ""

# Build unless --no-build is specified
if [ "$NO_BUILD" = false ]; then
    echo "Building MEAI project..."
    cd "$MEAI_DIR"
    dotnet build -c Release
    cd "$REPO_ROOT"
    echo "Build successful"
    echo ""
fi

# Run evaluation
echo "Running evaluation..."
cd "$REPO_ROOT"
dotnet run --project "$MEAI_DIR" --no-build -- \
    --repetitions "$REPETITIONS" \
    --output "$OUTPUT" \
    --provider copilot-sdk

echo ""
echo "Evaluation complete. Results saved to: $OUTPUT"

# Display summary if jq is available
if command -v jq &> /dev/null && [ -f "$OUTPUT" ]; then
    echo ""
    echo "Results Summary:"
    TOTAL=$(jq 'length' "$OUTPUT")
    PASSED=$(jq '[.[] | select(.passed == true)] | length' "$OUTPUT")
    FAILED=$(jq "[.[] | select(.passed == false)] | length" "$OUTPUT")
    TOTAL_TIME=$(jq '[.[].latency_ms] | add' "$OUTPUT")
    AVG_TIME=$(echo "scale=2; $TOTAL_TIME / $TOTAL" | bc)

    echo "  Total runs: $TOTAL"
    echo "  Passed: $PASSED"
    echo "  Failed: $FAILED"
    echo "  Total latency: ${TOTAL_TIME}ms"
    echo "  Average latency: ${AVG_TIME}ms"
fi
