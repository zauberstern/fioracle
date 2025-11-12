#!/bin/bash

# Quick Start Script for Union Investments Regime Forecasting System
# This script sets up the environment and runs a basic analysis

echo "============================================================"
echo "  Union Investments Regime Forecasting System"
echo "  Quick Start Setup"
echo "============================================================"

# Check Python version
echo ""
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run basic analysis (without lambda tuning for speed)
echo ""
echo "============================================================"
echo "  Running Basic Analysis"
echo "  (Lambda tuning disabled for quick start)"
echo "============================================================"
echo ""

python main.py \
    --start-date 1990-01-01 \
    --initial-lambda 5.0 \
    --n-macro-regimes 3 \
    --test-size 0.2 \
    --output-dir output

# Generate report
echo ""
echo "============================================================"
echo "  Generating Report"
echo "============================================================"
echo ""

python generate_report.py --output-dir output --docs-dir docs

# Summary
echo ""
echo "============================================================"
echo "  QUICK START COMPLETE"
echo "============================================================"
echo ""
echo "Results saved to: output/"
echo "Figures saved to: output/figures/"
echo "Report saved to: docs/index.md"
echo ""
echo "To view results:"
echo "  1. Check output/performance_summary.csv"
echo "  2. Open figures in output/figures/"
echo "  3. View report: docs/index.md"
echo ""
echo "To run with lambda tuning:"
echo "  python main.py --tune-lambda --validation-years 3"
echo ""
echo "To deploy to GitHub Pages:"
echo "  git add docs/"
echo "  git commit -m 'Add results report'"
echo "  git push origin main"
echo "  Then enable GitHub Pages in repository settings"
echo ""
echo "============================================================"

