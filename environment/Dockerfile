# hash:sha256:779c75fb4c3cb96b01c7739c49879263fa311c71b4c7862bbd70ea8b92bd1cfe
FROM registry.codeocean.allenneuraldynamics.org/codeocean/jupyterlab:3.6.1-miniconda4.12.0-python3.9-ubuntu20.04

ARG DEBIAN_FRONTEND=noninteractive

ARG GIT_ASKPASS
ARG GIT_ACCESS_TOKEN
COPY git-askpass /

RUN pip install -U --no-cache-dir \
    aind-data-access-api==0.6.1 \
    boto3==1.28.72 \
    pynwb==2.5.0 \
    hdmf-zarr==0.5.0
