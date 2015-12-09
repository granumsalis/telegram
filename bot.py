    #!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import telegram
import sys
from pyslack import SlackClient
import json
import argparse
import time
import timepad
import os
import traceback
import sqlite3
from datetime import datetime
from pony.orm import *

LAST_UPDATE_ID = None
MESSAGE = "Пока никаких новостей...\nЯ буду присылать анонсы сюда и в канал @GranumSalis."
MESSAGE_STOP = "Я умолкаю в этом чате! Может быть, за анонсами удобнее следить в канале @GranumSalis?.."
MESSAGE_HELP = "/hello - Greetings\n/help - show this message\n/stop - exclude self from notification list"
MESSAGE_ALARM = "Аларм! Аларм!"
CHAT_ID_ALARM = 79031498
SEND_BROAD_CMD = '/send_broad '
SEND_MSG_CMD = '/send'
STOP_CMD = '/stop'
SECRET_LIST_CMD = '/secret_list'
USER_LIST_CMD = '/user_list'
HELLO_CMD = '/hello'
HELP_CMD = '/help'
TELEGRAM_MSG_CHANNEL = '#telegram-messages'

db = Database('sqlite', 'granum_salis.sqlite', create_db=True)
class Chat(db.Entity):
    chat_id = Required(int, unique=True)
    user_id = Required(int)
    open_date = Required(datetime)
    last_message_date = Optional(datetime)
    username = Optional(str)
    first_name = Optional(str)
    last_name = Optional(str)
db.generate_mapping(create_tables=True)

def main():
    global LAST_UPDATE_ID

    parser = argparse.ArgumentParser(description="Telegram bot for GranumSalis")
    parser.add_argument("--logfile", type=str, default='log', help="Path to log file")
    args = parser.parse_args()

    with open('.admin_ids') as f:
        admin_ids = f.read().splitlines() 
    if admin_ids == None:
        admin_ids = list()

    # TODO: use it
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    telegram_token = open('.telegram_token').readline().strip()
    slack_token = open('.slack_token').readline().strip()
    bot = telegram.Bot(telegram_token)
    slackbot = SlackClient(slack_token)

    try:
        LAST_UPDATE_ID = bot.getUpdates()[-1].update_id
    except IndexError:
        LAST_UPDATE_ID = None

    while True:
        try:
            run(bot, admin_ids, args.logfile, slackbot)
        except telegram.TelegramError as error:
            print "TelegramError", error
            time.sleep(1)
        except Exception:
            traceback.print_exc()
            bot.sendMessage(chat_id=CHAT_ID_ALARM, text=MESSAGE_ALARM)
            time.sleep(100)


def log_update(update, logfile, slackbot):
    message = update.message
    slack_text = u'{} {} ({}): {{}}\n'.format(message.from_user.first_name,
                                                message.from_user.last_name,
                                                message.from_user.name)
    if message.left_chat_participant:
        slack_text = slack_text.format('jeft bot chat')
    elif message.new_chat_participant:
        slack_text = slack_text.format('joined bot chat')
    else:
        slack_text = slack_text.format(message.text)
    log_text = update.to_json().decode('unicode-escape').encode('utf-8') + '\n'
    chat_id = message.chat_id

    with open(logfile, 'a') as log:
        log.write(log_text)
    
    with db_session:
        chat = Chat.get(chat_id = chat_id)
        if message.text == STOP_CMD or message.left_chat_participant != None:
            chat.delete()
        else:
            if chat == None:
                chat = Chat(chat_id = chat_id, user_id = message.from_user.id, open_date = datetime.now(), \
                 last_message_date = datetime.now(), username = message.from_user.username, \
                 first_name = message.from_user.first_name, last_name = message.from_user.last_name)
            else:
                chat.last_message_date = datetime.now()
                chat.username = message.from_user.username
        commit()
    slackbot.chat_post_message(TELEGRAM_MSG_CHANNEL, slack_text, as_user=True)


def send_broad(bot, text):
    with db_session:
        for chat_id in select(chat.chat_id for chat in Chat):
            try:
                bot.sendMessage(chat_id=chat_id, text=text)
            except telegram.TelegramError:
                pass

def print_userlist(bot, message):
    with db_session:
        chats_str = ''
        for chat in select(chat for chat in Chat):
            try:
                chats_str += 'user: {0} user_id: {1}\n'.format(chat.username, chat.user_id)
            except telegram.TelegramError:
                pass
        bot.sendMessage(chat_id=message.chat_id, text = chats_str)

def send_message(bot, message):
    with db_session:
        cmd = text = ''
        user_id = 0
        params = message.text.split(' ',2)
        if len(params) > 0:
            cmd = params[0]
        if len(params) > 1:
            try:
                user_id = int(params[1])
            except ValueError:
                bot.sendMessage(chat_id=message.chat_id, text = 'cannot find user')
                return False
        if len(params) > 2:
            text = params[2]
        if user_id == 0:
            bot.sendMessage(chat_id=message.chat_id, text = 'cannot send message to empty user')
        elif len(text) == 0:
            bot.sendMessage(chat_id=message.chat_id, text = 'cannot send empty message')
        else:
            chat = Chat.get(user_id = user_id)
            if chat == None:
                bot.sendMessage(chat_id=message.chat_id, text = 'cannot find user')
            else:
                bot.sendMessage(chat_id=chat.chat_id, text = text)

def run(bot, admin_list, logfile, slackbot):
    global LAST_UPDATE_ID
    for update in bot.getUpdates(offset=LAST_UPDATE_ID, timeout=10):
        message = update.message
        # print message
        log_update(update, logfile, slackbot)
        is_admin = str(message.from_user.id) in admin_list
    
        if message.left_chat_participant:
            pass
        elif message.text == HELP_CMD:
            bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_HELP)
        elif message.text == HELLO_CMD:
            if message.from_user != None:
                username = message.from_user.first_name + ' ' + message.from_user.last_name
            else:
                username = 'anonymouse'
            bot.sendMessage(chat_id=message.chat_id, text="Hello " + username)
        elif message.text == STOP_CMD:
            bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_STOP)
        elif is_admin and message.text.startswith(SEND_BROAD_CMD):
            send_broad(bot, message.text[len(SEND_BROAD_CMD):])
        elif is_admin and message.text.startswith(SEND_MSG_CMD):
            send_message(bot, message)
        elif is_admin and message.text == SECRET_LIST_CMD:
            timepad_token = open('.timepad_token').readline().strip()
            timepad_list_filename = timepad.save_list_to_file(timepad_token)
            bot.sendDocument(chat_id=message.chat_id, document=open(timepad_list_filename, 'rb'))
            os.remove(timepad_list_filename)
        elif is_admin and message.text == USER_LIST_CMD:
            print_userlist(bot,message)
        elif is_admin and message.text != '':
            bot.sendMessage(chat_id=message.chat_id, text=MESSAGE)
        else:
            pass
            
        LAST_UPDATE_ID = update.update_id + 1

if __name__ == '__main__':
    main()
