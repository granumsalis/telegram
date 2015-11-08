#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import datetime
import json
import os
import codecs
import pdfkit

TIMEPAD_GRANUMSALIS_ORG_ID = 50011
TIMEPAD_LIST_FILENAME = '/tmp/granumsalis-list{0}{1}.{2}'

def get_timepad_info(token, org_id=TIMEPAD_GRANUMSALIS_ORG_ID, date=None):
    timepad_api_url = 'https://api.timepad.ru/v1/events'

    if not date:
        date = datetime.datetime.now().strftime('%Y-%m-%d')

    params = {
        'limit' : '1',
        'sort' : '+starts_at',
        'organization_ids' : org_id,
        'starts_at_min' : date,
        'token' : token
    }
    event = requests.get(timepad_api_url, params=params).json()
    event_id = event['values'][0]['id']
    title = event['values'][0]['name']
    starts_at = event['values'][0]['starts_at']

    names_list = []
    skip = 0
    limit = 20
    params = {
        'limit' : limit,
        'token' : token
    }
    while True:
        params['skip'] = skip
        orders = requests.get('{0}/{1}/orders'.format(timepad_api_url, event_id), params=params).json()
        if orders.has_key('values'):
            list_chunk = map(lambda order: u'{0} {1} ({2})'.format(order['tickets'][0]['answers']['surname'], 
                                                          order['tickets'][0]['answers']['name'],
                                                          len(order['tickets'])).title(),
                    orders['values'])
            names_list.extend(list_chunk)
            skip += limit
        else:
            break

    names_list.sort()
    current_time = datetime.datetime.now().strftime('%c')
    title = u'Щепотка Соли "{0}"'.format(title)
    return { 'title' : title,
             'date' : date,
             'names_list' : names_list,
             'current_time' : current_time,
             'starts_at' : starts_at
    }


def save_list_to_file(token, filename=None, file_format='pdf', org_id=TIMEPAD_GRANUMSALIS_ORG_ID, date=None):

    if not date:
        date = datetime.datetime.now().strftime('%Y-%m-%d')

    if not filename:
        filename = TIMEPAD_LIST_FILENAME.format('-', date, file_format)

    info = get_timepad_info(token, org_id=org_id, date=date)

    if file_format == 'txt':
        with open(filename, 'w') as list_file:
            list_file.write(info.title.encode('utf-8'))
            for name in info.names_list:
                list_file.write(u'{0}\n'.format(name).encode('utf-8'))
    elif file_format == 'pdf':
        LIST_JADE = 'list.jade'
        LIST_HTML = 'list.html'
        OPTIONS_JSON = 'options.json'

        with open(OPTIONS_JSON, 'w') as options_file:
            json.dump(info, options_file)

        #jade_text = open('list.jade').read()
        #list_html = pyjade.simple_convert(jade_text)
        #open('list.html', 'w').write(list_html)

        # have to hack it through command exec since pyjade sucks
        os.system('jade -P -O {0} < {1} > {2}'.format(OPTIONS_JSON, LIST_JADE, LIST_HTML))
        list_html = codecs.open(LIST_HTML, encoding='utf-8').read()
        pdfkit.from_string(list_html, filename)
    else:
        raise "Format not supported"

    return filename


def main():
    token = open('.timepad_token').readline().strip()
    filename = save_list_to_file(token)
    print('List saved to {0}'.format(filename))


if __name__ == '__main__':
    main()
