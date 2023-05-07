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


# app = typer.Typer()
app = typer.Typer(pretty_exceptions_show_locals=False)


class LoggerServer:
    """
    A process that replays all messages from a log file.
    """
    def __init__(self, context, rep_port, pub_port, sub_port):
        """
        :param context: The ZMQ context to use for creating sockets.
        :param rep_port: The port to use for the request/reply socket.
        :param pub_port: The port to use for the publisher socket.
        :param sub_port: The port to use for the subscriber socket.
        """
        self.context = context
        self.rep_port = rep_port
        self.pub_port = pub_port
        self.sub_port = sub_port

    async def start(self):
        project = self.logger_server()
        await asyncio.gather(project)

    async def logger_server(self):
        sub_socket = self.context.socket(zmq.SUB)
        sub_socket.hwm = 10000

        pub_socket = self.context.socket(zmq.PUB)
        pub_socket.hwm = 10000

        pub_socket.connect(f"tcp://localhost:{self.pub_port}")
        sub_socket.connect(f"tcp://localhost:{self.sub_port}")

        sub_socket.subscribe(b"")

        log_file_path = Path("log.plog")
        log_file = log_file_path.open("wb")

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

                time.sleep(1)

            except DeepDRRServerException as e:
                print(f"server exception: {e}")
                await pub_socket.send_multipart([b"/server_exception/", e.status_response().to_bytes()])



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

    with zmq_no_linger_context(zmq.asyncio.Context()) as context:
        with LoggerServer(context, rep_port, pub_port, sub_port) as time_server:
            asyncio.run(time_server.start())


if __name__ == '__main__':
    app()

