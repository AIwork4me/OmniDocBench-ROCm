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
if ! command -v magick >/dev/null 2>&1; then
  echo "[cdm] installing ImageMagick 7"
  sudo apt-get install -y -qq build-essential pkg-config libjpeg-dev libpng-dev libtiff-dev zlib1g-dev
  IM=7.1.1-38
  curl -fsSL "https://imagemagick.org/archive/releases/ImageMagick-${IM}.tar.xz" -o /tmp/im7.tar.xz
  tar -xf /tmp/im7.tar.xz -C /tmp && cd /tmp/ImageMagick-${IM}
  ./configure --disable-docs && make -j"$(nproc)" && sudo make install && sudo ldconfig
  cd - >/dev/null
else
  echo "[cdm] magick (IM7): already present"
fi

# CJK fonts for texlive (formulas can contain CJK).
sudo apt-get install -y -qq fonts-noto-cjk fonts-noto-cjk-extra 2>/dev/null || true

# Enable PDF write in IM7 policy.xml (default denies PDF).
POLICY="$(magick -configure | awk '/CONFIGURE PATH/{print $2; exit}')policy.xml" 2>/dev/null || true
if [ -n "${POLICY:-}" ] && [ -f "${POLICY}" ] && grep -q 'PDF" write="none"' "${POLICY}"; then
  sudo sed -i 's|PDF" write="none"|PDF" write="allowed"|g' "${POLICY}"
  echo "[cdm] enabled PDF write in ${POLICY}"
fi

echo "[cdm] setup complete"
