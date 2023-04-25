# ZMQ Interface for DeepDRR

[![Docker](https://github.com/PelvisVR/deepdrr_zmq/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/PelvisVR/deepdrr_zmq/actions/workflows/docker-publish.yml)

ZMQ/Capnp interface for [DeepDRR](https://github.com/arcadelab/deepdrr).

## Windows Setup
- Install wsl2
- Increase wsl2 available memory

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
- [x] Docker container
- [x] Heartbeat watchdog
- [x] Faster mesh voxelization
- [x] Proxy
- [x] Patient loader 
- [ ] Auto cache cleanup
- [ ] NIFTI cache invalidation
- [ ] Power save mode and auto shutdown after idle
- [ ] Faster decode
- [ ] Better cache invalidation with modification time


## Questions
- Does deepdrr support volume instancing?
- Does deepdrr support enabling/disabling volumes without recreating the projector?
- Code used for creating smooth capped meshes?