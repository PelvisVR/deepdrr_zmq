
import capnp
import typer
import zmq.asyncio
import os

file_path = os.path.dirname(os.path.realpath(__file__))
messages = capnp.load(os.path.join(file_path, "..", 'messages.capnp'))

def make_response(code, message):
    response = messages.StatusResponse.new_message()
    response.code = code
    response.message = message
    return response

def capnp_optional(optional):
    if optional.which() == "value":
        return optional.value
    else:
        return None

def capnp_square_matrix(optional):
    if len(optional.data) == 0:
        return None
    else:
        arr = np.array(optional.data)
        size = len(arr)
        side = int(size ** 0.5)
        assert size == side ** 2, f"expected square matrix, got {size} elements"
        arr = arr.reshape((side, side))
        return arr

class DeepDRRServerException(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return f"DeepDRRServerError({self.code}, {self.message})"

    def status_response(self):
        return make_response(self.code, self.message)
    