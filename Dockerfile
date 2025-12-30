FROM nvidia/cuda:13.1.0-runtime-ubuntu22.04

RUN \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y \
    git \
    curl \
    build-essential

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    /root/.cargo/bin/rustup default stable
ENV PATH="/root/.cargo/bin:${PATH}"

COPY --from=ghcr.io/astral-sh/uv:0.9.20 /uv /uvx /bin/
RUN \
    --mount=type=bind,source=uv.lock,target=uv.lock,readonly \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml,readonly \
    uv sync --python 3.11

WORKDIR /opt

COPY engine_manifest.json /opt/engine_manifest.json
COPY run.py /opt/run.py
COPY resources /opt/resources
COPY voicevox_engine /opt/voicevox_engine
COPY .serena /opt/.serena
COPY tools /opt/tools

CMD ["uv", "run", "python", "run.py", "--use_gpu", "--host", "0.0.0.0"]
