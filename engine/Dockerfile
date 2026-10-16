# SonoPlan STG-01: SPPS without GUI (ENG-001, ENG-002, DEV-002)
# Base and deps aligned with upstream I-Simpa CI (ubuntu-22.04 / sub_buildLinux.yml).
# Pin: see engine/PINNED.json — do not use floating "latest" for reproducibility.

ARG UBUNTU_TAG=22.04
FROM ubuntu:${UBUNTU_TAG}

ARG ISIMPA_COMMIT=929a5c8e5f590b189f29155faeff8670f3699479
ARG BUILD_TYPE=Release
ENV DEBIAN_FRONTEND=noninteractive \
    CPM_SOURCE_CACHE=/opt/cpm-cache \
    ISIMPA_COMMIT=${ISIMPA_COMMIT} \
    BUILD_TYPE=${BUILD_TYPE}

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    git \
    python3 \
    python3-dev \
    swig \
    libboost-all-dev \
    byacc \
    gettext \
    libpng-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# GUI packages intentionally omitted: SKIPISIMPA=ON (wxWidgets/GTK not required for SPPS).
# If configure fails needing OpenGL headers for non-GUI targets, add mesa packages and document why.

WORKDIR /src
RUN git clone --filter=blob:none https://github.com/Universite-Gustave-Eiffel/I-Simpa.git isimpa \
    && cd isimpa \
    && git checkout "${ISIMPA_COMMIT}" \
    && test "$(git rev-parse HEAD)" = "${ISIMPA_COMMIT}"

WORKDIR /src/isimpa
# SonoPlan patches (deposit-on-start-tetra; same as build-spps-native.sh)
COPY patches/ /src/sonoplan-patches/
COPY scripts/apply-spps-patches.py /src/apply-spps-patches.py
RUN mkdir -p /src/sonoplan-engine/patches /src/sonoplan-engine/scripts \
    && cp -a /src/sonoplan-patches/. /src/sonoplan-engine/patches/ \
    && cp /src/apply-spps-patches.py /src/sonoplan-engine/scripts/ \
    && python3 /src/sonoplan-engine/scripts/apply-spps-patches.py /src/isimpa

WORKDIR /src/isimpa/build
RUN cmake .. \
      -DCPM_SOURCE_CACHE=${CPM_SOURCE_CACHE} \
      -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
      -DSKIPISIMPA=ON \
    && cmake --build . --parallel "$(nproc)" \
    && cmake --install .

# Locate spps binary after install (path may vary by upstream install layout)
RUN SPPS_BIN="$(find /src/isimpa -type f -name spps -perm -111 | head -n 1)" \
    && test -n "$SPPS_BIN" \
    && mkdir -p /opt/sonoplan/bin \
    && cp -a "$SPPS_BIN" /opt/sonoplan/bin/spps \
    && echo "SPPS_BIN=$SPPS_BIN" > /opt/sonoplan/bin/ORIGIN.txt \
    && /opt/sonoplan/bin/spps 2>&1 | head -n 5 || true

ENV PATH="/opt/sonoplan/bin:${PATH}"
WORKDIR /work
ENTRYPOINT ["/opt/sonoplan/bin/spps"]
