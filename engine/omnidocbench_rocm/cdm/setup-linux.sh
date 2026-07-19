#!/usr/bin/env bash
# Idempotent host CDM toolchain for Linux/ROCm: texlive-full + ImageMagick 7 +
# ghostscript + node. The CDM metric compiles formulas (LaTeX) -> PDF ->
# rasterize (IM7) -> color-match. IM6 silently flattens color formulas to
# grayscale (#grayscale); this script enforces IM7. See docs/pitfalls.md.
set -euo pipefail

need=()
dpkg -s texlive-full      >/dev/null 2>&1 || need+=(texlive-full)
command -v gs             >/dev/null 2>&1 || need+=(ghostscript)
command -v node           >/dev/null 2>&1 || need+=(nodejs)
if [ ${#need[@]} -gt 0 ]; then
  echo "[cdm] apt install: ${need[*]}"
  sudo apt-get update -qq && sudo apt-get install -y -qq "${need[@]}"
else
  echo "[cdm] texlive/ghostscript/node: already present"
fi

# ImageMagick 7 (NOT the IM6 default on Ubuntu 22.04 — IM6 flattens color).
# NOTE: `magick` may exist as an IM6 legacy wrapper, so check the VERSION, not
# just the binary's presence.
if ! magick -version 2>/dev/null | grep -q 'ImageMagick 7'; then
  echo "[cdm] installing ImageMagick 7"
  sudo apt-get install -y -qq build-essential pkg-config libjpeg-dev libpng-dev libtiff-dev zlib1g-dev
  IM=7.1.2-8
  # imagemagick.org archive paths 404; the GitHub tag archive is the working source.
  curl -fsSL "https://github.com/ImageMagick/ImageMagick/archive/refs/tags/${IM}.tar.gz" -o /tmp/im7.tar.gz
  tar -xzf /tmp/im7.tar.gz -C /tmp && cd /tmp/ImageMagick-${IM}
  ./configure --disable-docs && make -j"$(nproc)" && sudo make install && sudo ldconfig
  cd - >/dev/null
else
  echo "[cdm] magick (IM7): already present ($(magick -version | head -1))"
fi

# CJK fonts for texlive. OmniDocBench CDM uses the Arphic `gkai` font with the
# CJK LaTeX package (\begin{CJK}{UTF8}{gkai}); it does NOT use Noto. The Arphic
# Type1 TFM (gkai00mp.tfm) is the #gkaiu-map requirement.
sudo apt-get install -y -qq fonts-arphic-ukai fonts-arphic-uming texlive-lang-chinese 2>/dev/null || true
if ! kpsewhich gkai00mp.tfm >/dev/null 2>&1; then
  echo "[cdm] WARNING: gkai00mp.tfm not found — CJK formulas will render BLANK (#gkaiu-map)." >&2
  echo "[cdm]   The CJK.sty .fd shims load but produce no glyphs without the Arphic Type1 TFM." >&2
  echo "[cdm]   CDM scoring needs a TeX install that ships it (e.g. a fuller texlive-full host," >&2
  echo "[cdm]   or the repro Docker image). Edit_dist + TEDS work WITHOUT it." >&2
fi

# Enable PDF write in IM7 policy.xml (default denies PDF).
POLICY="$(magick -configure | awk '/CONFIGURE PATH/{print $2; exit}')policy.xml" 2>/dev/null || true
if [ -n "${POLICY:-}" ] && [ -f "${POLICY}" ] && grep -q 'PDF" write="none"' "${POLICY}"; then
  sudo sed -i 's|PDF" write="none"|PDF" write="allowed"|g' "${POLICY}"
  echo "[cdm] enabled PDF write in ${POLICY}"
fi

echo "[cdm] setup complete"
