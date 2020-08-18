# -*- coding: utf-8 -*-


class Counter:
    def __init__(self, limit=0, action=None, *args, **kwargs):
        self.value = 0
        self.limit = limit
        self.action = action
        self.args = args
        self.kwargs = kwargs

    def clear(self):
        self.value = 0

    def reset(self):
        self.value = 0

    def inc(self):
        self.value += 1
        self.act()

    def check(self):
        return self.value > self.limit

    def act(self, action=None):
        if action is None:
            action = self.action
        if self.check():
            self.value = 0
            if action is not None:
                return action(*self.args, **self.kwargs)
            else:
                return True
        else:
            return False

    def __iadd__(self, other):
        self.value += other
        self.act()
        return self
