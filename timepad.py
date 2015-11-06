#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import datetime

TIMEPAD_GRANUMSALIS_ORG_ID = 50011

def save_list_to_file(filename, token, org_id=TIMEPAD_GRANUMSALIS_ORG_ID, date=None):
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


    full_list = []
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
                                                          len(order['tickets'])),
                    orders['values'])
            full_list.extend(list_chunk)
            skip += limit
        else:
            break

    with open(filename, 'w') as list_file:
        for name in full_list:
            list_file.write(u'{0}\n'.format(name).encode('utf-8'))


def main():
    token = open('.timepad_token').readline().strip()
    save_list_to_file('/tmp/today_list.txt', token)


if __name__ == '__main__':
    main()
