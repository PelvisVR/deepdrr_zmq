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


class LogReplayServer:
    def __init__(self, context, rep_port, pub_port, sub_port, log_root_path):
        self.context = context
        self.rep_port = rep_port
        self.pub_port = pub_port
        self.sub_port = sub_port
        self.log_root_path = log_root_path
        # self.log_recorder = LogRecorder(log_root_path, maxcount = 1e15, maxsize = 1e6)

    async def start(self):
        recorder_loop = self.logger_server()
        status_loop = self.replay_server()
        await asyncio.gather(recorder_loop, status_loop)

    async def logger_server(self):
        """
        Server for logging data from the surgical simulation.
        """
        sub_socket = self.context.socket(zmq.SUB)
        sub_socket.hwm = 10000

        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 10000

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")
        sub_socket.connect(f"tcp://localhost:{self.sub_port}")

        sub_socket.subscribe(b"")

        # with self.log_recorder as log_file:
        #     while True:
        #         try:
        #             latest_msgs = await zmq_poll_latest(sub_socket)

        #             for topic, data in latest_msgs.items():
        #                 # write to log file
        #                 msg = messages.LogEntry.new_message()
        #                 msg.logMonoTime = time.time()
        #                 msg.topic = topic
        #                 msg.data = data
        #                 log_file.write(msg.to_bytes())

        #                 # process loggerd commands
        #                 if topic == b"/loggerd/stop/":
        #                     log_file.stop_session()
        #                 elif topic == b"/loggerd/start/":
        #                     log_file.new_session()

        #             await asyncio.sleep(0.001)

        #         except DeepDRRServerException as e:
        #             print(f"server exception: {e}")
        #             await pub_socket.send_multipart([b"/server_exception/", e.status_response().to_bytes()])


    async def replay_server(self):
        """
        Server for sending the status of the logger.
        """
        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 10000

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")

        # folder = "pvrlogs/tbawxnvfmzmwa17w--2023-05-21-13-30-48"
        # get most recent folder in pvrlogs
        folder = max(Path(self.log_root_path).glob("*"), key=os.path.getmtime)
        print(f"replaying folder {folder}")
        files = Path(folder).glob("*.pvrlog")
        listfiles = list(files)
        sortedfiles = sorted(listfiles, key=lambda x: x.stem.split("--")[-1])
        

        while True:
            print("-"*20)
            i = 0
            log_time_offset = None
            for file in sortedfiles:
                print(f"replaying {file}")
                for logentry in messages.LogEntry.read_multiple_bytes(file.read_bytes()):
                    log_time = logentry.logMonoTime
                    if log_time_offset is None:
                        log_time_offset = time.time() - log_time

                    # sleep until it's time to send the message
                    while time.time() - log_time_offset < log_time:
                        await asyncio.sleep(0.001)
                    
                    await pub_socket.send_multipart([logentry.topic, logentry.data])

                    i+= 1
                    if i % 1000 == 0:
                        print(f"sent {i} messages")


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
        with LogReplayServer(context, rep_port, pub_port, sub_port, log_root_path) as time_server:
            asyncio.run(time_server.start())


if __name__ == '__main__':
    app()
