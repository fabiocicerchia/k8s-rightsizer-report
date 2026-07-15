#!/usr/bin/env bash
set -euo pipefail
# One-line installer for k8s-rightsizer-report
# Usage: curl -fsSL https://raw.githubusercontent.com/fabiocicerchia/k8s-rightsizer-report/main/install.sh | bash

if command -v pipx &>/dev/null; then
  pipx install git+https://github.com/fabiocicerchia/k8s-rightsizer-report
else
  pip install --user git+https://github.com/fabiocicerchia/k8s-rightsizer-report
fi
echo "k8s-rightsizer-report installed. Run: k8s-rightsizer-report --help"
