import asyncio
import os

import logging
from pathlib import Path

import capnp
import typer
import zmq.asyncio
import time
from deepdrrzmq.utils.zmq_util import zmq_no_linger_context, zmq_poll_latest

from .utils.typer_util import unwrap_typer_param
from .utils.server_util import make_response, DeepDRRServerException, messages



# app = typer.Typer()
app = typer.Typer(pretty_exceptions_show_locals=False)

excluded_prefixes = [
    "/loggerd/",
    "/replayd/",
]


class LogReplayer:
    def __init__(self, logfolderpath):
        self.logfolderpath = logfolderpath
        self.next_file_idx = 0
        self._current_time = None
        self.current_entryiter = None
        self._loop = False
        self.next_buffered = None
        self._starttime = None
        self._endtime = None
        self._allfiles = None

    @property
    def allfiles(self):
        if self._allfiles is None:
            listfiles = list(Path(self.logfolderpath).glob("*.pvrlog"))
            self._allfiles = sorted(listfiles, key=lambda x: int(x.stem.split("--")[-1]))
        return self._allfiles

    @property
    def loop(self, state):
        return self._loop
    
    @loop.setter
    def loop(self, state):
        self._loop = state

    @property
    def starttime(self):
        if self._starttime is None:
            firstfile = self.allfiles[0]
            self._starttime = next(messages.LogEntry.read_multiple_bytes(firstfile.read_bytes()))
        return self._starttime

    @property
    def endtime(self):
        if self._endtime is None:
            self._endtime = 0
            lastfile = self.allfiles[-1]
            for logentry in messages.LogEntry.read_multiple_bytes(lastfile.read_bytes()):
                self._endtime = logentry.logMonoTime
        return self._endtime
    
    @property
    def current_time(self):
        if self._current_time is None:
            self._current_time = self.starttime
        return self._current_time
    
    @current_time.setter
    def current_time(self, time):
        self._current_time = time

    def __iter__(self):
        return self

    def __next__(self):
        if self.next_buffered is not None:
            msg = self.next_buffered
            self.next_buffered = None
            self.current_time = msg.logMonoTime
            return msg
        if self.current_entryiter is None:
            if self.next_file_idx >= len(self.allfiles):
                if self.loop:
                    self.next_file_idx = 0
                else:
                    self.current_time = None
                    raise StopIteration
            self.current_entryiter = messages.LogEntry.read_multiple_bytes(self.allfiles[self.next_file_idx].read_bytes())
            self.next_file_idx += 1
        try:
            msg = next(self.current_entryiter)
            self.current_time = msg.logMonoTime
            return msg
        except StopIteration:
            self.current_entryiter = None
            msg = next(self)
            self.current_time = msg.logMonoTime
            return msg
        
    def seek_time(self, time):
        if time < self.current_time:
            self.next_file_idx = 0
            self.current_entryiter = None
        self.next_buffered = None
        
        while self.current_time < time:
            self.next_buffered = next(self)
        self.current_time = time


class LogReplayServer:
    def __init__(self, context, rep_port, pub_port, sub_port, log_root_path):
        self.context = context
        self.rep_port = rep_port
        self.pub_port = pub_port
        self.sub_port = sub_port
        self.log_root_path = log_root_path
        self.log_replayer = None
        self._play_state = False
        self.log_id = None
        self.log_time_offset = None

    @property
    def play_state(self):
        return self._play_state
    
    @play_state.setter
    def play_state(self, state):
        if state and self.log_replayer is None:
            raise DeepDRRServerException(400, "no log loaded")
        
        self._play_state = state
        if state:
            self.log_time_offset = time.time() - self.log_replayer.current_time
        else:
            self.log_time_offset = None

    async def start(self):
        await asyncio.gather(
            self.command_loop(),
            self.status_loop(),
            self.replay_loop(),
        )

    async def command_loop(self):
        sub_socket = self.context.socket(zmq.SUB)
        sub_socket.hwm = 10000

        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 10000

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")
        sub_socket.connect(f"tcp://localhost:{self.sub_port}")

        sub_socket.subscribe(b"/replayd/in/")

        while True:
            try:
                latest_msgs = await zmq_poll_latest(sub_socket)

                for topic, data in latest_msgs.items():
                    if topic == b"/replayd/in/listrequest/":
                        pathes = list(Path(self.log_root_path).glob("*"))
                        pathes_sorted_mtime = sorted(pathes, key=os.path.getmtime)
                        pathes_sorted_mtime = [p for p in pathes_sorted_mtime if p.is_dir()]
                        msg = messages.LogList.new_message()
                        msg.init('logs', len(pathes_sorted_mtime))
                        for i, path in enumerate(pathes_sorted_mtime):
                            msg.logs[i].id = path.name
                            msg.logs[i].mtime = int(os.path.getmtime(path))
                        await pub_socket.send_multipart([b"/replayd/list/", msg.to_bytes()])
                        print("listrequest")
                    elif topic == b"/replayd/in/load/":
                        with messages.LoadLogRequest.from_bytes(data) as msg:
                            self.log_id = data.decode()
                            self.log_replayer = LogReplayer(Path(self.log_root_path) / data.decode())
                            self.log_replayer.seek_time(msg.startTime)
                            self.log_replayer.loop = msg.loop
                            self.play_state = msg.autoplay
                    elif topic == b"/replayd/in/loop/":
                        with messages.Bool.from_bytes(data) as msg:
                            self.log_replayer.loop = msg.value
                    elif topic == b"/replayd/in/start/":
                        self.play_state = True
                    elif topic == b"/replayd/in/stop/":
                        self.play_state = False
                    elif topic == b"/replayd/in/scrub/":
                        with messages.Float32.from_bytes(data) as msg:
                            prev_play_state = self.play_state
                            self.play_state = False
                            self.log_replayer.seek_time(msg.value)
                            self.play_state = prev_play_state

                await asyncio.sleep(0.001)

            except DeepDRRServerException as e:
                print(f"server exception: {e}")
                await pub_socket.send_multipart([b"/server_exception/", e.status_response().to_bytes()])
            

    async def status_loop(self):
        """
        Server for sending the status of the logger.
        """
        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 10000

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")

        while True:
            await asyncio.sleep(1)
            msg = messages.ReplayerStatus.new_message()
            msg.playing = self.play_state
            msg.time = self.log_replayer.current_time if self.log_replayer is not None else 0
            msg.logid = self.log_id if self.log_id is not None else ""
            msg.startTime = self.log_replayer.starttime if self.log_replayer is not None else 0
            msg.endTime = self.log_replayer.endtime if self.log_replayer is not None else 0
            msg.loop = self.log_replayer.loop if self.log_replayer is not None else False
            await pub_socket.send_multipart([b"/replayd/status/", msg.to_bytes()])
            print(f"replayd status: {msg.playing} {msg.time} {msg.logid} {msg.startTime} {msg.endTime} {msg.loop}")

    async def replay_loop(self):
        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 10000

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")

        print("-"*20)
        i = 0
        while True:
            while self.play_state and self.log_replayer is not None:
                print(f"replayd: {self.log_replayer.current_time}")
                try:
                    logentry = next(self.log_replayer)

                    # skip excluded topics
                    if any(logentry.topic.startswith(prefix) for prefix in excluded_prefixes):
                        continue

                    # sleep until it's time to send the message
                    while time.time() - self.log_time_offset < logentry.logMonoTime:
                        await asyncio.sleep(0.001)
                    
                    await pub_socket.send_multipart([logentry.topic, logentry.data])

                    i+= 1
                    if i % 1000 == 0:
                        print(f"sent {i} messages")
                except StopIteration:
                    self.play_state = False
                await asyncio.sleep()
            await asyncio.sleep(0.01)
            


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass




@app.command()
@unwrap_typer_param
def main(
        rep_port=typer.Argument(40100),
        pub_port=typer.Argument(40101),
        sub_port=typer.Argument(40102),
):
    print(f"rep_port: {rep_port}")
    print(f"pub_port: {pub_port}")
    print(f"sub_port: {sub_port}")

    log_root_path = Path("pvrlogs") 
    log_root_path = Path(os.environ.get("LOG_DIR", log_root_path))
    print(f"log_root_path: {log_root_path}")

    with zmq_no_linger_context(zmq.asyncio.Context()) as context:
        with LogReplayServer(context, rep_port, pub_port, sub_port, log_root_path) as time_server:
            asyncio.run(time_server.start())


if __name__ == '__main__':
    app()
