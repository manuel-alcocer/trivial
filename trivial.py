#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import weechat
import sqlite3

import sys
reload(sys)
sys.setdefaultencoding('utf8')

from datetime import datetime

global TRIV
TRIV = {}
TRIV['commands'] = {}
TRIV['rc'] = {}
TRIV['instances'] = { 'ids' : 'schranz,dnbjungle' }
TRIV['instances']['launched'] = {}
TRIV['default_instance_options'] = {
    'time_interval' : '20',
    'wait_time'     : '5',
    'header_time'   : '5',
    'trivial_path'  : '/home/manuel/.weechat_trivial/python',
    'trivial_db'    : 'trivialbot.db',
    'reward'        : '25000',
    'pot'           : '1',
    'admin_nicks'   : 'z0idberg',
    'cmd_prefix'    : '#',
    'room'          : '',
    'server'        : ''
    }

# Register script
TRIV['register'] = {
    'script_name'       : 'trivial',
    'author'            : 'nashgul <m.alcocer1978@gmail.com>',
    'version'           : '0.1',
    'license'           : 'beer-ware',
    'description'       : 'trivial game for weechat',
    'shutdown_function' : 'free_options_cb',
    'charset'           : ''
    }

# create command
TRIV['commands']['main'] = {
    'command'           : 'trivial',
    'description'       : 'trivial bot for weechat',
    'args'              : '[start] | [stop]',
    'args_description'  : '',
    'completion'        : '',
    'callback'          : 'my_trivial_cb',
    'callback_data'     : ''
    }

class Trivial:
#==================#
# OPTIONS SETTINGS #
#==================#

    def __init__(self, instance):
        self.TrivId = instance
        self.running = False
        self.trivial = {}
        self.opts = {}
        self.Load_Vars()

    def Load_Vars(self):
        for option in TRIV['default_instance_options'].keys():
            self.opts[option] = self.MyOpt('instance.' + self.TrivId + '.' + option)
            self.Depurar(option + ' - ' + self.opts[option])
        self.buffer_ptr = weechat.buffer_search('irc','%s.%s' %(self.opts['server'], self.opts['room']))
        self.Depurar(str(self.buffer_ptr))


    def MyOpt(self, option):
        value = weechat.config_get_plugin(option)
        return value

    def Depurar(self, value):
        weechat.prnt('',str(value))

#==================#
# LISTENER METHODS #
#==================#

    def Start_Listener(self):
        self.listener_hook = weechat.hook_print(self.buffer_ptr, 'irc_privmsg', '', 1, 'Check_message_cb', self.TrivId)

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
        nicklist = self.opts['admin_nicks'].split(',')
        nicklist = [ nick_ad.strip(' ') for nick_ad in nicklist ]
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
        values = (date_str, self.opts['server'], self.opts['room'])
        select = '''select count(id), id
                    from sessions
                    where date=?
                    and server=?
                    and room=?'''
        self.SelectOne(select, values)
        if self.result[0] < 1:
            self.InsertOne('insert into sessions (date, server, room) values (?,?,?)', values)
            self.SelectOne(select, values)
        if self.result[0] > 0:
            return int(self.result[1])
        else:
            return False

    def Check_Nick_db(self, nick):
        values = (nick, self.opts['server'])
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
        points_won = self.trivial['reward']
        if not winner:
            values = (datetime_str, id_session, id_question, points_won)
            insert = 'insert into session_questions (datetime, id_session, id_question, points_won) values (?,?,?,?)'
        else:
            id_user = self.Check_Nick_db(winner)
            insert = 'insert into session_questions (datetime, id_session, id_question, id_user, points_won) values (?,?,?,?,?)'
            values = (datetime_str, id_session, id_question, id_user, points_won)
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
            self.trivial['main_timer'] = weechat.hook_timer(interval * 1000, 0, maxcalls, 'Run_Game_cb', self.TrivId)
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
        weechat.command(self.buffer_ptr, 'Trivial stopped')

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
        weechat.hook_timer(interval * 1000, 0, 1, 'Wait_Next_Round_cb', self.TrivId)

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
                    order by points desc
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
        weechat.command(self.buffer_ptr, 'Puntos conseguidos por %s: %s' % (winner, self.trivial['reward']))

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
        self.trivial['reward'] = int(self.opts['reward']) / self.trivial['state']
        reward_str = u'\x03' + '06' + str(self.trivial['reward']) + u'\x0f'
        points_str = u'\x03' + '08' + 'Puntos: ' + u'\x0f'
        weechat.command(self.buffer_ptr, '%s %s' % (points_str, reward_str))

### REGISTER SCRIPT
def Register():
    weechat.register(TRIV['register']['script_name'],
                     TRIV['register']['author'],
                     TRIV['register']['version'],
                     TRIV['register']['license'],
                     TRIV['register']['description'],
                     TRIV['register']['shutdown_function'],
                     TRIV['register']['charset'])
### END REGISTER SCRIPT

### REGISTER MAIN COMMAND
def AddCommand():
    TRIV['commands']['main']['hook'] = weechat.hook_command(TRIV['commands']['main']['command'],
                                        TRIV['commands']['main']['description'],
                                        TRIV['commands']['main']['args'],
                                        TRIV['commands']['main']['args_description'],
                                        TRIV['commands']['main']['completion'],
                                        TRIV['commands']['main']['callback'],
                                        TRIV['commands']['main']['callback_data'])
    return weechat.WEECHAT_RC_OK
### END MAIN COMMAND

### SCRIPT OPTIONS
def set_default_options():
    if not weechat.config_is_set_plugin('ids'):
        weechat.config_set_plugin('ids', TRIV['instances']['ids'])

def Set_Instance_Options(instance):
    for option, value in TRIV['default_instance_options'].items():
        if not weechat.config_is_set_plugin(instance + '.' + option):
            weechat.config_set_plugin('instance.' + instance + '.' + option, value)

def free_options_cb(all_conf=True):
    weechat.unhook_all()
    for instance in TRIV['instances']['launched'].keys():
        for option in TRIV['default_instance_options'].keys():
            TRIV['rc']['instance.' + instance + '.' + option] = weechat.config_unset_plugin('instance.' + instance + '.' + option)
    if all_conf:
        TRIV['rc']['instances'] = weechat.config_unset_plugin('ids')
    for option,value in TRIV['rc'].items():
        if value == weechat.WEECHAT_CONFIG_OPTION_UNSET_ERROR:
            return weechat.WEECHAT_RC_ERROR
    return weechat.WEECHAT_RC_OK

def reload_options_cb(data, option, value):
    option_chgd = option.split('.')[-1]
    if option_chgd != 'ids':
        instance = option.split('.')[-2]
        TRIV['instances']['launched'][instance].Load_Vars()
    else:
        # CRITICAL CHANGE
        Stop_All_Instances()
        Free_All_Options()
        Relaunch_Instances()
    return weechat.WEECHAT_RC_OK

def config_hook():
    weechat.hook_config('plugins.var.python.' + TRIV['register']['script_name'] + '.*', 'reload_options_cb', '')
### END OPTIONS

### CRITICAL CONF CHANGED
def Stop_All_Instances():
    for instance in TRIV['instances']['launched'].keys():
        TRIV['instances']['launched'][instance].Stop_Game()

def Free_All_Options():
    free_options_cb(False)

def Relaunch_Instances():
    LaunchInstances()
### END CRITICAL CONF CHANGED

### LAUNCH INSTANCES
def LaunchInstances():
    instances = weechat.config_get_plugin('ids')
    instances = instances.split(',')
    instances = [ instance.strip(' ') for instance in instances ]
    for instance in instances:
        Set_Instance_Options(instance)
        TRIV['instances']['launched'][instance] = Trivial(instance)
        TRIV['instances']['launched'][instance].Start_Listener()
    AddCommand()
    TRIV['config_hook'] = config_hook()
### END INSTANCES

### TRIVIAL CALLBACK FUNCTIONS
def my_trivial_cb(data, buffer, args):
    params = args.split(' ')
    if len(params) == 2:
        if params[0] == 'start':
            TRIV['instances']['launched'][params[1]].Start_Game()
        elif params[0] == 'stop':
            TRIV['instances']['launched'][params[1]].Stop_Game()
        else:
            # do nothing
            weechat.prnt('', str(params))
    return weechat.WEECHAT_RC_OK

def Run_Game_cb(data, remaining_calls):
    TRIV['instances']['launched'][data].running = True
    if TRIV['instances']['launched'][data].trivial['state'] == 0:
        if int(remaining_calls) == 0:
            TRIV['instances']['launched'][data].Main_Timer(False,3)
        TRIV['instances']['launched'][data].First_State()
    elif TRIV['instances']['launched'][data].trivial['state']== 1:
        TRIV['instances']['launched'][data].Second_State()
    elif TRIV['instances']['launched'][data].trivial['state'] == 2:
        TRIV['instances']['launched'][data].Third_State()
    else:
        TRIV['instances']['launched'][data].No_Winner()
    return weechat.WEECHAT_RC_OK

def Wait_Next_Round_cb(data, remaining_calls):
    TRIV['instances']['launched'][data].Main_Timer()
    return weechat.WEECHAT_RC_OK

def Check_message_cb(data, buffer, date, tags, displayed, highlight, prefix, message):
    nick = TRIV['instances']['launched'][data].Check_Nick(prefix)
    cmd_prefix = TRIV['instances']['launched'][data].opts['cmd_prefix']
    if TRIV['instances']['launched'][data].running == True and TRIV['instances']['launched'][data].trivial['state'] != 0:
        if message.lower() == TRIV['instances']['launched'][data].answer.lower():
            TRIV['instances']['launched'][data].Winner(nick)
        elif message.lower() == cmd_prefix + 'trivial stop'.lower() and TRIV['instances']['launched'][data].Is_Admin(nick):
            TRIV['instances']['launched'][data].Stop_Game()
    else:
        if message.lower() == cmd_prefix + 'trivial start'.lower() and TRIV['instances']['launched'][data].Is_Admin(nick):
            TRIV['instances']['launched'][data].Start_Game()
    return weechat.WEECHAT_RC_OK
### END CALLBACK FUNCTIONS

### MAIN PROCEDURE
def main():
    Register()
    set_default_options()
    LaunchInstances()

if __name__ == '__main__':
    main()
