import datetime
import os
import threading
import time


def encode(message):
    return message.decode('utf-8').encode('windows-1251')


def get_dir():
    path = 'd:\\temp\\evelog\\'
    
    dirname = os.path.dirname(os.path.join(path, 'ruller') + '\\')
    
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    
    return dirname


class Botlog():
    def __init__(self):
        try:
            self.timer_stop = False
            
            t = threading.Thread(target=self.timer)
            t.daemon = True
            t.start()
            
            self._info = None
            self.day = datetime.datetime.date(datetime.datetime.now())
        
        except Exception as e:
            print 'except in botlog.__init__: {}'.format(e)
    
    def timer(self):
        
        now = datetime.datetime.now()
        
        while not self.timer_stop:
            time.sleep(1)
            
            if not self._info:
                continue
            
            if datetime.datetime.now() - now > datetime.timedelta(seconds=10):
                self._info.flush()
                
                now = datetime.datetime.now()
    
    def close(self):
        try:
            self.timer_stop = True
            
            self._info.flush()
            self._info.close()
        except Exception as e:
            print 'except in botlog.close: {}'.format(e)
    
    def flush(self):
        try:
            self._info.flush()
        except Exception as e:
            print 'except in botlog.flush: {}'.format(e)
    
    def info(self, message, prefix='general', status='INFO'):
        try:
            if self.day != datetime.datetime.date(datetime.datetime.now()):
                self._info.flush()
                self._info.close()
                self._info = None
            
            if not self._info:
                self.day = datetime.datetime.date(datetime.datetime.now())
                self._info = open(os.path.join(get_dir(), 'info_{}.log'.format(self.day)), 'a')
            
            now = str(datetime.datetime.now().replace(microsecond=0)).replace('-', '.')
            
            _str = '{:20} {:10} {:20} {}\n'.format(now, status, encode(prefix), encode(message))
            self._info.write(_str)
        except Exception as e:
            print 'except in botlog.info: {}'.format(e)
