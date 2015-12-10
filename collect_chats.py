#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import telegram
import argparse
from db import granumDB
from bot import update_chat_db


def main():

    parser = argparse.ArgumentParser(description="Collect chats info from log to DB")
    parser.add_argument("--logfile", type=str, default='log', help="Path to log file")
    parser.add_argument("--dbfile", type=str, default='granumsalis.sqlite.collected', help="Path to sqlite DB file")
    args = parser.parse_args()

    # Rename dbfile if exists
    os.system('[ -e {0} ] && mv -f {0} {1}'.format(args.dbfile, args.dbfile + '.old'))
    granumDB.bind('sqlite', args.dbfile, create_db=True)
    granumDB.generate_mapping(create_tables=True)

    with open(args.logfile) as log:
        for line in log:
            try:
                update = telegram.Update.de_json(json.loads(line.rstrip()))
                update_chat_db(update.message)
            except Exception as e:
                # TODO: process multilines correctly
                print str(e), type(e)
                print(line.rstrip())
                pass



if __name__ == '__main__':
    main()
