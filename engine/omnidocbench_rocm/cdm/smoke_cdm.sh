#!/usr/bin/env bash
# CDM smoke probe: compile one color-coded formula (LaTeX->PDF), rasterize (IM7),
# and confirm a non-grayscale PNG is produced. Catches #posix / #grayscale /
# #cdm-zero before a full run. Exits 0 = toolchain CDM-capable, 1 = not.
set -euo pipefail
D="$(mktemp -d)"; trap 'rm -rf "$D"' EXIT
cat > "$D/f.tex" <<'TEX'
\documentclass[preview]{standalone}
\usepackage{xcolor}
\begin{document}
{\color{red}$E=mc^2$}
\end{document}
TEX
cd "$D"
pdflatex -interaction=nonstopmode f.tex >/dev/null 2>&1 || { echo "[cdm-smoke] pdflatex failed (#posix?)"; exit 1; }
magick -density 150 f.pdf f.png 2>/dev/null || { echo "[cdm-smoke] magick rasterize failed"; exit 1; }
# Assert the PNG is not grayscale (red channel present):
python3 -c "import sys; from PIL import Image; im=Image.open('$D/f.png').convert('RGB'); r,g,b=im.getpixel((5,5)); sys.exit(0 if r!=g or r!=b else 1)" \
  || { echo "[cdm-smoke] raster is grayscale (#grayscale — IM6/IM7 policy?)"; exit 1; }
echo "[cdm-smoke] OK: toolchain is CDM-capable"
