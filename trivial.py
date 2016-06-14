#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import weechat
import sqlite3

import sys
reload(sys)
sys.setdefaultencoding('utf8')

from datetime import datetime

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

def load_options_cb():
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
    params = args.split(' ')
    if params[0] == 'start':
        Start_Game()
    elif params[0] == 'stop':
        Stop_Game()
    else:
        # do nothing
        weechat.prnt('', args[1])
    return weechat.WEECHAT_RC_OK

def Start_Game():
    global trivial, OPTS
    weechat.prnt('', 'Trivial started')
    trivial['state'] = 0
    # set first question in 10 seconds
    interval = int(OPTS['plugin_options']['header_time'])
    Main_Timer(interval,1)

def Stop_Game():
    global trivial
    if trivial.has_key('main_timer'):
        weechat.unhook(trivial['main_timer'])
    trivial['running'] = False
    weechat.prnt('', 'Trivial stopped')

def Main_Timer(interval=False, maxcalls=False):
    global trivial, OPTS
    if not interval:
        interval = int(OPTS['plugin_options']['time_interval'])
    if not maxcalls:
        maxcalls = 4
    trivial['main_timer'] = weechat.hook_timer(interval * 1000, 0, maxcalls, 'Run_Game_cb', '')

def Run_Game_cb(data, remaining_calls):
    global trivial
    trivial['running'] = True
    if trivial['state'] == 0:
        if int(remaining_calls) == 0:
            Main_Timer(False,3)
        First_State()
    elif trivial['state']== 1:
        Second_State()
    elif trivial['state'] == 2:
        Third_State()
    else:
        No_Winner()
    return weechat.WEECHAT_RC_OK

def First_State():
    global trivial
    trivial['state'] = 1
    Fetch_Question()
    Show_Question()
    Show_Rewards()
    Show_Tips()

def Second_State():
    global trivial
    trivial['state'] = 2
    Show_Question()
    Show_Rewards()
    Show_Tips()

def Third_State():
    global trivial
    trivial['state'] = 3
    Show_Question()
    Show_Rewards()
    Show_Tips()

def No_Winner():
    global trivial, OPTS
    trivial['state'] = 0
    trivial['reward'] = OPTS['plugin_options']['reward']
    weechat.command(trivial['buffer_ptr'], 'no hubo aciertos')
    Register_Question()
    Points_To_Pot()
    Main_Timer()

def Winner(winner):
    global trivial, OPTS
    trivial['state'] = 0
    if trivial['main_timer']:
        weechat.unhook(trivial['main_timer'])
    Show_Awards(winner)
    Register_Question(winner)
    Show_Session_Awards(winner)
    interval = int(OPTS['plugin_options']['wait_time'])
    weechat.hook_timer(interval * 1000, 0, 1, 'Wait_Next_Round_cb', '')

def Wait_Next_Round_cb(data, remaining_calls):
    global trivial
    Main_Timer()
    return weechat.WEECHAT_RC_OK

def Show_Awards(winner):
    global trivial
    weechat.command(trivial['buffer_ptr'], 'Puntos conseguidos por %s: %d' % (winner, trivial['reward']))


def Show_Session_Awards(winner):
    global trivial, OPTS
    id_session = Check_Session_db()
    id_user = Check_Nick_db(winner)
    conn = sqlite3.connect(OPTS['plugin_options']['trivial_path'] + '/' + OPTS['plugin_options']['trivial_db'])
    conn.text_factory = str
    c = conn.cursor()
    c.execute('select sum(points_won) from session_questions where id_session=? and id_user=?', (id_session, id_user))
    points = str(c.fetchone()[0])
    conn.close()
    weechat.command(trivial['buffer_ptr'], 'Puntos de hoy por %s: %s' % (winner, points))


def Register_Question(winner = False):
    global trivial, OPTS
    id_session = Check_Session_db()
    if id_session:
        id_question = trivial['question'][-1]
        datetime_str = str(datetime.now())
        points_won = trivial['reward']
        if not winner:
            conn = sqlite3.connect(OPTS['plugin_options']['trivial_path'] + '/' + OPTS['plugin_options']['trivial_db'])
            conn.text_factory = str
            c = conn.cursor()
            c.execute('insert into session_questions (datetime, id_session, id_question, points_won) values (?,?,?,?)', (datetime_str, id_session, id_question, points_won))
            conn.commit()
            conn.close()
        else:
            id_user = Check_Nick_db(winner)
            if id_user:
                conn = sqlite3.connect(OPTS['plugin_options']['trivial_path'] + '/' + OPTS['plugin_options']['trivial_db'])
                conn.text_factory = str
                c = conn.cursor()
                c.execute('insert into session_questions (datetime, id_session, id_question, id_user, points_won) values (?,?,?,?,?)', (datetime_str, id_session, id_question, id_user, points_won))
                conn.commit()
                conn.close()
            else:
                # if error do nothing
                pass
    else:
        # if error do nothing
        pass

def Check_Nick_db(nick):
    global trivial, OPTS
    server = OPTS['plugin_options']['server']
    conn = sqlite3.connect(OPTS['plugin_options']['trivial_path'] + '/' + OPTS['plugin_options']['trivial_db'])
    conn.text_factory = str
    c = conn.cursor()
    c.execute('select count(id), id from users where nick=? and server=?', (nick, server))
    result = c.fetchone()
    if result[0] < 1:
        c.execute('insert into users (nick, server) values (?,?)', (nick, server))
        conn.commit()
        c.execute('select count(id), id from users where nick=? and server=?', (nick, server))
        result = c.fetchone()
    conn.close()
    if result[0] > 0:
        return int(result[1])
    else:
        return False

def Check_Session_db():
    global OPTS
    server = OPTS['plugin_options']['server']
    date_str = str(datetime.now().date())
    conn = sqlite3.connect(OPTS['plugin_options']['trivial_path'] + '/' + OPTS['plugin_options']['trivial_db'])
    conn.text_factory = str
    c = conn.cursor()
    c.execute('select count(id), id from sessions where date=? and server=?', (date_str, server))
    result = c.fetchone()
    if result[0] < 1:
        c.execute('insert into sessions (date, server) values (?,?)', (date_str, server))
        conn.commit()
        c.execute('select count(id), id from sessions where date=? and server=?', (date_str, server))
        result = c.fetchone()
    conn.close()
    if result[0] > 0:
        return int(result[1])
    else:
        return False


def Show_Question():
    global trivial
    theme = u'\x03' + '12' + trivial['question'][2] + u'\x0f'
    question = u'\x02' + trivial['question'][0] + u'\x0f'
    weechat.command(trivial['buffer_ptr'], '%s : %s' %(theme, question))

def Show_Tips():
    global trivial
    if trivial['state'] == 1:
        answer = ''
        for word in trivial['question'][1]:
            if word != ' ':
                answer = answer + '*'
            else:
                answer = answer + ' '
    elif trivial['state'] == 2:
        answer = ''
        count = 0
        for word in trivial['question'][1]:
            if count < 3:
                answer = answer + word
                count = count + 1
            else:
                if word != ' ':
                    answer = answer + '*'
                else:
                    answer = answer + ' '
    elif trivial['state'] == 3:
        answer = ''
        count = 0
        constraints = 'bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ'
        for word in trivial['question'][1]:
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
    weechat.command(trivial['buffer_ptr'], u'\x03' + '12' + 'Pista: ' + u'\x0f' + u'\x03' + '10' + '%s' % answer + '\x0f')

def Show_Rewards():
    global trivial, OPTS
    trivial['reward'] = int(OPTS['plugin_options']['reward']) / trivial['state']
    reward = u'\x03' + '06' + str(trivial['reward']) + u'\x0f'
    points = u'\x03' + '08' + 'Puntos: ' + u'\x0f'
    weechat.command(trivial['buffer_ptr'], '%s %s' % (points, reward))

def Points_To_Pot():
    pass

def Fetch_Question():
    global trivial, OPTS
    conn = sqlite3.connect(OPTS['plugin_options']['trivial_path'] + '/' + OPTS['plugin_options']['trivial_db'])
    conn.text_factory = str
    c = conn.cursor()
    c.execute('select q.question, q.answer, t.theme, q.id from questions q, themes t where q.id_theme = t.id order by random() limit 1')
    trivial['question'] = c.fetchone()
    conn.close

def Load_Game():
    global trivial
    trivial['buffer_ptr'] = weechat.buffer_search('irc','%s.%s' %(weechat.config_get_plugin('server'), weechat.config_get_plugin('room')))
    if not trivial.has_key('running'):
        trivial['running'] = False

def Start_Listener():
    global trivial
    trivial['listener_hook'] = weechat.hook_print(trivial['buffer_ptr'], 'irc_privmsg', '', 1, 'Check_message_cb', '')

def Stop_Listener():
    global trivial
    weechat.unhook(trivial['listener_hook'])

def Check_message_cb(data, buffer, date, tags, displayed, highlight, prefix, message):
    global trivial
    nick = Check_Nick(prefix)
    if trivial['running'] == True:
        if message.lower() == trivial['question'][1].lower():
            Winner(nick)
        elif message.lower() == '!trivial stop'.lower() and Is_Admin(nick):
            Stop_Game()
    else:
        if message.lower() == '!trivial start'.lower() and Is_Admin(nick):
            Start_Game()
    return weechat.WEECHAT_RC_OK

def Check_Nick(prefix):
    global trivial
    if weechat.nicklist_search_nick(trivial['buffer_ptr'], '', prefix):
        return prefix
    else:
        wildcards = '+@'
        if prefix[0] in wildcards:
            if weechat.nicklist_search_nick(trivial['buffer_ptr'], '', prefix[1:]):
                return prefix[1:]

def Is_Admin(nick):
    global OPTS
    nicklist = OPTS['plugin_options']['admin_nicks'].split(',')
    nicklist = [nick_ad.strip(' ') for nick_ad in nicklist]
    if nick in nicklist:
        return True
    else:
        return False

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
    options = {
        'server'        : 'hispano',
        'room'          : '#dnb_&_jungle',
        'time_interval' : '20',
        'wait_time'     : '5',
        'header_time'   : '10',
        'trivial_path'  : '/home/manuel/.weechat_trivial/python',
        'trivial_db'    : 'trivialbot.db',
        'reward'        : '25000',
        'pot'           : '1',
        'admin_nicks'   : 'z0idberg'
        }
    set_default_options(options)

    # load actual plugin options
    load_options_cb()
    config_hook()

    # create command
    global trivial
    trivial = {}
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
    Load_Game()
    Start_Listener()

if __name__ == '__main__':
    main()
