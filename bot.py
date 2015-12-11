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
from datetime import datetime
from pony.orm import db_session, select
from db import granumDB, Chat


LAST_UPDATE_ID = None
MESSAGE_START = "Пока никаких новостей...\nЯ буду присылать анонсы сюда и в канал @GranumSalis."
MESSAGE_STOP = "Я умолкаю в этом чате! Может быть, за анонсами удобнее следить в канале @GranumSalis?.."
MESSAGE_HELP = "/hello - Greetings\n/help - show this message\n/next - next event\n/stop - exclude self from notification list"
KEYBOARD = '{"keyboard" : [["/start", "/stop", "/next", "/help"]], "resize_keyboard" : true}'
KEYBOARD_ADMIN = '{"keyboard" : [["/start", "/stop", "/next", "/help"], ["/user_list", "/secret_list"]], "resize_keyboard" : true}'
MESSAGE_HELP_ADMIN = "/hello - Greetings\n/help - show this message\n/next - next event\n/user_list - list of subscribers\n/secret_list - get participants list for next event\n/send_broad <message> - send message to all users\n/send <user_id> <message> - send <message> to <user_id>\n/stop - exclude self from notification list"
MESSAGE_ALARM = "Аларм! Аларм!"
CHAT_ID_ALARM = 79031498
BOT_ID = 136777319
SEND_BROAD_CMD = '/send_broad'
SEND_MSG_CMD = '/send'
START_CMD = '/start'
STOP_CMD = '/stop'
SECRET_LIST_CMD = '/secret_list'
USER_LIST_CMD = '/user_list'
HELLO_CMD = '/hello'
HELP_CMD = '/help'
NEXT_CMD = '/next'
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



def send_broad(bot, text):
    with db_session:
        for chat_id in select(chat.chat_id for chat in Chat if not (chat.silent_mode or chat.deleted)):
            try:
                bot.sendMessage(chat_id=chat_id, text=text)
            except telegram.TelegramError:
                pass


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
            bot.sendMessage(chat_id=message.chat_id, text=chats_str)
        except telegram.TelegramError:
            pass


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


def run(bot, admin_list, logfile, slackbot):
    global LAST_UPDATE_ID
    for update in bot.getUpdates(offset=LAST_UPDATE_ID, timeout=10):
        message = update.message
        log_update(update, logfile, slackbot)
        update_chat_db(message)
        is_admin = str(message.from_user.id) in admin_list
    
        if message.left_chat_participant:
            pass
        elif message.text == HELP_CMD:
            if is_admin:
                bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_HELP_ADMIN)
            else:
                bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_HELP)
        elif message.text == HELLO_CMD:
            if message.from_user != None:
                username = message.from_user.first_name + ' ' + message.from_user.last_name
            else:
                username = 'Anonymous'
            bot.sendMessage(chat_id=message.chat_id, text="Hello, {}!".format(username))
        elif message.text == START_CMD:
            bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_START, \
                                reply_markup=(KEYBOARD_ADMIN if is_admin else KEYBOARD))
        elif message.text == STOP_CMD:
            bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_STOP)
        elif message.text == NEXT_CMD:
            timepad_token = open('.timepad_token').readline().strip()
            next_event_message=timepad.get_next_event(timepad_token)
            bot.sendMessage(chat_id=message.chat_id, text=next_event_message)
        elif is_admin and message.text.startswith(SEND_BROAD_CMD):
            send_broad(bot, message.text[len(SEND_BROAD_CMD) + 1:])
        elif is_admin and message.text.startswith(SEND_MSG_CMD):
            send_message(bot, message)
        elif is_admin and message.text == SECRET_LIST_CMD:
            timepad_token = open('.timepad_token').readline().strip()
            timepad_list_filename = timepad.save_list_to_file(timepad_token)
            bot.sendDocument(chat_id=message.chat_id, document=open(timepad_list_filename, 'rb'))
            os.remove(timepad_list_filename)
        elif is_admin and message.text == USER_LIST_CMD:
            print_userlist(bot,message)
        else:
            pass
            
        LAST_UPDATE_ID = update.update_id + 1


if __name__ == '__main__':
    main()
