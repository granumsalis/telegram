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
import urllib2
import itertools
from datetime import datetime
from pony.orm import db_session, select
from db import granumDB, Chat


LAST_UPDATE_ID = None
MESSAGE_START = "Вы подписаны на рассылку новостей.\nЯ буду присылать анонсы сюда и в канал @GranumSalis. Наберите /stop, чтобы остановить рассылку."
MESSAGE_STOP = "Я умолкаю в этом чате! Наберите /start, чтобы вновь подписаться на рассылку анонсов. Может быть, за анонсами удобнее следить в канале @GranumSalis?.."
MESSAGE_HELP = "/flood - ссылка на флуд-чат\n/help - показать это сообщение\n/next - ближайшее мероприятие\n/start - подписаться на рассылку анонсов\n/stop - остановить рассылку анонсов\n/timing - расписание ближайшего мероприятия"
KEYBOARD = '{"keyboard" : [["/start", "/flood"], ["/next", "/timing", "/help"]], "resize_keyboard" : true}'
KEYBOARD_ADMIN = '{"keyboard" : [["/start", "/flood"], ["/next", "/timing", "/help"], ["/user_list", "/secret_list"]], "resize_keyboard" : true}'
MESSAGE_HELP_ADMIN = MESSAGE_HELP + "\n/user_list - list of subscribers\n/secret_list - get participants list for next event\n/send_broad <message> - send message to all users\n/send <user_id> <message> - send <message> to <user_id>"
MESSAGE_ALARM = "Аларм! Аларм!"
CHAT_ID_ALARM = 79031498
BOT_ID = 136777319
FLOOD_CHAT_LINK = 'Чат для щепоточного флуда: https://telegram.me/joinchat/BLXsyghalbG00BT_9U3viA'
SEND_BROAD_CMD = '/send_broad'
SEND_MSG_CMD = '/send'
START_CMD = '/start'
STOP_CMD = '/stop'
SECRET_LIST_CMD = '/secret_list'
USER_LIST_CMD = '/user_list'
HELLO_CMD = '/hello'
HELP_CMD = '/help'
NEXT_CMD = '/next'
FLOOD_CMD = '/flood'
TIMING_CMD = '/timing'
TELEGRAM_MSG_CHANNEL = '#telegram-messages'


def main():
    global LAST_UPDATE_ID

    parser = argparse.ArgumentParser(description="Telegram bot for GranumSalis")
    parser.add_argument("--logfile", type=str, default='log', help="Path to log file")
    parser.add_argument("--dbfile", type=str, default='granumsalis.sqlite', help="Path to sqlite DB file")
    args = parser.parse_args()

    granumDB.bind('sqlite', args.dbfile, create_db=True)
    granumDB.generate_mapping(create_tables=True)

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
        except urllib2.URLError as error:
            print "URLError", error
            time.sleep(1)
        except:
            traceback.print_exc()
            try:
                bot.sendMessage(chat_id=CHAT_ID_ALARM, text=MESSAGE_ALARM)
            except:
                pass
            time.sleep(100) # 100 seconds


def log_update(update, logfile, slackbot, primary_id):
    message = update.message
    slack_text = u'{} {} ({}, GSid: {}): {{}}\n'.format(message.from_user.first_name,
                                                        message.from_user.last_name,
                                                        message.from_user.name,
                                                        primary_id)
    if message.left_chat_participant:
        slack_text = slack_text.format('jeft bot chat')
    elif message.new_chat_participant:
        slack_text = slack_text.format('joined bot chat')
    else:
        slack_text = slack_text.format(message.text)
    log_text = update.to_json().decode('unicode-escape').encode('utf-8') + '\n'

    slackbot.chat_post_message(TELEGRAM_MSG_CHANNEL, slack_text, as_user=True)
    with open(logfile, 'a') as log:
        log.write(log_text)


def update_chat_db(message):
    with db_session:
        chat = Chat.get(chat_id=message.chat.id)
        if chat == None:
            chat = Chat(chat_id=message.chat.id, user_id=message.from_user.id, open_date=datetime.now(), \
                            last_message_date=datetime.now(), username=message.from_user.username, \
                            first_name=message.from_user.first_name, last_name=message.from_user.last_name, \
                            silent_mode=False, deleted=False)
        else:
            chat.last_message_date = datetime.now()
            chat.username = message.from_user.username
            chat.first_name = message.from_user.first_name
            chat.last_name = message.from_user.last_name

        if message.text == STOP_CMD:
            chat.silent_mode = True
        elif message.left_chat_participant != None:
            if message.left_chat_participant.id == BOT_ID:
                chat.deleted = True
        elif message.new_chat_participant != None:
            if message.new_chat_participant.id == BOT_ID:
                chat.deleted = False
        elif message.text == START_CMD:
            chat.silent_mode = False
            chat.deleted = False

        return chat.primary_id, chat.silent_mode


def send_broad(bot, text, admin_list):
    with db_session:
        for chat in select(chat for chat in Chat if not (chat.silent_mode or chat.deleted)):
            try:
                is_admin = str(chat.primary_id) in admin_list
                reply_markup = KEYBOARD_ADMIN if is_admin else KEYBOARD
                bot.sendMessage(chat_id=chat.chat_id, text=text, reply_markup=reply_markup)
            except telegram.TelegramError as error:
                print "TelegramError", error


def send_large_message(bot, chat_id, text):
    MAX_LINES = 100

    def grouper(iterable, n, fillvalue=None):
        "Collect data into fixed-length chunks or blocks"
        # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
        args = [iter(iterable)] * n
        return itertools.izip_longest(fillvalue=fillvalue, *args)

    lines = text.splitlines()
    for block in grouper(lines, MAX_LINES, ''):
        bot.sendMessage(chat_id=chat_id, text='\n'.join(block))
    

def print_userlist(bot, message):
    with db_session:
        chats_str = ''
        for chat in select(chat for chat in Chat):
            chats_str += u'{}. {} {} (@{})'.format(chat.primary_id, chat.first_name, chat.last_name, \
                                                     chat.username)
            if chat.silent_mode:
                chats_str += ' (silent mode)'
            if chat.deleted:
                chats_str += ' (deleted)'
            chats_str += '\n'

        try:
            send_large_message(bot, message.chat_id, chats_str)
        except telegram.TelegramError as error:
            print "TelegramError", error


def send_message(bot, message):
    with db_session:
        cmd = text = ''
        primary_id = 0
        params = message.text.split(' ', 2)
        if len(params) > 0:
            cmd = params[0]
        if len(params) > 1:
            try:
                primary_id = int(params[1])
            except ValueError:
                bot.sendMessage(chat_id=message.chat_id, text='cannot find user')
                return False
        if len(params) > 2:
            text = params[2]
        if primary_id == 0:
            bot.sendMessage(chat_id=message.chat_id, text='cannot send message to empty user')
        elif len(text) == 0:
            bot.sendMessage(chat_id=message.chat_id, text='cannot send empty message')
        else:
            chat = Chat.get(primary_id=primary_id)
            if chat == None:
                bot.sendMessage(chat_id=message.chat_id, text='cannot find user')
            elif chat.deleted:
                bot.sendMessage(chat_id=message.chat_id, text='this user marked as deleted')
            else:
                bot.sendMessage(chat_id=chat.chat_id, text=text)


def get_timing_message():
    CMD = "curl -s 'https://docs.google.com/spreadsheets/d/1eBh9w0WRRJleBQd7eVHFKBQgc5V_w0TYymMkKHL6598/export?format=tsv&id=1eBh9w0WRRJleBQd7eVHFKBQgc5V_w0TYymMkKHL6598&gid=1758330787' | sed -e 's/[[:space:]]$//g' | awk 'NF > 1 {print }'"
    return os.popen(CMD).read()


def run(bot, admin_list, logfile, slackbot):
    global LAST_UPDATE_ID
    for update in bot.getUpdates(offset=LAST_UPDATE_ID, timeout=10):
        message = update.message
        primary_id, silent_mode = update_chat_db(message)
        log_update(update, logfile, slackbot, primary_id)
        is_admin = str(primary_id) in admin_list
        reply_markup = KEYBOARD_ADMIN if is_admin else KEYBOARD
        if not silent_mode:
            reply_markup = reply_markup.replace(START_CMD, STOP_CMD)
    
        if message.left_chat_participant:
            pass
        elif message.text == HELP_CMD:
                bot.sendMessage(chat_id=message.chat_id, \
                                text=MESSAGE_HELP_ADMIN if is_admin else MESSAGE_HELP)
        elif message.text == HELLO_CMD:
            if message.from_user != None:
                username = message.from_user.first_name + ' ' + message.from_user.last_name
            else:
                username = 'Anonymous'
            bot.sendMessage(chat_id=message.chat_id, text=u'Hello, {}!'.format(username))
        elif message.text == START_CMD:
            bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_START, reply_markup=reply_markup)
        elif message.text == STOP_CMD:
            bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_STOP, reply_markup=reply_markup)
        elif message.text == NEXT_CMD:
            timepad_token = open('.timepad_token').readline().strip()
            next_event_message=timepad.get_next_event(timepad_token)
            bot.sendMessage(chat_id=message.chat_id, text=next_event_message, reply_markup=reply_markup)
        elif message.text == FLOOD_CMD:
            bot.sendMessage(chat_id=message.chat_id, text=FLOOD_CHAT_LINK, reply_markup=reply_markup)
        elif message.text.lower() == TIMING_CMD:
            timing_message = get_timing_message()
            bot.sendMessage(chat_id=message.chat_id, text=timing_message, reply_markup=reply_markup)
        elif is_admin and message.text.startswith(SEND_BROAD_CMD):
            send_broad(bot, message.text[len(SEND_BROAD_CMD) + 1:], admin_list)
        elif is_admin and message.text.startswith(SEND_MSG_CMD):
            send_message(bot, message)
        elif is_admin and message.text == SECRET_LIST_CMD:
            timepad_token = open('.timepad_token').readline().strip()
            timepad_list_filename = timepad.save_list_to_file(timepad_token)
            bot.sendDocument(chat_id=message.chat_id, document=open(timepad_list_filename, 'rb'))
            os.remove(timepad_list_filename)
        elif is_admin and message.text == USER_LIST_CMD:
            print_userlist(bot, message)
        else:
            pass
            
        LAST_UPDATE_ID = update.update_id + 1


if __name__ == '__main__':
    main()
