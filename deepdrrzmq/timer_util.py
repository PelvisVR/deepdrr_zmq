import time
import collections

class FPS:
    def __init__(self,print_every_seconds=1):
        self.starttime = time.time()
        self.printevery = print_every_seconds
        self.calls = 0
    def __call__(self):
        self.calls += 1
        if time.time()-self.starttime > self.printevery:
            ret = self.calls/(time.time()-self.starttime) 
            self.starttime = time.time()
            self.calls = 0
            return ret
        return None
            