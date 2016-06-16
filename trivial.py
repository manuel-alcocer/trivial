#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import weechat
import sqlite3

import sys
reload(sys)
sys.setdefaultencoding('utf8')

from datetime import datetime

global TRIV, colors
TRIV = {}
TRIV['commands'] = {}
TRIV['rc'] = {}
TRIV['instances'] = { 'ids' : 'schranz,dnbjungle' }
TRIV['instances']['launched'] = {}
TRIV['default_instance_options'] = {
    'time_interval' : '20',
    'wait_time'     : '5',
    'header_time'   : '5',
    'trivial_path'  : '/home/manuel/.weechat/python',
    'trivial_db'    : 'trivialbot.db',
    'reward'        : '25000',
    'pot'           : '1',
    'admin_nicks'   : 'z0idberg',
    'cmd_prefix'    : '#',
    'room'          : '',
    'server'        : 'hispano'
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

COLORS = {
'WHITE' : '00', 'BLACK' : '01', 'DARKBLUE' : '02', 'DARKGREEN' : '03',
'LIGHTRED' : '04', 'DARKRED' : '05', 'MAGENTA' : '06', 'ORANGE' : '07',
'YELLOW' : '08', 'LIGHTGREEN' : '09', 'CYAN' : '10', 'LIGHTCYAN' : '11',
'LIGHTBLUE' : '12', 'LIGHTMAGENTA' : '13', 'GRAY' : '14', 'LIGHTGRAY' : '15'
}
for color in COLORS.keys():
    COLORS[color] = u'\x03' + COLORS[color]


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
        self.buffer_ptr = weechat.buffer_search('irc','%s.%s' %(self.opts['server'], self.opts['room']))

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
                    where date = ?
                    and server = ?
                    and room = ?'''
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
        select = '''select count(id), id
                    from users
                    where nick = ?
                    and server = ?'''
        self.SelectOne(select, values)
        if self.result[0] < 1:
            try:
                self.InsertOne('insert into users (nick, server) values (?,?)', values)
                self.SelectOne(select, values)
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
            insert = '''insert into session_questions (datetime, id_session, id_question, points_won)
                        values (?,?,?,?)'''
        else:
            id_user = self.Check_Nick_db(winner)
            insert = '''insert into session_questions (datetime, id_session, id_question, id_user, points_won)
                        values (?,?,?,?,?)'''
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

#=============#
# GAME STATES #
#==============

    def First_State(self):
        self.trivial['state'] = 1
        self.Fetch_Question()
        self.Show_Question()
        self.Show_Tips()
        #self.Show_Rewards()

    def Second_State(self):
        self.trivial['state'] = 2
        self.Show_Tips()
        #self.Show_Rewards()

    def Third_State(self):
        self.trivial['state'] = 3
        self.Show_Question()
        self.Show_Tips()
        #self.Show_Rewards()

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
        self.Show_Answer()
        self.Register_Question(winner)
        self.Show_Session_Awards(winner)
        self.Show_Ranking()
        interval = int(self.opts['wait_time'])
        weechat.hook_timer(interval * 1000, 0, 1, 'Wait_Next_Round_cb', self.TrivId)

#==================#
# QUESTION IN GAME #
#==================#

    def Fetch_Question(self):
        self.OpenDB()
        select = '''select q.question, q.answer, t.theme, q.id
                    from questions q, themes t
                    where q.id_theme = t.id
                    order by random()
                    limit 1'''
        self.cur.execute(select)
        self.question, self.answer, self.theme, self.qid = self.cur.fetchone()
        self.conn.close()

#=========#
# BANNERS #
#=========#

    def GiveColor(self, string, color):
        colors = {
        'white' : '00', 'black' : '01', 'darkblue' : '02', 'darkgreen' : '03',
        'lightred' : '04', 'darkred' : '05', 'magenta' : '06', 'orange' : '07',
        'yellow' : '08', 'lightgreen' : '09', 'cyan' : '10', 'lightcyan' : '11',
        'lightblue' : '12', 'lightmagenta' : '13', 'gray' : '14', 'lightgray' : '15'
        }
        string_str = u'\x03' + colors[color] + string + u'\x0f'
        return string_str

    def Show_Question(self):
        question = u'\x02 ' + self.question
        answer = self.answer
        string = '%s[ %spreg No.%s %s] %s<< %sTema: %s %s>> %sPregunta: %s' %(COLORS['LIGHTGREEN'],
                                                                              COLORS['LIGHTRED'], str(self.qid),
                                                                              COLORS['LIGHTGREEN'],
                                                                              COLORS['YELLOW'],
                                                                              COLORS['LIGHTBLUE'], self.theme,
                                                                              COLORS['YELLOW'],
                                                                              COLORS['LIGHTBLUE'], question) + u'\x0f'
        weechat.command(self.buffer_ptr, string)
        weechat.prnt('', 'Tema: %s - Pregunta: %s - Respuesta: %s' %(self.theme, self.question, self.answer))

    def Show_First_Header(self):
        weechat.command(self.buffer_ptr, 'El trivial comienza en %s segundos.' % self.opts['header_time'])

    def Show_Answer(self):
        string = '%sLa respuesta era: %s%s' %(COLORS['LIGHTBLUE'],
                                              COLORS['YELLOW'], self.answer)  + u'\x0f'
        weechat.command(self.buffer_ptr, string)

    def Show_Ranking(self):
        self.ranking = []
        id_session = self.Check_Session_db()
        self.OpenDB()
        select = '''select u.nick, sum(sq.points_won) as points
                    from users u, session_questions sq, sessions s
                    where sq.id_user = u.id
                    and sq.id_session = s.id
                    and s.server = (
                                    select server
                                    from sessions
                                    where id = ?
                                    )
                    group by sq.id_user
                    order by points desc
                    limit 10'''
        self.cur.execute(select, (id_session,))
        self.ranking = self.cur.fetchall()
        self.conn.close()
        count = 1
        self.Show_Ranking_Header()
        string = ''
        for nick_stat in self.ranking:
            number_str = '%s[%s%s%s]:' %(COLORS['LIGHTGREEN'],
                                         COLORS['YELLOW'], str(count),
                                         COLORS['LIGHTGREEN']) + u'\x0f'
            nick_str = '%s%s' %(COLORS['LIGHTBLUE'], nick_stat[0]) + '\x0f'
            points_str = ' %s(%s%s%s)  ' %(COLORS['LIGHTRED'],
                                           COLORS['LIGHTBLUE'], str(nick_stat[1]),
                                           COLORS['LIGHTRED']) + u'\x0f'
            string = string + number_str + nick_str + points_str
            count = count + 1
        weechat.command(self.buffer_ptr, string)

    def Show_Ranking_Header(self):
        pass

    def Show_Awards(self, winner):
        string = '%s¡¡¡Enhorabuena!!! %s %s¡¡¡Acertó!!!' %(COLORS['LIGHTRED'],
                                                           COLORS['LIGHTGREEN'], COLORS['LIGHTRED']) + u'\x0f'
        weechat.command(self.buffer_ptr, string)
        string = '%sPuntos conseguidos: %s%s' %(COLORS['YELLOW'],
                                                COLORS['LIGHTBLUE'], str(self.trivial['reward'])) + u'\x0f'
        weechat.command(self.buffer_ptr, string)

    def Show_Session_Awards(self, winner):
        id_session = self.Check_Session_db()
        id_user = self.Check_Nick_db(winner)
        values = (id_session, id_user)
        self.OpenDB()
        select = '''select sum(points_won)
                    from session_questions
                    where id_session = ?
                    and id_user = ?'''
        self.SelectOne(select, values)
        points = self.result[0]
        self.conn.close()
        string = '%s-->>%s%s %sha conseguido hoy: %s%s %spuntos %s<<--' %(COLORS['YELLOW'],
                                                                        COLORS['LIGHTBLUE'], winner,
                                                                        COLORS['LIGHTRED'],
                                                                        COLORS['LIGHTBLUE'], str(points),
                                                                        COLORS['LIGHTRED'],
                                                                        COLORS['YELLOW']) + u'\x0f' + u'\x0f'
        weechat.command(self.buffer_ptr, string)

    def Show_Tips(self):
        state = str(self.trivial['state'])
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
        self.trivial['reward'] = int(self.opts['reward']) / self.trivial['state']
        string = '%s%sª pista: %s%s %s<<-- %s%s' %(COLORS['LIGHTBLUE'], state,
                                                   COLORS['LIGHTGREEN'], answer,
                                                   COLORS['LIGHTRED'],
                                                   COLORS['YELLOW'], self.trivial['reward']) + u'\x0f'
        weechat.command(self.buffer_ptr, string)

#=======================#
# (TODO) POT MANAGEMENT #
#=======================#

    def Points_To_Pot(self):
        pass

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

### CRITICAL CONF CHANGED
def Stop_All_Instances():
    for instance in TRIV['instances']['launched'].keys():
        TRIV['instances']['launched'][instance].Stop_Game()

def Free_All_Options():
    free_options_cb(False)

def Relaunch_Instances():
    LaunchInstances()
### END CRITICAL CONF CHANGED
### END OPTIONS

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

### MAIN CONFIG MENU
def Main_Config_Menu():
    TRIV['conf_buffer'] = weechat.buffer_new('trivial', 'buffer_conf_cb', '',
                            'close_callback_cb', '')
    weechat.prnt('', str(TRIV['conf_buffer']))

def buffer_conf_cb():
    pass
    return weechat.WEECHAT_RC_OK

def close_callback_cb():
    pass
    return weechat.WEECHAT_RC_OK
### END MAIN CONFIG MENU

### TRIVIAL CALLBACK FUNCTIONS
def my_trivial_cb(data, buffer, args):
    params = args.split(' ')
    if len(params) == 2:
        if params[0].lower() == 'start':
            TRIV['instances']['launched'][params[1]].Start_Game()
        elif params[0].lower() == 'stop':
            TRIV['instances']['launched'][params[1]].Stop_Game()
        else:
            # do nothing
            pass
    elif params[0].lower() == 'config':
        Main_Config_Menu()
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
        elif message.lower() == cmd_prefix + 'trivial stop' and TRIV['instances']['launched'][data].Is_Admin(nick):
            TRIV['instances']['launched'][data].Stop_Game()
    else:
        if message.lower() == cmd_prefix + 'trivial start' and TRIV['instances']['launched'][data].Is_Admin(nick):
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
