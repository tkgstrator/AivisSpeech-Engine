# FROM nvidia/cuda:12.1.0-cudnn9-runtime-ubuntu22.04
# FROM nvidia/cuda:12.1.0-base-ubuntu22.04
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Install base packages (rarely changes - good cache layer)
RUN \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y \
    git-filter-repo \
    pkg-config \
    sudo \
    btop \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavdevice-dev

# Create vscode user with UID/GID 1000 (similar to MCR devcontainer images)
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -G sudo $USERNAME \
    && echo '%sudo ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/nopasswd

USER $USERNAME
