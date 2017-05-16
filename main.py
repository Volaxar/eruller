# coding=utf-8
import datetime
import math
import os
import pickle
import threading
import time

from configobj import ConfigObj

import gl


# region Общие методы


# Обработка очереди запросов к БД
def queue_check():
    try:
        while not gl.flagQuit:
            if not gl.queue.is_empty():
                s = gl.queue.pop()

                if s['type'] == 'select':
                    answer = gl.d.select(s['query'], s['params'])
                    send_answer(s['from'], answer, s['rnd'])

                elif s['type'] == 'query':
                    gl.d.query(s['query'], s['params'])

            time.sleep(0.01)

    except Exception as e:
        print 'except in queue_check: {}'.format(e)


# Загрузка настроек
def refresh_opt():
    config = ConfigObj('Z:\\EveRuller\\everuller.ini')

    if config:
        gl.opt = config


def send_answer(_from, answer, rnd):
    gl.l.info('Отправляем ответ {} для {}: {}'.format(rnd, _from, answer))

    ans = {'type': 'answer', 'answer': answer, 'rnd': rnd}
    gl.j.ja_send('{}@172.20.0.3'.format(_from), '?{}'.format(pickle.dumps(ans)))


def send_notification(_from, func, data=None):
    rec = {'type': 'notification', 'func': func, 'args': data}

    gl.j.ja_send('{}@172.20.0.3'.format(_from), '?{}'.format(pickle.dumps(rec)))


# Запрос к БД
def db_send(_from, s):
    gl.l.info('Пришел запрос от {}: {}'.format(_from, s))

    if 'rnd' in s:
        rnd = s['rnd']
    else:
        rnd = None

    gl.queue.push({'from': _from, 'type': s['type'], 'query': s['query'], 'params': s['params'], 'rnd': rnd})


# Записать данные в БД
def query(_from, s):
    db_send(_from, s)


# Получить данные из БД
def select(_from, s):
    db_send(_from, s)


# endregion


# region Методы Crub


# Обработка очереди нпц
def npc_queue():
    try:
        while not gl.flagQuit:

            for k, v in gl.npc_queue_ch.items():
                if v and datetime.datetime.now() - v > datetime.timedelta(seconds=1):
                    gl.npc_queue_ch[k] = None

                    threading.Thread(target=calc_npc_queue, args=(k, )).start()

            time.sleep(1)

    except Exception as e:
        print 'except in npc_queue: {}'.format(e)


# endregion


# Установка статуса бота
def set_bot_params(_from, s):
    gl.lock('bots')

    gl.l.info('Установка параметров бота {}: {}'.format(_from, s))

    p_type = s['p_type']    # online, role, place, ...
    value = s['value']

    # TODO: Лажа, перенести в другое место
    # Сбрасываем привязку дронов к неписи, если любой корабль в группе покидает грид
    if gl.bots[_from]['role'] == 'crub':
        if p_type == 'place' and gl.bots[_from]['place'] and not value:
            place_id = gl.bots[_from]['place']

            if place_id:
                threading.Thread(target=reset_site_drone, args=(place_id, )).start()

    gl.bots[_from][p_type] = value

    # Сбрасываем параметры
    if p_type == 'online':
        gl.bots[_from]['role'] = None
        gl.bots[_from]['group'] = None
        gl.bots[_from]['place'] = None

    # Рассылка статуса другим ботам
    for k, v in gl.bots.items():
        if k != _from and v['online']:
            send_notification(k, 'update_data', gl.bots[_from])

            gl.l.info('Отправили уведомление для {} от {}: {}'.format(k, _from, gl.bots[_from]))

    gl.lock_free('bots')


# Запрос на получение параметров активных ботов
def get_bots_params(_from, s):
    gl.lock('bots')

    gl.l.info('Запрос от {} на получение параметров активных ботов: {}'.format(_from, s))

    data = []

    for k, v in gl.bots.items():
        if k != _from and v['online']:
            data.append(v)

    gl.lock_free('bots')

    send_answer(_from, data, s['rnd'])


# Получить статус контейнера и заблокировать его если необходимо
def jet_status(_from, s):
    gl.lock('jets')

    gl.l.info('Запрос от {} статуса джета: {}'.format(_from, s))

    jet_id = s['jet_id']
    lock = s['lock']

    if jet_id not in gl.jets \
            or datetime.datetime.now() - gl.jets[jet_id]['time'] > datetime.timedelta(seconds=15) \
            or _from == gl.jets[jet_id]['owner']:

        if lock:
            if jet_id not in gl.jets:
                gl.jets[jet_id] = {}

            gl.jets[jet_id]['owner'] = _from
            gl.jets[jet_id]['time'] = datetime.datetime.now()

        status = 'free'

    else:
        status = 'busy'

    gl.lock_free('jets')

    send_answer(_from, status, s['rnd'])


# Освободить контейнер
def jet_free(_from, s):
    gl.lock('jets')

    gl.l.info('Освобождение джета от {}: {}'.format(_from, s))

    jet_id = s['jet_id']

    if jet_id in gl.jets and _from == gl.jets[jet_id]['owner']:
        del gl.jets[jet_id]

    gl.lock_free('jets')


# Выполняется действие
def do_action(_from, s):
    gl.lock('actions')

    gl.l.info('Выполнение действия от {}: {}'.format(_from, s))

    act = s['action']
    grid = s['grid']
    gr = s['gr']

    if gr:
        who = gr
    else:
        who = _from

    if grid not in gl.actions:
        gl.actions[grid] = {}

    if act not in gl.actions[grid]:
        gl.actions[grid][act] = {}

    now = datetime.datetime.now()

    gl.actions[grid][act]['who'] = who
    gl.actions[grid][act]['time'] = now

    gl.lastActionTime = now

    gl.lock_free('actions')


# Отмена выполнения действия
def unlock_action(_from, s):
    gl.lock('actions')

    gl.l.info('Отмена выполнение действия от {}: {}'.format(_from, s))

    act = s['action']
    grid = s['grid']
    gr = s['gr']

    if gr:
        who = gr
    else:
        who = _from

    if grid in gl.actions and act in gl.actions[grid]:
        if gl.actions[grid][act]['who'] == who:
            gl.actions[grid][act] = {'who': None, 'time': None}

    gl.lock_free('actions')


# Запрос на выполнение действия
def act_status(_from, s):
    gl.lock('actions')

    gl.l.info('Запрос на выполнение действия от {}: {}'.format(_from, s))

    act = s['action']
    grid = s['grid']
    add_time = s['add_time']
    gr = s['gr']
    lock = s['lock']

    if gr:
        who = gr
    else:
        who = _from

    if grid not in gl.actions:
        gl.actions[grid] = {}

    now = datetime.datetime.now()

    status = 'ready'

    if gl.lastActionTime and now - gl.lastActionTime < datetime.timedelta(milliseconds=1000):
        tm = datetime.timedelta(milliseconds=1000) - (now - gl.lastActionTime)
        status = now + tm

    elif act not in gl.actions[grid]:
        gl.actions[grid][act] = {'who': None, 'time': None}

    elif gl.actions[grid][act]['time']:
        delay_time = 1000 + gl.get_random(1000, 2000) + add_time
        delta_flag = now - gl.actions[grid][act]['time'] < datetime.timedelta(milliseconds=delay_time)

        if gl.actions[grid][act]['who'] != who and delta_flag:
            tm = datetime.timedelta(milliseconds=delay_time) - (now - gl.actions[grid][act]['time'])
            status = now + tm

    if status == 'ready' and lock:
        if grid not in gl.actions:
            gl.actions[grid] = {}

        if act not in gl.actions[grid]:
            gl.actions[grid][act] = {}

        gl.actions[grid][act]['who'] = who
        gl.actions[grid][act]['time'] = now

        gl.lastActionTime = now

    gl.lock_free('actions')

    send_answer(_from, status, s['rnd'])


# Получить статус аномали
# free - свободна
# pre - потенциально следующая аномалька
# marked - помеченная, но еще не занятая
# begined - начато прохождение
# ended - выполнение аномали завершено
# busy - аномаль занята
# other - аномаль выполняется другой группой - виртуальный статус
def get_anomaly_status(_from, s):
    gl.lock('anomalies')

    gl.l.info('Запрос на получение статуса аномальки от {}: {}'.format(_from, s))

    status = _get_anomaly_status(s['site_id'], s['who'])

    gl.lock_free('anomalies')

    send_answer(_from, status, s['rnd'])


def _get_anomaly_status(site_id, who):
    status = 'free'

    if site_id not in gl.anomalies:
        status = 'ended'

    else:
        if gl.anomalies[site_id]['status'] in ['busy', 'ended']:
            status = gl.anomalies[site_id]['status']

        elif gl.anomalies[site_id]['status'] in ['pre', 'marked', 'begined']:

            if who == gl.anomalies[site_id]['who']:
                status = gl.anomalies[site_id]['status']
            else:
                status = 'other'

    return status


# Установить статус аномали
def set_anomaly_status(_from, s):
    gl.lock('anomalies')

    gl.l.info('Установка статуса аномальки от {}: {}'.format(_from, s))

    site_id = s['site_id']
    status = s['status']

    old_status = gl.anomalies[site_id]['status']

    if status == 'busy':
        if old_status in ['pre', 'free']:
            gl.anomalies[site_id]['send'] = True
            gl.anomalies[site_id]['who'] = None
        else:
            status = old_status

    gl.anomalies[site_id]['status'] = status

    gl.lock_free('anomalies')

    if old_status != status:
        gl.l.info('Новый статус аномальки {} - {}'.format(site_id, gl.anomalies[site_id]['status']))

        show_screen()


# Получить свободную аномальку
def get_anomaly(_from, s):
    gl.lock('anomalies')

    gl.l.info('Запрос на получение свободной аномальки от {}: {}'.format(_from, s))

    who = s['who']

    data = None

    # Если есть помеченная или начатая аномаль, возвращаем ее
    for k, v in gl.anomalies.items():

        if v['who'] == who and v['status'] in ['marked', 'begined']:
            data = _get_anomaly_data(k)

            break

    gl.lock_free('anomalies')

    send_answer(_from, {'data': data}, s['rnd'])


# Выбрать и пометить свободную аномальку
def sel_anomaly(_from, s):
    gl.lock('anomalies')

    gl.l.info('Помечаем аномальку как рабочую от {}: {}'.format(_from, s))

    who = s['who']
    pos = s['pos']

    site_id = None
    data = None

    # Если есть помеченная или начатая аномаль, возвращаем ее
    for k, v in gl.anomalies.items():

        # Если запрашиваемая аномаль уже есть
        if v['who'] == who and v['status'] in ['pre', 'marked', 'begined']:
            site_id = k

            break

    # Получаем свободную аномаль
    if not site_id:
        site_list = []

        for k, v in gl.anomalies.items():

            if v['status'] == 'free':
                if pos:
                    site_list.append((_get_dist(pos, v['pos']), v))
                else:
                    site_list.append((v['full_name'], v))

        site_list.sort()

        if site_list:
            v = site_list[0][1]

            site_id = v['id']

            gl.anomalies[site_id]['status'] = 'pre'
            gl.anomalies[site_id]['who'] = who

    if site_id:
        data = _get_anomaly_data(site_id)

    gl.lock_free('anomalies')

    send_answer(_from, {'data': data}, s['rnd'])


def _get_anomaly_data(site_id):

    data = {}

    if site_id in gl.anomalies:
        for x in ['site_id', 'full_name', 'pos', 'dni', 'status']:
            data[x] = gl.anomalies[site_id][x]

    return data


# Получить список ид аномалек
def get_anomaly_list(_from, s):
    gl.lock('anomalies')

    gl.l.info('Запрос на получение списка аномалек от {}: {}'.format(_from, s))

    ans = [x for x in gl.anomalies.keys()]

    gl.lock_free('anomalies')

    send_answer(_from, ans, s['rnd'])


# Добавляем недостающие аномальки в список
def set_anomaly_list(_from, s):
    gl.lock('anomalies')

    gl.l.info('Добавляем недостающие аномальки в список от {}: {}'.format(_from, s))

    data = s['data']

    for v in data.values():

        site_id = v['site_id']
        full_name = v['name']
        status = v['status']
        pos = v['pos']
        dni = v['dni']

        if full_name:
            name = full_name[-3:]
        else:
            name = None

        if site_id not in gl.anomalies:
            gl.anomalies[site_id] = {
                'site_id': site_id,
                'status': status,
                'who': None,
                'full_name': full_name,
                'name': name,
                'send': False,
                'pos': pos,
                'dni': dni
            }

    gl.lock_free('anomalies')

    show_screen()


# Удаляем аномальки из списка
def del_anomaly_list(_from, s):
    gl.lock('anomalies')

    gl.l.info('Удаляем аномальки из списка от {}: {}'.format(_from, s))

    data = s['data']

    for site_id in data:
        if site_id in gl.anomalies and gl.anomalies[site_id]['status'] in ['free', 'busy', 'ended']:
            gl.l.info('Удаляю аномальку: {}'.format(site_id))
            del gl.anomalies[site_id]

    gl.lock_free('anomalies')

    show_screen()


def show_screen():
    threading.Thread(target=_show_screen).start()


def _show_screen():
    gl.lock('screen')

    os.system('cls')

    _show_anomaly_list()

    gl.lock_free('screen')


def _show_anomaly_list():
    alist = {}

    for k, v in gl.anomalies.items():
        if v['status'] not in alist:
            alist[v['status']] = []

        alist[v['status']].append((v['full_name'], v['name']))

    tlist = ['pre', 'marked', 'begined', 'free', 'busy', 'ended']

    for t in tlist:
        if t in alist:
            print '{}:'.format(t)

            alist[t].sort()

            for n1, n2 in alist[t]:
                if n1 and n2:
                    print '{} - {}'.format(n2, n1)

            print ''


def set_send_status(_from, s):
    gl.lock('anomalies')

    gl.l.info('Установка статуса отправки аномальки от {}: {}'.format(_from, s))

    _id = s['site_id']

    gl.anomalies[_id]['send'] = True

    gl.lock_free('anomalies')


def get_send_status(_from, s):
    gl.lock('anomalies')

    gl.l.info('Получение статуса отправки аномальки от {}: {}'.format(_from, s))

    site_id = s['site_id']

    gl.lock_free('anomalies')

    send_answer(_from, gl.anomalies[site_id]['send'], s['rnd'])


def set_ball_pos(_from, s):
    gl.lock('npc')

    gl.l.info('Добавляем координаты неписи и дронов {}: {}'.format(_from, s))

    _id = s['site_id']

    npc_list = s['npc']
    drone_list = s['drone']

    if _id in gl.npcs:
        for k, v in npc_list.items():
            if k in gl.npcs[_id]:
                gl.npcs[_id][k]['pos'] = v

    if _id in gl.drones:
        for k, v in drone_list.items():
            if k in gl.drones[_id]:
                gl.drones[_id][k]['pos'] = v

    gl.lock_free('npc')


# Добавляем непись в аномаль
def add_npc(_from, s):
    gl.lock('npc')

    gl.l.info('Добавляем непись {}: {}'.format(_from, s))

    _id = s['site_id']
    npc_list = s['npc_list']

    if _id not in gl.npcs:
        gl.npcs[_id] = {}

    if _id in gl.drones:
        for k in gl.drones[_id].keys():
            gl.drones[_id][k]['npc'] = None

    for k in gl.npcs[_id].keys():
        gl.npcs[_id][k]['dmg'] = 0
        gl.npcs[_id][k]['list'] = []

    for npc_id, npc_info in npc_list:
        if npc_id not in gl.npcs[_id]:
            gl.npcs[_id][npc_id] = npc_info
            gl.npcs[_id][npc_id]['dmg'] = 0                         # Суммарный демаг от дронов
            gl.npcs[_id][npc_id]['list'] = []                       # Список дронов
            gl.npcs[_id][npc_id]['pos'] = None                      # Координаты нпц

    gl.npc_queue_ch[_id] = datetime.datetime.now()

    gl.lock_free('npc')


# Удаляем непись из аномали
def del_npc(_from, s):
    gl.lock('npc')

    gl.l.info('Удаляем непись {}: {}'.format(_from, s))

    _id = s['site_id']
    npc_list = s['npc_list']

    if _id in gl.npcs:
        for npc_id in npc_list:
            if npc_id in gl.npcs[_id]:
                for drone_id in gl.npcs[_id][npc_id]['list']:
                    gl.drones[_id][drone_id]['npc'] = None

                del gl.npcs[_id][npc_id]

        gl.npc_queue_ch[_id] = datetime.datetime.now()

    gl.lock_free('npc')


# Расстояние между двумя точками
def _get_dist(p1, p2):
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2)


def _get_free_drone(site_id):
    dmg_list = {}

    # Распределяем дронов в группы по наносимому урону
    for k, v in gl.drones[site_id].items():
        if v['npc']:
            continue

        if v['dmg'] not in dmg_list:
            dmg_list[v['dmg']] = []

        dmg_list[v['dmg']].append(k)

    min_dmg = []

    # Определяем минимальный урон
    for k in dmg_list.keys():
        min_dmg.append(k)

    min_dmg.sort()

    # Выбираем дронов с минимальным демагом
    for i in min_dmg:
        for k in dmg_list[i]:
            return k

    return None


# Список дронов распределенных в группы по наносимому урону
def _get_dmg_list(site_id):
    dmg_list = {}

    # Распределяем дронов в группы по наносимому урону
    for k, v in gl.drones[site_id].items():
        if v['npc'] or not v['pos']:
            continue

        if v['dmg'] not in dmg_list:
            dmg_list[v['dmg']] = []

        dmg_list[v['dmg']].append(k)

    return dmg_list


# Получить любого дрона, в приоритете дроны без координат
def _get_any_drone(site_id):
    for k, v in gl.drones[site_id].items():
        if v['npc'] or v['pos']:
            continue

        return k

    for k, v in gl.drones[site_id].items():
        if v['npc']:
            continue

        return k

    return None


# Получить ближайшего дрона к нпц
def _get_near_drone(site_id, npc_id):
    drone_list = []

    npc_pos = gl.npcs[site_id][npc_id]['pos']

    if not npc_pos:
        return _get_any_drone(site_id)

    dmg_list = _get_dmg_list(site_id)

    min_dmg = []

    # Определяем минимальный урон
    for k in dmg_list.keys():
        min_dmg.append(k)

    min_dmg.sort()

    # Выбираем дронов с минимальным демагом
    for i in min_dmg:
        for k in dmg_list[i]:
            pos = gl.drones[site_id][k]['pos']
            drone_list.append((_get_dist(npc_pos, pos), k))

        if drone_list:
            break

    if drone_list:
        drone_list.sort()

        return drone_list[0][1]

    return _get_any_drone(site_id)


# Сбрасываем привязку дронов к неписи
def reset_site_drone(site_id):
    gl.lock('npc')

    if site_id in gl.drones:
        for drone_id in gl.drones[site_id].keys():
            if drone_id in gl.drones[site_id]:
                gl.drones[site_id][drone_id]['npc'] = None

    if site_id not in gl.npcs:
        gl.npcs[site_id] = {}

    for npc_id in gl.npcs[site_id].keys():
        gl.npcs[site_id][npc_id]['dmg'] = 0
        gl.npcs[site_id][npc_id]['list'] = []

    gl.npc_queue_ch[site_id] = datetime.datetime.now()

    gl.lock_free('npc')


# Пересчет очереди нпц в гриде
def calc_npc_queue(site_id):
    gl.lock('npc')

    if site_id in gl.drones and site_id in gl.npcs:

        queue = []

        q = {}

        for x in range(1, 8):
            q[x] = []

        # Сортируем непись по очереди в порядке приоритета
        for k, v in gl.npcs[site_id].items():

            # Центрики с носферату
            if v['sentry'] and bool(v['nosferatu']):
                q[1].append(k)

            # Фригаты со скрамблерами
            elif v['sig'] < 50 and bool(v['scramble']):
                q[2].append(k)

            # Фригаты
            elif v['sig'] < 50:
                q[3].append(k)

            # Остальные центрики
            elif v['sentry']:
                q[4].append(k)

            # Элитные и сентинели
            elif v['name'].split(' ')[0] in ['Elite', 'Sentient']:
                q[5].append(k)

            # Остальные корабли, кроме БШ
            elif v['sig'] < 350:
                q[6].append((v['sig'], k))

            # БШ и все остальное
            else:
                q[7].append(k)

        # Собираем очередь
        for x in range(1, 8):
            if x in [1, 2, 3, 4, 5, 7]:
                q[x].sort(reverse=bool(gl.opt['general']['first_new']))
                queue += q[x]

            elif x == 6:
                tmp = {}

                for i in q[x]:
                    if i[0] not in tmp:
                        tmp[i[0]] = []

                    tmp[i[0]].append(i[1])

                for key in sorted(tmp):
                    tmp[key].sort(reverse=bool(gl.opt['general']['first_new']))
                    queue += tmp[key]

        change_list = []
        bots_list = {}

        dmg_list = {}

        # Распределяем дронов в группы по наносимому урону
        for k, v in gl.drones[site_id].items():
            if v['dmg'] not in dmg_list:
                dmg_list[v['dmg']] = []

            dmg_list[v['dmg']].append(k)

        min_dmg = []

        # Определяем минимальный урон
        for k in dmg_list.keys():
            min_dmg.append(k)

        min_dmg.sort()

        ed = 30         # Расчетное время уничтожения неписи в секундах

        # Назначаем дронов для неписи
        for i in range(1, 4):
            ed /= i

            for npc_id in queue:
                ehp = gl.npcs[site_id][npc_id]['ehp']

                # Выбираем дронов с минимальным демагом
                for m in min_dmg:
                    for k in dmg_list[m]:

                        if gl.drones[site_id][k]['npc']:
                            continue

                        dmg = gl.npcs[site_id][npc_id]['dmg']

                        if not dmg or ehp / dmg > ed:
                            v = gl.drones[site_id][k]

                            if v['min_sig'] > gl.npcs[site_id][npc_id]['sig']:
                                continue

                            gl.drones[site_id][k]['npc'] = npc_id
                            gl.npcs[site_id][npc_id]['list'].append(k)
                            gl.npcs[site_id][npc_id]['dmg'] += v['dmg']

                            if v['from'] not in change_list:
                                change_list.append(v['from'])

                if not _get_any_drone(site_id):
                    break

        for k, v in gl.drones[site_id].items():
            if v['npc']:
                npc_id = v['npc']

                if npc_id not in bots_list:
                    bots_list[npc_id] = []

                if v['from'] not in bots_list[npc_id]:
                    bots_list[npc_id].append(v['from'])

        # Помечаем непись которую будут лочить боты
        for k, v in gl.bots.items():
            if v['place'] != site_id:
                continue

            for npc_id in queue:

                if npc_id not in bots_list:
                    bots_list[npc_id] = []

                if v['login'] in bots_list[npc_id]:
                    continue

                dmg = gl.npcs[site_id][npc_id]['dmg']
                ehp = gl.npcs[site_id][npc_id]['ehp']

                if not dmg or ehp / dmg > ed:
                    bots_list[npc_id].append(v['login'])

        gl.npc_queue[site_id] = []

        for npc_id in queue:
            if npc_id not in bots_list:
                bots_list[npc_id] = []

            gl.npc_queue[site_id].append((npc_id, gl.npcs[site_id][npc_id]['list'], bots_list[npc_id]))

        for f in change_list:
            send_notification(f, 'update_npc_queue')

    gl.lock_free('npc')


# Запрос на получения очереди из неписи
def get_npc_queue(_from, s):
    gl.lock('npc')

    gl.l.info('Запрос неписевой очереди {}: {}'.format(_from, s))

    _id = s['site_id']

    queue = []

    if _id in gl.npc_queue:
        queue = gl.npc_queue[_id]

    gl.lock_free('npc')

    send_answer(_from, queue, s['rnd'])


def add_drones_space(_from, s):
    gl.lock('npc')

    gl.l.info('Добавляем дронов на аномальку {}: {}'.format(_from, s))

    _id = s['site_id']
    drones = s['drones']    # [(drone_id, (damage, min_sig)), ...]

    change_flag = False

    if _id not in gl.drones:
        gl.drones[_id] = {}

    for k, v in drones:
        if k not in gl.drones[_id]:
            change_flag = True

            gl.drones[_id][k] = {'dmg': v[0], 'min_sig': v[1], 'npc': None, 'from': _from, 'pos': None}

    if change_flag:
        gl.npc_queue_ch[_id] = datetime.datetime.now()

    gl.lock_free('npc')


def del_drones_space(_from, s):
    gl.lock('npc')

    gl.l.info('Удаляем дронов с аномальки {}: {}'.format(_from, s))

    _id = s['site_id']
    drones = s['drones']    # [drone_id, ...]

    change_flag = False

    if _id in gl.drones:
        for drone_id in drones:
            if drone_id in gl.drones[_id]:
                change_flag = True

                npc_id = gl.drones[_id][drone_id]['npc']

                if npc_id:
                    if drone_id in gl.npcs[_id][npc_id]['list']:
                        gl.npcs[_id][npc_id]['dmg'] -= gl.drones[_id][drone_id]['dmg']

                        gl.npcs[_id][npc_id]['list'].remove(drone_id)

                del gl.drones[_id][drone_id]

    if change_flag:
        gl.npc_queue_ch[_id] = datetime.datetime.now()

    gl.lock_free('npc')


# Принудительная установка статуса по имени
def sas(name, status):
    for k, v in gl.anomalies.items():

        if name == v['name'] or name == v['full_name']:
            gl.l.info('Принудительная установка статуса аномальки {}: {}'.format(v['full_name'], status))

            gl.anomalies[k]['status'] = status

            break

    show_screen()


def all_free():
    for k, v in gl.anomalies.items():

        gl.l.info('Принудительная установка статуса аномальки {}: {}'.format(v['full_name'], 'free'))
        gl.anomalies[k]['status'] = 'free'

    show_screen()
