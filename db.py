# coding=utf-8
import time

import mysql.connector as Mysql


class Db:
    def __init__(self):
        self.con = None
        self.cur = None
        
        self.connect()
    
    def connect(self):
        try:
            self.con = None
            self.con = Mysql.Connect(host='172.20.0.3', database='', user='', password='', port=3306,
                                     charset='utf8', autocommit=True, connect_timeout=2)
            
            if self.con:
                self.cur = None
                self.cur = self.con.cursor()
        except Exception as e:
            print 'except in db.connect: {}'.format(e)
    
    def close(self):
        try:
            if self.cur:
                self.cur.close()
            
            if self.con:
                self.con.close()
        except Exception as e:
            print 'except in db.close: {}'.format(e)
    
    def _reconnect(self):
        try:
            print 'Reconnect'
            
            if self.con and self.con.is_connected():
                self.close()
            
            if self.cur:
                self.cur = None
            
            if self.con:
                self.con = None
            
            self.connect()
        except Exception as e:
            print 'except in _reconnect: {}'.format(e)
    
    def _select(self, query, params):
        try:
            if self.con is not None and self.con.is_connected():
                self.cur.execute(query, params)
                
                ret = self.cur.fetchall()
                
                return ret
            else:
                return 'error'
        
        except Exception as e:
            print 'except in db._select: {}\n{}\n{}'.format(e, query, params)
            return 'error'
    
    def _query(self, query, params):
        try:
            if self.con is not None and self.con.is_connected():
                if isinstance(params, list):
                    self.cur.executemany(query, params)
                else:
                    self.cur.execute(query, params)
            else:
                return 'error'
        
        except Exception as e:
            print 'except in db.query: {}\n{}\n{}'.format(e, query, params)
            return 'error'
    
    def select(self, query, params=None):
        try:
            # ret = self._select(query, params)
            # return ret
            
            error_count = 0
            
            while True:
                ret = self._select(query, params)
                
                if ret == 'error' and error_count < 2:
                    time.sleep(2.5)
                    
                    self._reconnect()
                    
                    error_count += 1
                    
                    continue
                
                return ret
        except Exception as e:
            print 'except in db.select: {}\n{}\n{}'.format(e, query, params)
    
    def query(self, query, params=None):
        try:
            # ret = self._query(query, params)
            # return ret
            
            error_count = 0
            
            while True:
                ret = self._query(query, params)
                
                if ret == 'error' and error_count < 2:
                    time.sleep(2.5)
                    
                    self._reconnect()
                    
                    error_count += 1
                    
                    continue
                
                return ret
        
        except Exception as e:
            print 'except in db.query: {}\n{}\n{}'.format(e, query, params)
