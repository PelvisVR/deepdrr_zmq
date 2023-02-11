import time
import collections

class FPS:
    def __init__(self,printevery=1):
        self.starttime = time.time()
        self.printevery = printevery
        self.calls = 0
    def __call__(self):
        self.calls += 1
        if self.calls % self.printevery == 0:
            ret = self.printevery/(time.time()-self.starttime)
            self.starttime = time.time()
            return ret
        return None
            