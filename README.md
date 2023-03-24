# ZMQ Interface for DeepDRR

https://github.com/arcadelab/deepdrr

## Installation
- `mamba env create -f ./environment.yml`
- `conda init powershell`
- `conda activate deepdrr_zmq`

## Notes
- Windows ssh key auth: https://superuser.com/questions/1510227/authorized-keys-win-10-ssh-issue

## TODO
<!-- - Auto tool loader -->
<!-- - Allow recreate projector -->
<!-- - Cache volumes -->
<!-- - Manager -->
- Docker container
- Heartbeat watchdog
- Proxy
- Faster decode
- Auto cache cleanup
- Faster mesh voxelization


## Questions
- Does deepdrr support volume instancing?

docker run --runtime=nvidia --gpus all -p 40101:40101 -p 40102:40102 --read-only --rm deepdrrzmq