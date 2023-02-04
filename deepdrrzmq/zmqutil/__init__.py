from contextlib import contextmanager
import zmq.asyncio
import zmq


@contextmanager
def zmq_no_linger_context(context):
    try:
        yield context
    finally:
        context.destroy(linger=0)
