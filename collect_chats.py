#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json

log = open('log')

chats = []
for line in log:
    try:
        s = json.loads(line.rstrip())
        chat = s['message']['chat']['id']
        if not chat in chats:
            chats.append(chat)
    except:
        pass

with open('chats', 'w') as chatsfile:
    json.dump(chats, chatsfile, indent=4)
