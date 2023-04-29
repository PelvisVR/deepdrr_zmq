import asyncio
import os

import logging
from pathlib import Path

import capnp
import typer
import zmq.asyncio
import time
from deepdrrzmq.utils.zmq_util import zmq_no_linger_context

from .utils.typer_util import unwrap_typer_param
from .utils.server_util import make_response, DeepDRRServerException, messages
import random
import string


# app = typer.Typer()
app = typer.Typer(pretty_exceptions_show_locals=False)

class LogWriter:
    def __init__(self, fileobj):
        self.filestream = fileobj
        # self.filestream = log_file_path.open("wb")

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        pass

    def write(self, data):
        return self.filestream.write(data)

class LogShardWriter:
    def __init__(self, pattern, maxcount, maxsize, start_shard=0, verbose=False, **kw):
        self.verbose = 1
        self.maxcount = maxcount
        self.maxsize = maxsize
        self.kw = kw

        self.logstream = None
        self.shard = start_shard
        self.pattern = pattern
        self.total = 0
        self.count = 0
        self.size = 0
        self.fname = None
        self.next_stream()


    def next_stream(self):
        self.finish()
        self.fname = self.pattern % self.shard
        if self.verbose:
            print(
                "# writing",
                self.fname,
                self.count,
                "%.1f GB" % (self.size / 1e9),
                self.total,
            )
        self.shard += 1
        stream = open(self.fname, "wb")
        self.logstream = LogWriter(stream, **self.kw)
        self.count = 0
        self.size = 0

    def write(self, data):
        if (
            self.logstream is None
            or self.count >= self.maxcount
            or self.size >= self.maxsize
        ):
            self.next_stream()
        size = self.logstream.write(data)
        self.count += 1
        self.total += 1
        self.size += size

    def finish(self):
        if self.logstream is not None:
            self.logstream.close()
            assert self.fname is not None
            self.logstream = None

    def close(self):
        self.finish()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kw):
        self.close()


class LogRecorder:
    def __init__(self, log_root_path, **kw):
        self.kw = kw
        self.log_root_path = log_root_path
        self.session = None
        self.session_id = None

    def new_session(self):
        self.finish()
        self.session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

        date_string = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        log_foldername = f"{self.session_id}--{date_string}"
        log_filename = f"{self.session_id}--{date_string}--%d.pvrlog"

        log_folder = Path(self.log_root_path) / log_foldername
        log_folder.mkdir(parents=True, exist_ok=True)

        log_path = log_folder / log_filename

        self.session = LogShardWriter(str(log_path), **self.kw)

    def stop_session(self):
        self.finish()

    def write(self, data):
        if (
            self.session is None
        ):
            return
        self.session.write(data)

    def finish(self):
        if self.session is not None:
            self.session.close()
            self.session = None
            self.session_id = None

    def close(self):
        self.finish()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kw):
        self.close()

class LoggerServer:
    def __init__(self, context, rep_port, pub_port, sub_port, log_root_path):
        self.context = context
        self.rep_port = rep_port
        self.pub_port = pub_port
        self.sub_port = sub_port
        self.log_root_path = log_root_path
        self.log_recorder = LogRecorder(log_root_path, maxcount = 1e15, maxsize = 1e6)

    async def start(self):
        recorder_loop = self.logger_server()
        status_loop = self.status_server()
        await asyncio.gather(recorder_loop, status_loop)

    async def logger_server(self):
        sub_socket = self.context.socket(zmq.SUB)
        sub_socket.hwm = 10000

        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 10000

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")
        sub_socket.connect(f"tcp://localhost:{self.sub_port}")

        sub_socket.subscribe(b"")

        with self.log_recorder as log_file:
            while True:
                try:
                    latest_msgs = {}

                    try:
                        for i in range(1000):
                            topic, data = await sub_socket.recv_multipart(flags=zmq.NOBLOCK)
                            latest_msgs[topic] = data
                    except zmq.ZMQError:
                        pass

                    for topic, data in latest_msgs.items():
                        msg = messages.LogEntry.new_message()
                        msg.logMonoTime = time.time()
                        msg.topic = topic
                        msg.data = data
                        log_file.write(msg.to_bytes())

                        if topic == b"/loggerd/stop/":
                            log_file.stop_session()
                        elif topic == b"/loggerd/start/":
                            log_file.new_session()

                    await asyncio.sleep(0.001)

                except DeepDRRServerException as e:
                    print(f"server exception: {e}")
                    await pub_socket.send_multipart([b"/server_exception/", e.status_response().to_bytes()])


    async def status_server(self):
        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 10000

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")

        while True:
            await asyncio.sleep(1)
            msg = messages.LoggerStatus.new_message()
            msg.recording = self.log_recorder.session_id is not None
            msg.sessionId = self.log_recorder.session_id or ""
            await pub_socket.send_multipart([b"/loggerd/status/", msg.to_bytes()])
            print(f"sent logger status: {msg}")


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
        log_root_path=typer.Argument("pvrlogs")
):

    print(f"rep_port: {rep_port}")
    print(f"pub_port: {pub_port}")
    print(f"sub_port: {sub_port}")
    print(f"log_root_path: {log_root_path}")

    with zmq_no_linger_context(zmq.asyncio.Context()) as context:
        with LoggerServer(context, rep_port, pub_port, sub_port, log_root_path) as time_server:
            asyncio.run(time_server.start())


if __name__ == '__main__':
    app()
