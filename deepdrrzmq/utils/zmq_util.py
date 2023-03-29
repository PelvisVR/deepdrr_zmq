from contextlib import contextmanager
import zmq.asyncio
import zmq


@contextmanager
def zmq_no_linger_context(context):
    try:
        yield context
    finally:
        context.destroy(linger=0)


async def zmq_poll_latest(sub_socket, max_skip=1000):
    latest_msgs = {}

    topic, data = await sub_socket.recv_multipart()
    latest_msgs[topic] = data

    try:
        for i in range(max_skip):
            topic, data = await sub_socket.recv_multipart(flags=zmq.NOBLOCK)
            latest_msgs[topic] = data
    except zmq.ZMQError:
        pass

    return latest_msgs