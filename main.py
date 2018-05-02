import json
import requests
import datetime
import time
import logging
import copy
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger()
BASE_URL = 'https://api.gotinder.com'
DESIGNATED_SCHOOLS = ['aalto', 'helsinki', 'åbo', 'lund', 'stock', 'oulu', 'sibeliu']
can_approve = True


with open('config.json') as fp:
    conf = json.load(fp)


def get_headers():
    return {'x-auth-token': conf.get('token'),
            'User-Agent': conf.get('ua'),
            'Content-Type': 'application/json'}

def has_designated_school(school_obj_list):
    schools = ''.join([ob.get('name', '') for ob in school_obj_list]).lower()
    return any((school in schools for school in DESIGNATED_SCHOOLS))


def filtering_criteria(user_profile):
    return (len(user_profile.get('bio')) > 3
            and len(user_profile.get('photos')) > 1
            and (len(user_profile.get('jobs')) > 0 or (len(user_profile.get('schools')) > 0))
            and user_profile.get('gender') == 1) or has_designated_school(user_profile.get('schools', []))


def filter_user(user_profile):
    global can_approve
    def _make_request_keep():
        return requests.get(f'{BASE_URL}/like/{user_profile.get("_id")}', headers=get_headers())

    def _make_request_filter():
        return requests.get(f'{BASE_URL}/pass/{user_profile.get("_id")}', headers=get_headers())

    if not filtering_criteria(user_profile):
        print(f'filtering out user {user_profile.get("_id")}')
        res = _make_request_filter()
        while res.status_code != 200:
            time.sleep(1)
            res = _make_request_filter()
        print(f'user {user_profile.get("_id")} filter query returned: {res.status_code}')
        return {}
    else:
        if not can_approve:
            return {}

        res = _make_request_keep()
        while res.status_code != 200:
            time.sleep(1)
            res = _make_request_keep()
        if not res.json().get('likes_remaining', False):
            print(f'Out of likes, recording negatives')
            can_approve = False
            return {}
        print(f'user {user_profile.get("_id")} keep query returned: {res.status_code}\n{res.json()}')
        return user_profile


def is_match(user_profile):
    return user_profile.get('group_matched') is True


def sanitize_result(user_profile):
    keys = [k for k in user_profile.keys()]
    allowed_keys = {'group_matched', '_id', 'common_friends', 'bio', 'birth_date', 'name', 'photos', 'jobs', 'schools'}
    for key in keys:
        if key not in allowed_keys:
            del user_profile[key]
    return user_profile

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
            with open('-'.join(str(datetime.datetime.utcnow()).split(' ')) + '.json', 'w') as fp:
                fp.write(json.dumps([sanitize_result(res) for res in response]))
        print('wrote batch')

    except BaseException as e:
        print(f'{e}')
        raise e


while True:
    time.sleep(1)
    get_recs()
