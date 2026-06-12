FROM quay.io/pypa/manylinux2014_x86_64

# manylinux2014 is based on CentOS 7 with glibc 2.17 — the oldest glibc
# target PyPA still maintains. The binary runs on RHEL/CentOS 7+,
# Ubuntu 14.04+, Debian 8+, SLES 12+, and anything newer.
#
# CentOS 7 ships OpenSSL 1.0.2 which is too old for Python 3.12, so we
# build OpenSSL 3.0 LTS from source first, then CPython against it.
ENV PYTHON_VERSION=3.12.10
ENV OPENSSL_VERSION=3.0.16

RUN yum install -y bzip2-devel libffi-devel xz-devel sqlite-devel \
    readline-devel zlib-devel ncurses-devel perl-core && \
    yum clean all

# --- OpenSSL 3.0 LTS (shared, rpath'd) -------------------------------------
# --libdir=lib: CPython's configure probes $prefix/lib, not lib64
RUN curl -fsSL "https://github.com/openssl/openssl/releases/download/openssl-${OPENSSL_VERSION}/openssl-${OPENSSL_VERSION}.tar.gz" | tar xz && \
    cd openssl-${OPENSSL_VERSION} && \
    ./config shared --prefix=/usr/local/ssl --libdir=lib --openssldir=/etc/ssl \
        -Wl,-rpath,/usr/local/ssl/lib && \
    make -j"$(nproc)" >/dev/null && \
    make install_sw >/dev/null && \
    cd / && rm -rf openssl-${OPENSSL_VERSION}

# --- CPython (shared, against our OpenSSL) ----------------------------------
RUN curl -fsSL "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz" | tar xz && \
    cd Python-${PYTHON_VERSION} && \
    ./configure --enable-shared --prefix=/usr/local \
        --with-openssl=/usr/local/ssl --with-openssl-rpath=auto \
        LDFLAGS="-Wl,-rpath,/usr/local/lib -Wl,-rpath,/usr/local/ssl/lib" && \
    make -j"$(nproc)" >/dev/null && \
    make install >/dev/null && \
    cd / && rm -rf Python-${PYTHON_VERSION}

ENV PATH="/usr/local/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/local/lib:/usr/local/ssl/lib:${LD_LIBRARY_PATH}"

# Sanity check: ssl module must import (catches OpenSSL linking mistakes early)
RUN python3 -c "import ssl; print('OpenSSL:', ssl.OPENSSL_VERSION)"

# Strip RPATH/RUNPATH from our custom-built libraries. PyInstaller's
# bootloader provides the library search path at runtime, and staticx
# refuses inputs whose bundled libraries carry absolute RPATHs.
# (LD_LIBRARY_PATH set above keeps python3 working inside this image.)
# patchelf is pinned: 0.17.x has an assertion bug (shiftFile) that breaks
# patching PyInstaller bootloaders.
RUN pip3 install 'patchelf==0.13.1.0' && \
    patchelf --remove-rpath /usr/local/lib/libpython3.12.so.1.0 && \
    patchelf --remove-rpath /usr/local/ssl/lib/libssl.so.3 && \
    patchelf --remove-rpath /usr/local/ssl/lib/libcrypto.so.3 && \
    for f in /usr/local/lib/python3.12/lib-dynload/*.so; do \
        patchelf --remove-rpath "$f"; \
    done && \
    python3 -c "import ssl; print('ssl OK after rpath strip')"

WORKDIR /build

# Install dependencies
COPY requirements.txt .
RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt pyinstaller

# Copy source
COPY . .

# Install the package
RUN pip3 install -e .

# Stamp build info (shown by --version)
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown
RUN printf 'BUILD_INFO = {\n    "commit": "%s",\n    "built": "%s",\n    "glibc_target": "2.17 (manylinux2014)",\n}\n' \
    "$GIT_SHA" "$BUILD_DATE" > src/dxc_doctor/_build_info.py

# Build binary using spec file (handles dynamic hidden imports)
RUN pyinstaller dxc-doctor.spec

# Best-effort fully static variant: staticx bundles glibc itself so the
# binary runs on ANY Linux (even musl/Alpine), regardless of glibc version.
RUN pip3 install staticx && \
    staticx dist/dxc-doctor dist/dxc-doctor-static && \
    echo "staticx OK" || echo "WARNING: staticx step failed — only the glibc-2.17 binary was produced"

RUN ls -lh dist/

CMD ["sh", "-c", "cp dist/dxc-doctor /output/dxc-doctor && cp dist/dxc-doctor-static /output/dxc-doctor-static 2>/dev/null; true"]
