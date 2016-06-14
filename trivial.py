#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import weechat
import sqlite3

import sys
reload(sys)
sys.setdefaultencoding('utf8')

from datetime import datetime

class TrivialRoom:
                    #==================#
                    # OPTIONS SETTINGS #
                    #==================#

    def __init__(self):
        self.running = False
        self.trivial = {}
        self.Load_Vars()

    def Load_Vars(self):
        global options
        self.opts = {}
        for option in options.keys():
            self.opts[option] = self.MyOpt(option)
        self.buffer_ptr = weechat.buffer_search('irc','%s.%s' %(self.opts['server'], self.opts['room']))

    def MyOpt(self, option):
        value = weechat.config_get_plugin(option)
        return value

                    #==================#
                    # LISTENER METHODS #
                    #==================#

    def Start_Listener(self):
        my = self
        self.listener_hook = weechat.hook_print(self.buffer_ptr, 'irc_privmsg', '', 1, 'Check_message_cb', '')

    def Stop_Listener(self):
        weechat.unhook(self.listener_hook)

                    #==============#
                    # NICK METHODS #
                    #==============#

    def Check_Nick(self, prefix):
        if weechat.nicklist_search_nick(self.buffer_ptr, '', prefix):
            return prefix
        else:
            wildcards = '+@'
            if prefix[0] in wildcards:
                if weechat.nicklist_search_nick(self.buffer_ptr, '', prefix[1:]):
                    return prefix[1:]

    def Is_Admin(self, nick):
        nicklist = self.admin_nicks.split(',')
        nicklist = [nick_ad.strip(' ') for nick_ad in nicklist]
        if nick in nicklist:
            return True
        else:
            return False

                    #=================#
                    # SQLITE3 METHODS #
                    #=================#

    def OpenDB(self):
        self.dbpath = self.opts['trivial_path'] + '/' + self.opts['trivial_db']
        self.conn = sqlite3.connect(self.dbpath)
        self.conn.text_factory = str
        self.cur = self.conn.cursor()

    def SelectOne(self, select, values=None):
        self.OpenDB()
        self.cur.execute(select, values)
        self.result = self.cur.fetchone()
        self.conn.close()

    def InsertOne(self, insert, values):
        self.OpenDB()
        self.cur.execute(insert, values)
        self.conn.commit()
        self.conn.close()

    def Check_Session_db(self):
        date_str = str(datetime.now().date())
        values = (date_str, self.server)
        self.SelectOne('select count(id), id from sessions where date=? and server=?', values)
        if self.result[0] < 1:
            self.InsertOne('insert into sessions (date, server) values (?,?)', values)
            self.SelectOne('select count(id), id from sessions where date=? and server=?', values)
        if self.result[0] > 0:
            return int(self.result[1])
        else:
            return False

    def Check_Nick_db(self, nick):
        values = (nick, self.server)
        self.SelectOne('select count(id), id from users where nick=? and server=?', values)
        if self.result[0] < 1:
            try:
                self.InsertOne('insert into users (nick, server) values (?,?)', values)
                self.SelectOne('select count(id), id from users where nick=? and server=?', values)
            except:
                weechat.prnt('', 'Error during insertion Nick on DB')
        if self.result[0] > 0:
            return int(self.result[1])
        else:
            return False

    def Register_Question(self, winner = False):
        id_session = self.Check_Session_db()
        id_question = self.qid
        datetime_str = str(datetime.now())
        points_won = self.opts['reward']
        if not winner:
            values = (datetime_str, id_session, id_question, points_won)
            insert = 'insert into session_questions (datetime, id_session, id_question, points_won) values (?,?,?,?)'
        else:
            id_user = self.Check_Nick_db(winner)
            insert = 'insert into session_questions (datetime, id_session, id_question, id_user, points_won) values (?,?,?,?,?)'
            values = (datetime_str, id_session, id_question, id_user, points_won)
            for x in values:
                weechat.prnt('', str(x))
        self.InsertOne(insert, values)

                    #==============#
                    # GAME METHODS #
                    #==============#

    def Main_Timer(self, interval=False, maxcalls=False):
        if not interval:
            interval = int(self.opts['time_interval'])
        if not maxcalls:
            maxcalls = 4
        try:
            ##                                                                              WWWW
            self.trivial['main_timer'] = weechat.hook_timer(interval * 1000, 0, maxcalls, 'Run_Game_cb', '')
        except:
            weechat.prnt('', 'Error loading main main_timer on Main_Timer')

    def Start_Game(self):
        weechat.prnt('', 'Trivial started')
        self.trivial['state'] = 0
        # set first question in 10 seconds
        self.Show_First_Header()
        interval = int(self.opts['header_time'])
        self.Main_Timer(interval,1)

    def Stop_Game(self):
        if self.trivial.has_key('main_timer'):
            weechat.unhook(self.trivial['main_timer'])
        self.running = False
        weechat.prnt('', 'Trivial stopped')

    def Fetch_Question(self):
        self.OpenDB()
        self.cur.execute('select q.question, q.answer, t.theme, q.id from questions q, themes t where q.id_theme = t.id order by random() limit 1')
        self.question, self.answer, self.theme, self.qid = self.cur.fetchone()
        self.conn.close()

    def Show_Question(self):
        theme = u'\x03' + '12 ' + self.theme + u'\x0f'
        question = u'\x02 ' + self.question + u'\x0f'
        answer = self.answer
        weechat.command(self.buffer_ptr, '%s : %s' %(theme, question))
        weechat.prnt('', 'Tema: %s - Pregunta: %s - Respuesta: %s' %(self.theme, self.question, self.answer))

    def Show_First_Header(self):
        weechat.command(self.buffer_ptr, 'El trivial comienza en %s segundos.' % self.opts['header_time'])

    def First_State(self):
        self.trivial['state'] = 1
        self.Fetch_Question()
        self.Show_Question()
        self.Show_Tips()
        self.Show_Rewards()

    def Second_State(self):
        self.trivial['state'] = 2
        self.Show_Tips()
        self.Show_Rewards()

    def Third_State(self):
        self.trivial['state'] = 3
        self.Show_Question()
        self.Show_Tips()
        self.Show_Rewards()

    def No_Winner(self):
        self.trivial['state'] = 0
        self.Show_Answer()
        self.Register_Question()
        self.Points_To_Pot()
        self.Main_Timer()

    def Winner(self, winner):
        self.trivial['state'] = 0
        if self.trivial['main_timer']:
            weechat.unhook(self.trivial['main_timer'])
        self.Show_Awards(winner)
        self.Register_Question(winner)
        self.Show_Session_Awards(winner)
        self.Show_Ranking()
        interval = int(self.opts['wait_time'])
        weechat.hook_timer(interval * 1000, 0, 1, 'Wait_Next_Round_cb', '')

    def Show_Answer(self):
        answer_str = u'\x03' + '12' + 'La respuesta era: ' + u'\x0f'
        answer = u'\x02' + self.answer + u'\x0f'
        weechat.command(self.buffer_ptr, '%s %s' %(answer_str, answer))

    def Show_Ranking(self):
        self.ranking = []
        id_session = self.Check_Session_db()
        self.OpenDB()
        select = '''select u.nick, sum(sq.points_won) as points from users u,
                    session_questions sq,
                    sessions s
                    where sq.id_user = u.id
                    and  sq.id_session = s.id
                    and s.server = (select server from sessions where id = ? )
                    group by sq.id_user
                    order by points
                    limit 10'''
        self.cur.execute(select, (id_session,))
        self.ranking = self.cur.fetchall()
        self.conn.close()
        weechat.prnt('', str(len(self.ranking)))
        count = 1
        self.Show_Ranking_Header()
        total_str = ''
        for nick_stat in self.ranking:
            number_str = u'\x03' + '8 ' + str(count) + ': ' + u'\x0f'
            nick_str = u'\x03' + '6' + nick_stat[0] + u'\x0f'
            points_str = u'\x03' '9' + ' (' + u'\x0f' + u'\x03' + '6 ' + str(nick_stat[1]) + u'\x0f' + u'\x03' '9' + ' )' + u'\x0f'
            total_str = total_str + number_str + nick_str + points_str
            count = count + 1
        weechat.command(self.buffer_ptr, total_str)

    def Show_Ranking_Header(self):
        pass

    def Show_Awards(self, winner):
        weechat.command(self.buffer_ptr, 'Puntos conseguidos por %s: %s' % (winner, self.opts['reward']))

    def Show_Session_Awards(self, winner):
        id_session = self.Check_Session_db()
        id_user = self.Check_Nick_db(winner)
        values = (id_session, id_user)
        self.OpenDB()
        select = 'select sum(points_won) from session_questions where id_session=? and id_user=?'
        self.SelectOne(select, values)
        points = self.result[0]
        self.conn.close()
        weechat.command(self.buffer_ptr, 'Puntos de hoy por %s: %s' % (winner, points))

    def Points_To_Pot(self):
        pass

    def Show_Tips(self):
        if self.trivial['state'] == 1:
            answer = ''
            for word in self.answer:
                if word != ' ':
                    answer = answer + '*'
                else:
                    answer = answer + ' '
        elif self.trivial['state'] == 2:
            answer = ''
            count = 0
            for word in self.answer:
                if count < 3:
                    answer = answer + word
                    count = count + 1
                else:
                    if word != ' ':
                        answer = answer + '*'
                    else:
                        answer = answer + ' '
        elif self.trivial['state'] == 3:
            answer = ''
            count = 0
            constraints = 'bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ'
            for word in self.answer:
                if count < 3:
                    answer = answer + word
                    count = count + 1
                else:
                    if word != ' ':
                        if word not in constraints:
                            answer = answer + word
                        else:
                            answer = answer + '*'
                    else:
                        answer = answer + ' '
        tip_msg = u'\x03' + '12' + 'Pista: ' + u'\x0f' + u'\x03' + '10' + '%s' % answer + '\x0f'
        weechat.command(self.buffer_ptr, tip_msg)

    def Show_Rewards(self):
        reward = int(self.opts['reward']) / self.trivial['state']
        reward_str = u'\x03' + '06' + str(reward) + u'\x0f'
        points_str = u'\x03' + '08' + 'Puntos: ' + u'\x0f'
        weechat.command(self.buffer_ptr, '%s %s' % (points_str, reward_str))

def Register(params):
    global OPTS
    OPTS = {}
    OPTS['params'] = {}
    OPTS['commands'] = {}
    for key, value in params.items():
        OPTS['params'][key] = value
    weechat.register(OPTS['params']['script_name'], OPTS['params']['author'],
                     OPTS['params']['version'], OPTS['params']['license'],
                     OPTS['params']['description'], OPTS['params']['shutdown_function'],
                     OPTS['params']['charset'])

def set_default_options(options):
    global OPTS
    OPTS['default_options'] = options
    OPTS['plugin_options'] = {}
    for option, default_value in OPTS['default_options'].items():
        if not weechat.config_is_set_plugin(option):
            weechat.config_set_plugin(option, default_value)

def load_options():
    global OPTS
    for option in OPTS['default_options'].keys():
        OPTS['plugin_options'][option] = weechat.config_get_plugin(option)

def free_options_cb():
    global OPTS
    OPTS['rc'] = {}
    for option in OPTS['default_options'].keys():
        OPTS['rc'][option] = weechat.config_unset_plugin(option)

    for option,value in OPTS['rc'].items():
        if value == weechat.WEECHAT_CONFIG_OPTION_UNSET_ERROR:
            return weechat.WEECHAT_RC_ERROR
    return weechat.WEECHAT_RC_OK

def reload_options_cb(data, option, value):
    global OPTS
    OPTS['plugin_options'][option] = value
    Reload_Trivial_Vars()
    return weechat.WEECHAT_RC_OK

def config_hook():
    global OPTS
    weechat.hook_config('plugins.var.python.' + OPTS['params']['script_name'] + '.*', 'reload_options_cb', '')

def AddCommand(params):
    global OPTS
    hook = weechat.hook_command(params['command'], params['description'],
                                params['args'], params['args_description'],
                                params['completion'], params['callback'],
                                params['callback_data'])
    OPTS['commands'][params['command']] = hook
    return weechat.WEECHAT_RC_OK

### Trivial functions
def my_trivial_cb(data, buffer, args):
    global MyTriv
    params = args.split(' ')
    if params[0] == 'start':
        MyTriv.Start_Game()
    elif params[0] == 'stop':
        MyTriv.Stop_Game()
    else:
        # do nothing
        weechat.prnt('', args[1])
    return weechat.WEECHAT_RC_OK

def Run_Game_cb(data, remaining_calls):
    global MyTriv
    MyTriv.running = True
    if MyTriv.trivial['state'] == 0:
        if int(remaining_calls) == 0:
            MyTriv.Main_Timer(False,3)
        MyTriv.First_State()
    elif MyTriv.trivial['state']== 1:
        MyTriv.Second_State()
    elif MyTriv.trivial['state'] == 2:
        MyTriv.Third_State()
    else:
        MyTriv.No_Winner()
    return weechat.WEECHAT_RC_OK

def Wait_Next_Round_cb(data, remaining_calls):
    global MyTriv
    MyTriv.Main_Timer()
    return weechat.WEECHAT_RC_OK

def Check_message_cb(data, buffer, date, tags, displayed, highlight, prefix, message):
    global MyTriv
    nick = MyTriv.Check_Nick(prefix)
    if MyTriv.running == True:
        if message.lower() == MyTriv.answer.lower():
            MyTriv.Winner(nick)
        elif message.lower() == '!trivial stop'.lower() and MyTriv.Is_Admin(nick):
            MyTriv.Stop_Game()
    else:
        if message.lower() == '!trivial start'.lower() and MyTriv.Is_Admin(nick):
            MyTriv.Start_Game()
    return weechat.WEECHAT_RC_OK

def Reload_Trivial_Vars():
    global MyTriv
    MyTriv.Load_Vars()
### End plugin functions


### Main procedure
def main():
    # Register script
    register_params = {
        'script_name'       : 'trivialbot',
        'author'            : 'nashgul <m.alcocer1978@gmail.com>',
        'version'           : '0.1',
        'license'           : 'beer-ware',
        'description'       : 'trivial bot',
        'shutdown_function' : 'free_options_cb',
        'charset'           : ''
        }
    Register(register_params)

    # Setting default options for script
    global options
    options = {
        'server'        : 'hispano',
        'room'          : '#dnb_&_jungle',
        'time_interval' : '20',
        'wait_time'     : '5',
        'header_time'   : '5',
        'trivial_path'  : '/home/manuel/.weechat_trivial/python',
        'trivial_db'    : 'trivialbot.db',
        'reward'        : '25000',
        'pot'           : '1',
        'admin_nicks'   : 'z0idberg',
        }
    set_default_options(options)

    # load actual plugin options
    load_options()
    config_hook()

    # create command
    main_command = {
        'command'           : 'trivial',
        'description'       : 'trivial bot for weechat',
        'args'              : '[start] | [stop]',
        'args_description'  : '',
        'completion'        : '',
        'callback'          : 'my_trivial_cb',
        'callback_data'     : ''
        }
    AddCommand(main_command)

    global MyTriv
    MyTriv = TrivialRoom()
    MyTriv.Start_Listener()

if __name__ == '__main__':
    main()
