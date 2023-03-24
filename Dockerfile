# syntax=docker/dockerfile:1
   
FROM pytorch/pytorch:1.13.1-cuda11.6-cudnn8-runtime as base
WORKDIR /app

RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y

# # copy environment.yml
# COPY environment.yml .

# # install dependencies in existing environment
# RUN conda env update -f environment.yml

RUN conda install -c conda-forge pycuda -y
# RUN conda install -c conda-forge libsm-cos6-x86_64
# RUN conda install -c conda-forge xorg-libx11
# RUN conda install -c anaconda mesa-libgl-cos6-x86_64

# RUN conda install -c conda-forge libglvnd-opengl-cos7-aarch64


COPY requirements.txt .
RUN pip install -r requirements.txt

# new layer
FROM base as builder

COPY . .

CMD ["python", "-m", "deepdrrzmq.manager"]

EXPOSE 40100
EXPOSE 40101
EXPOSE 40102