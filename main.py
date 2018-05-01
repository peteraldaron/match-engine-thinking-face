import json
import requests
import datetime
import time
import logging
import copy
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger()
BASE_URL = 'https://api.gotinder.com'


with open('config.json') as fp:
    conf = json.load(fp)


def get_headers():
    return {'x-auth-token': conf.get('token'),
            'User-Agent': conf.get('ua'),
            'Content-Type': 'application/json'}


def filtering_criteria(user_profile):
    return (len(user_profile.get('bio')) != 0
            and len(user_profile.get('photos')) > 1
            and (len(user_profile.get('jobs')) > 0 or (len(user_profile.get('schools')) > 0))
            and user_profile.get('gender') == 1)

def filter_user(user_profile):
    if not filtering_criteria(user_profile):
        print(f'filtering out user {user_profile.get("_id")}')
        requests.get(f'{BASE_URL}/pass/{user_profile.get("_id")}')
        return {}
    else:
        requests.get(f'{BASE_URL}/like/{user_profile.get("_id")}')
        return user_profile

def is_match(user_profile):
    return user_profile.get('group_matched') is True


def sanitize_result(user_profile):
    keys = [k for k in user_profile.keys()]
    allowed_keys = {'group_matched', '_id', 'common_friends', 'bio', 'birth_date', 'name', 'photos', 'jobs', 'schools'}
    for key in keys:
        if key not in allowed_keys:
            del user_profile[key]

def get_recs():
    try:
        req = requests.get(f'{BASE_URL}/user/recs', headers=get_headers())
        results = req.json().get('results', [])
        print(f'got results, size = {len(results)}')
        with ThreadPoolExecutor(max_workers=32) as ex:
            response = list(ex.map(filter_user, results))
        print(f'Final list size: {len(response)}')
        response = [v for v in response if len(v)]

        if len(response):
            with open(str(datetime.datetime.utcnow()) + '.json', 'w') as fp:
                fp.write(json.dumps([sanitize_result(res) for res in response]))
        print('wrote batch')

    except BaseException as e:
        print(f'{e}')
        raise e


while True:
    time.sleep(1)
    get_recs()
