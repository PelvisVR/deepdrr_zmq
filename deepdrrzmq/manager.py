# adapted from https://github.com/commaai/openpilot

import datetime
import os
import signal
import subprocess
import sys
import traceback
from typing import List, Tuple, Union
import logging

from .utils.zmq_util import *
from .process import *


def manager_prepare() -> None:
    for p in managed_processes.values():
        p.prepare()


def manager_cleanup() -> None:
    # send signals to kill all procs
    for p in managed_processes.values():
        p.stop(block=False)

    # ensure all are killed
    for p in managed_processes.values():
        p.stop(block=True)

    logging.info("everything is dead")


def manager_thread() -> None:
    logging.info("manager start")

    with zmq_no_linger_context(zmq.asyncio.Context()) as context:
        ensure_running(managed_processes.values())

        while True:
            ensure_running(managed_processes.values())

            running = ' '.join("%s%s\u001b[0m" % ("\u001b[32m" if p.proc.is_alive() else "\u001b[31m", p.name)
                                            for p in managed_processes.values() if p.proc)
            print(running)

            time.sleep(1)

            # todo: shutdown command
            # shutdown = False

            # if shutdown:
            #         break


def main() -> None:
    manager_prepare()

    # SystemExit on sigterm
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(1))

    try:
        manager_thread()
    except Exception:
        logging.exception("manager crashed")
        traceback.print_exc()
    finally:
        manager_cleanup()


procs = [
    PythonProcess("deepdrrd", "deepdrrzmq.deepdrrd", watchdog_max_dt=-1),
    PythonProcess("zmqproxyd", "deepdrrzmq.zmqproxyd", watchdog_max_dt=-1),
    PythonProcess("patientloaderd", "deepdrrzmq.patientloaderd", watchdog_max_dt=-1),
    PythonProcess("timed", "deepdrrzmq.timed", watchdog_max_dt=-1),
]

managed_processes = {p.name: p for p in procs}

if __name__ == "__main__":
    # set log level
    logging.basicConfig(level=logging.DEBUG)

    try:
        main()
    except Exception:
        logging.exception("manager main crashed")
        traceback.print_exc()
        
    
    logging.info("manager exit")
    # manual exit because we are forked
    sys.exit(0)
