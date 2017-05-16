# coding=utf-8
import datetime
import threading
import time

import botlog
import db
import gl
import ja
import main


def get_all_bots():
    query = 'SELECT charid, login, charname FROM eve_bot'
    result = gl.d.select(query)
    
    if not result:
        return []
    
    return result


def run():
    try:
        now = datetime.datetime.now()
        
        while not gl.flagQuit:
            time.sleep(1)
            
            if datetime.datetime.now() - now > datetime.timedelta(minutes=5):
                now = datetime.datetime.now()
                
                # Раз в 5 минут дергаем БД, что бы не отвалилась по таймауту
                gl.d.select('SELECT id FROM eve_bot LIMIT 1')
    
    except Exception as e:
        print e


gl.l = botlog.Botlog()
gl.l.info('Начало записи')

gl.d = db.Db()

bots = get_all_bots()

if bots:
    for _bot in bots:
        bot_login = _bot[1].lower()
        
        gl.bots[bot_login] = {}
        
        gl.bots[bot_login]['id'] = int(_bot[0])
        gl.bots[bot_login]['login'] = bot_login
        gl.bots[bot_login]['name'] = _bot[2]
        
        gl.bots[bot_login]['online'] = None
        gl.bots[bot_login]['role'] = None
        gl.bots[bot_login]['group'] = None
        gl.bots[bot_login]['place'] = None

gl.j = ja.Ja()

t = threading.Thread(target=main.queue_check)
t.daemon = True
t.start()

t = threading.Thread(target=main.npc_queue)
t.daemon = True
t.start()

run()

gl.j.ja_close()

time.sleep(1)

gl.l.info('Конец записи')
gl.l.close()
