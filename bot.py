#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import telegram
import sys
from pyslack import SlackClient
import json

LAST_UPDATE_ID = None
MESSAGE = "Пока никаких новостей...\nСледите за анонсами на сайте granumsalis.ru или в группе vk.com/granumsalis."


def main():
    global LAST_UPDATE_ID

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    telegram_token = open('.telegram_token').readline().strip()
    slack_token = open('.slack_token').readline().strip()

    bot = telegram.Bot(telegram_token)
    slackbot = SlackClient(slack_token)

    # This will be our global variable to keep the latest update_id when requesting
    # for updates. It starts with the latest update_id if available.
    try:
        LAST_UPDATE_ID = bot.getUpdates()[-1].update_id
    except IndexError:
        LAST_UPDATE_ID = None

    while True:
        try:
            echo(bot, slackbot)
        except telegram.TelegramError:
            pass


def echo(bot, slackbot):
    global LAST_UPDATE_ID

    # Request updates after the last updated_id
    for update in bot.getUpdates(offset=LAST_UPDATE_ID, timeout=10):
        message = update.message

        slack_text = u'{} {} ({}): {}\n'.format(message.from_user.first_name,
                                                message.from_user.last_name,
                                                message.from_user.name,
                                                message.text)
        log_text = update.to_json().decode('unicode-escape').encode('utf-8') + '\n'
        sys.stdout.write(log_text)
        sys.stdout.flush()
        slackbot.chat_post_message('#telegram-messages', slack_text, as_user=True)

        if (True): #message.text == '/start'):
            # Reply the message
            bot.sendMessage(chat_id=message.chat_id,
                            text=MESSAGE)

            # Updates global offset to get the new updates
            LAST_UPDATE_ID = update.update_id + 1


if __name__ == '__main__':
    main()
