# ZMQ Interface for DeepDRR

[![Docker](https://github.com/PelvisVR/deepdrr_zmq/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/PelvisVR/deepdrr_zmq/actions/workflows/docker-publish.yml)

ZMQ/Capnp interface for [DeepDRR](https://github.com/arcadelab/deepdrr).



## Installation
- `mamba env create -f ./environment.yml`
- `mamba activate deepdrr_zmq`

## Usage
- `python -m deepdrrzmq.manager`

## Docker Install
- If on windows, don't use docker desktop 4.17.1 https://github.com/docker/for-win/issues/13324

## TODO 
- [x] Auto tool loader
- [x] Allow recreate projector
- [x] Cache volumes
- [x] Manager
- [ ] Docker container
- [ ] Heartbeat watchdog
- [ ] Proxy
- [ ] Faster decode
- [ ] Auto cache cleanup
- [ ] Faster mesh voxelization

## Questions
- Does deepdrr support volume instancing?