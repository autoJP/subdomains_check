#!/bin/sh
set -eu

sudo apt-get update
sudo apt-get install -y python3-publicsuffix2

echo "Dependencies installed. Run: python3 check_subdomains.py"
