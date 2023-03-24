# syntax=docker/dockerfile:1
   
FROM pytorch/pytorch:1.13.1-cuda11.6-cudnn8-runtime as base
WORKDIR /app

RUN apt-get update && apt-get install ffmpeg libsm6 libxext6 build-essential -y

# COPY environment.yml .

# RUN conda env update -f environment.yml

RUN conda install -c conda-forge pycuda -y

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "deepdrrzmq.manager"]

EXPOSE 40100/tcp
EXPOSE 40101/tcp
EXPOSE 40102/tcp