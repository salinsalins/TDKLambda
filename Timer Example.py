import time
import threading


def timer_function():
    global b
    print(time.time() - t0, 'timer function')
    b = 2


timer = threading.Timer(1.0, timer_function)
timer.start()
t0 = time.time()
a = 0
b = 0
print(time.time() - t0, 'started')
while time.time() - t0 < 2.1:
    #print('qq')
    print(time.time() - t0, 'in the loop')
    #time.sleep(0.2)
    a += 1
    pass
print(time.time() - t0, 'finished')
print(b)