# coding=utf-8
import random
import time

flagQuit = False

bots = {}           # Боты

j = None
d = None
l = None

jets = {}           # Контейнеры
actions = {}        # Действия
anomalies = {}      # Аномальки

npcs = {}           # Непись
drones = {}         # Дроны в аномальках

npc_queue = {}      # Очередь нпц
npc_queue_ch = {}   # Флаги пересчета очереди

lastActionTime = None
isGarbaged = False      # Проводилась ли очистка мусора после ДТ

locks = {}      # Блокировки
glock = False

# Настройки из файл everuller.ini
opt = {
    u'general': {
        u'first_new': ''
    }
}


class Stack:
    def __init__(self):
        self.items = []

    def is_empty(self):
        return self.items == []

    def push(self, item):
        self.items.insert(0, item)

    def pop(self):
        return self.items.pop()

    def peek(self):
        return self.items[len(self.items)-1]

    def size(self):
        return len(self.items)


queue = Stack()


def lock(_lock):
    global glock

    while glock:
        pass

    glock = True

    if not isinstance(_lock, list):
        _lock = [_lock]

    for _l in _lock:
        if _l not in locks:
            locks[_l] = False

        while locks[_l]:
            pass

        locks[_l] = True

    glock = False


def lock_free(_lock):
    if not isinstance(_lock, list):
        _lock = [_lock]

    for _l in _lock:
        locks[_l] = False


# Генерирование случайной паузы
def get_random(fromtime=500, totime=1000):
    if fromtime > totime:
        fromtime = totime

    return float(random.randrange(fromtime, totime))


def rand_pause(fromtime=500, totime=1000):
    time.sleep(get_random(fromtime, totime) / 1000)

