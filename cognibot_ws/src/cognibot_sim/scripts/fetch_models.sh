#!/usr/bin/env bash
# Pinned model fetch script for MuJoCo Menagerie models (SO-101 and Panda).
# Pin: Menagerie commit 8161bba264d7fa7c99ca301e91e7fb44737676ad
set -euo pipefail

MENAGERIE_REPO="https://github.com/google-deepmind/mujoco_menagerie.git"
MENAGERIE_COMMIT="8161bba264d7fa7c99ca301e91e7fb44737676ad"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

SO101_DEST="${SIM_DIR}/robots/so101/mjcf"
PANDA_DEST="${SIM_DIR}/robots/panda/mjcf"

# Check if already fetched and pristine
if [ -f "${SO101_DEST}/scene.xml" ] && [ -f "${PANDA_DEST}/scene.xml" ] && [ -f "${SO101_DEST}/MODIFICATIONS.md" ]; then
    echo "Menagerie models already present in ${SO101_DEST} and ${PANDA_DEST}."
fi

TMP_DIR="$(mktemp -d /tmp/menagerie_fetch_XXXXXX)"
cleanup() {
    rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "Fetching MuJoCo Menagerie models at commit ${MENAGERIE_COMMIT}..."
cd "${TMP_DIR}"
git clone --filter=blob:none --no-checkout "${MENAGERIE_REPO}" .
git checkout "${MENAGERIE_COMMIT}" -- robotstudio_so101 franka_emika_panda LICENSE

ACTUAL_COMMIT="$(git rev-parse HEAD)"
if [ "${ACTUAL_COMMIT}" != "${MENAGERIE_COMMIT}" ]; then
    echo "ERROR: Expected commit ${MENAGERIE_COMMIT}, got ${ACTUAL_COMMIT}" >&2
    exit 1
fi

echo "Setting up SO-101 MJCF in ${SO101_DEST}..."
mkdir -p "${SO101_DEST}"
cp -r robotstudio_so101/* "${SO101_DEST}/"

if [ ! -f "${SO101_DEST}/MODIFICATIONS.md" ]; then
    cat << 'EOF' > "${SO101_DEST}/MODIFICATIONS.md"
# MuJoCo Menagerie SO-101 Model Modifications

- **Upstream source:** [google-deepmind/mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie)
- **Subdirectory:** `robotstudio_so101`
- **Pinned commit:** `8161bba264d7fa7c99ca301e91e7fb44737676ad`
- **License:** Apache-2.0 (see `LICENSE`)

## Modifications
- None (pristine upstream from Menagerie).
EOF
fi

echo "Setting up Franka Panda MJCF in ${PANDA_DEST}..."
mkdir -p "${PANDA_DEST}"
cp -r franka_emika_panda/* "${PANDA_DEST}/"

if [ ! -f "${PANDA_DEST}/MODIFICATIONS.md" ]; then
    cat << 'EOF' > "${PANDA_DEST}/MODIFICATIONS.md"
# MuJoCo Menagerie Franka Emika Panda Model Modifications

- **Upstream source:** [google-deepmind/mujoco_menagerie](https://github.com/google-deepmind/mujoco_menagerie)
- **Subdirectory:** `franka_emika_panda`
- **Pinned commit:** `8161bba264d7fa7c99ca301e91e7fb44737676ad`
- **License:** Apache-2.0 (see `LICENSE`)

## Modifications
- None (pristine upstream from Menagerie).
EOF
fi

echo "Successfully fetched and verified SO-101 and Panda models at ${MENAGERIE_COMMIT}."
