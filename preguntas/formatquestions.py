#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from os import listdir
from os.path import isfile, join
import sqlite3

mypath = '.'
onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
conn = sqlite3.connect('trivial.db')
conn.text_factory = str
c = conn.cursor()
count = 0
for onlyfile in onlyfiles:
    if onlyfile[-3:] == 'txt':
        data = None
        with open(onlyfile, 'r') as of:
            data = of.readlines()
        for line in data:
            print line
            if len(line) > 4:
                theme = line[:-1].split('©')[0]
                question = line[:-1].split('«')[1].split('*')[0]
                answer = line[:-1].split('*')[-1]
                try:
                    c.execute('SELECT id FROM themes WHERE theme=?', (theme,))
                    idtheme = c.fetchone()[0]
                except:
                    idtheme = False
                if idtheme == False:
                    c.execute('insert into themes (theme) values (?)', (theme,))
                    c.execute('SELECT id FROM themes WHERE theme=?', (theme,))
                    idtheme = c.fetchone()[0]
                try:
                    c.execute('insert into questions (question,answer,id_theme) values (?,?,?)', (question,answer,idtheme))
                    count = count + 1
                except:
                    pass
conn.commit()
conn.close()
print count
