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

LAST_UPDATE_ID = None
MESSAGE = "Пока никаких новостей...\nЯ буду присылать анонсы сюда и в канал @GranumSalis."
MESSAGE_STOP = "Я умолкаю в этом чате! Может быть, за анонсами удобнее следить в канале @GranumSalis?.."
MESSAGE_ALARM = "Аларм! Аларм!"
CHAT_ID_ALARM = 79031498
SEND_BROAD_CMD = '/send_broad '
STOP_CMD = '/stop'
SECRET_LIST_CMD = '/secret_list'
TELEGRAM_MSG_CHANNEL = '#telegram-messages'

def main():
    global LAST_UPDATE_ID

    parser = argparse.ArgumentParser(description="Telegram bot for GranumSalis")
    parser.add_argument("--logfile", type=str, default='log', help="Path to log file")
    parser.add_argument("--chatsfile", type=str, default='chats', help="Path to chats file")
    args = parser.parse_args()

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
            run(bot, args.logfile, args.chatsfile, slackbot)
        except telegram.TelegramError as error:
            print "TelegramError", error
            time.sleep(1)
        except Exception:
            traceback.print_exc()
            bot.sendMessage(chat_id=CHAT_ID_ALARM, text=MESSAGE_ALARM)
            time.sleep(100)


def log_update(update, logfile, chatsfile, slackbot):
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
        
    # TODO: rewrite with message.left_chat_participant
    with open(chatsfile) as chatsf:
        chats = json.load(chatsf)

    if not chat_id in chats:
        chats.append(chat_id)
        with open(chatsfile, 'w') as chatsf:
            json.dump(chats, chatsf, indent=4)

    if message.text == STOP_CMD:
        chats.remove(chat_id)
        with open(chatsfile, 'w') as chatsf:
            json.dump(chats, chatsf, indent=4)

    slackbot.chat_post_message(TELEGRAM_MSG_CHANNEL, slack_text, as_user=True)


def send_broad(bot, chatsfile, text):
    with open(chatsfile) as chatsf:
        chats = json.load(chatsf)

    new_chats = []
    for chat in chats:
        try:
            bot.sendMessage(chat_id=chat, text=text)
            new_chats.append(chat)
        except telegram.TelegramError:
            pass

    with open(chatsfile, 'w') as chatsf:
        json.dump(new_chats, chatsf, indent=4)


def run(bot, logfile, chatsfile, slackbot):
    global LAST_UPDATE_ID

    for update in bot.getUpdates(offset=LAST_UPDATE_ID, timeout=10):
        message = update.message

        log_update(update, logfile, chatsfile, slackbot)

        if message.text.startswith(SEND_BROAD_CMD):
            send_broad(bot, chatsfile, message.text[len(SEND_BROAD_CMD):])
        elif message.left_chat_participant:
            pass
        elif message.text == STOP_CMD:
            bot.sendMessage(chat_id=message.chat_id, text=MESSAGE_STOP)
        elif message.text == SECRET_LIST_CMD:
            timepad_token = open('.timepad_token').readline().strip()
            timepad_list_filename = timepad.save_list_to_file(timepad_token)
            bot.sendDocument(chat_id=message.chat_id, document=open(timepad_list_filename, 'rb'))
            os.remove(timepad_list_filename)
        elif message.text != '':
            bot.sendMessage(chat_id=message.chat_id, text=MESSAGE)
        else:
            pass
            
        LAST_UPDATE_ID = update.update_id + 1


if __name__ == '__main__':
    main()
