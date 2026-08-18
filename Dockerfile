FROM ubuntu:22.04

RUN apt update && apt install -y \
    python3.10 python3.10-dev python3.10-venv \
    python3-pip \
    git build-essential \
    openjdk-17-jdk \
    unzip \
    autoconf automake libtool \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev \
    zlib1g-dev libgstreamer1.0-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python3.10 -m pip install --upgrade pip setuptools wheel
RUN python3.10 -m pip install buildozer cython
RUN python3.10 -m pip install appdirs colorama jinja2 sh meson ninja build toml packaging

WORKDIR /home/user/hostcwd
CMD ["buildozer", "android", "debug"]
