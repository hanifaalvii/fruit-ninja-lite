#!/bin/sh
# Builds the web version and copies it to docs/ (served by GitHub Pages).
set -e
cd "$(dirname "$0")"
python3 -m pygbag --build .
rm -rf docs
mkdir docs
cp -R build/web/* docs/
touch docs/.nojekyll
echo "Done. Now: git add -A && git commit -m 'Update game' && git push"
