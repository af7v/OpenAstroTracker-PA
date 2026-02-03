#!/bin/bash
# Build script for OAT Web PA Debian package
# Run this script from WSL Ubuntu

set -e

PACKAGE_NAME="oat-web-pa"
VERSION="1.0.0"
ARCH="all"

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="/tmp/oat-web-pa-build"
PACKAGE_DIR="${BUILD_DIR}/${PACKAGE_NAME}_${VERSION}-1_${ARCH}"

echo "Building ${PACKAGE_NAME} version ${VERSION}..."

# Clean up any previous build
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Create package directory structure
mkdir -p "${PACKAGE_DIR}/DEBIAN"
mkdir -p "${PACKAGE_DIR}/opt/oat-web-pa/static"
mkdir -p "${PACKAGE_DIR}/opt/oat-web-pa/templates"
mkdir -p "${PACKAGE_DIR}/etc/systemd/system"

# Copy application files
echo "Copying application files..."
cp "${SCRIPT_DIR}/app.py" "${PACKAGE_DIR}/opt/oat-web-pa/"
cp "${SCRIPT_DIR}/config.py" "${PACKAGE_DIR}/opt/oat-web-pa/"
cp "${SCRIPT_DIR}/mount_client.py" "${PACKAGE_DIR}/opt/oat-web-pa/"
cp "${SCRIPT_DIR}/camera_client.py" "${PACKAGE_DIR}/opt/oat-web-pa/"
cp "${SCRIPT_DIR}/plate_solver.py" "${PACKAGE_DIR}/opt/oat-web-pa/"
cp "${SCRIPT_DIR}/pa_calculator.py" "${PACKAGE_DIR}/opt/oat-web-pa/"
cp "${SCRIPT_DIR}/requirements.txt" "${PACKAGE_DIR}/opt/oat-web-pa/"

cp "${SCRIPT_DIR}/static/style.css" "${PACKAGE_DIR}/opt/oat-web-pa/static/"
cp "${SCRIPT_DIR}/static/app.js" "${PACKAGE_DIR}/opt/oat-web-pa/static/"
cp "${SCRIPT_DIR}/templates/index.html" "${PACKAGE_DIR}/opt/oat-web-pa/templates/"

cp "${SCRIPT_DIR}/oat-web-pa.service" "${PACKAGE_DIR}/etc/systemd/system/"

# Create DEBIAN control file
echo "Creating control file..."
cat > "${PACKAGE_DIR}/DEBIAN/control" << EOF
Package: ${PACKAGE_NAME}
Version: ${VERSION}-1
Section: science
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.8), python3-pip, python3-venv
Recommends: python3-opencv, python3-pil, python3-numpy, astap
Suggests: astrometry.net, python3-indi
Maintainer: TAS Hellequin <theaffablesatanist@proton.me>
Description: Web-based polar alignment for OpenAstroTracker
 A lightweight web interface for performing polar alignment on
 OpenAstroTracker mounts. Control your mount, capture images,
 plate solve, and achieve precise polar alignment from your
 phone or tablet.
 .
 Features include auto-align mode, manual RA/DEC and AZ/ALT
 jog controls, ASTAP and astrometry.net solver support.
EOF

# Copy maintainer scripts
echo "Copying maintainer scripts..."
cp "${SCRIPT_DIR}/debian/postinst" "${PACKAGE_DIR}/DEBIAN/"
cp "${SCRIPT_DIR}/debian/prerm" "${PACKAGE_DIR}/DEBIAN/"
cp "${SCRIPT_DIR}/debian/postrm" "${PACKAGE_DIR}/DEBIAN/"

# Set permissions
chmod 755 "${PACKAGE_DIR}/DEBIAN/postinst"
chmod 755 "${PACKAGE_DIR}/DEBIAN/prerm"
chmod 755 "${PACKAGE_DIR}/DEBIAN/postrm"
chmod 644 "${PACKAGE_DIR}/opt/oat-web-pa/"*.py
chmod 644 "${PACKAGE_DIR}/opt/oat-web-pa/requirements.txt"
chmod 644 "${PACKAGE_DIR}/opt/oat-web-pa/static/"*
chmod 644 "${PACKAGE_DIR}/opt/oat-web-pa/templates/"*
chmod 644 "${PACKAGE_DIR}/etc/systemd/system/oat-web-pa.service"

# Build the package
echo "Building .deb package..."
dpkg-deb --build "${PACKAGE_DIR}"

# Move to script directory
mv "${PACKAGE_DIR}.deb" "${SCRIPT_DIR}/"

echo ""
echo "============================================"
echo "Build complete!"
echo "Package: ${SCRIPT_DIR}/${PACKAGE_NAME}_${VERSION}-1_${ARCH}.deb"
echo ""
echo "To install on Raspberry Pi:"
echo "  sudo dpkg -i ${PACKAGE_NAME}_${VERSION}-1_${ARCH}.deb"
echo "  sudo apt-get install -f  # Install dependencies"
echo "============================================"
