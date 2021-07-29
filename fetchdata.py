import requests, os, json
from datetime import datetime, time, timedelta
import time as tim
accepted_initials = ['PL',  'PD', 'BL1', 'FL1',"SA",  "CL", "WC"] #look at football-data.org to add other competitions
# if you want to use a different api change process and get matches. format match data in the same way. 
# Watch out for utcdate!
api_key = os.environ[__apikey__]
ids = {
    'PL':733,
    'PD':380,
    'BL1':742,
    'FL1':746,
    'SA':757,
    'CL':734,
    'WC': 1
}
base = 'https://api.football-data.org/v2/'
headers = {
    'X-Auth-Token':api_key
}
def get_comp(id):
    resp = requests.get(f'{base}competitions/{id}', headers=headers)
    return json.loads(resp.text)

def get_matches(all_ids):
    id_list = ','.join(all_ids)
    today = ((datetime.utcnow()+timedelta(0)).strftime("%Y-%m-%d"))
    final=(datetime.utcnow()+timedelta(10)).strftime("%Y-%m-%d")
    resp=requests.get(f'https://api.football-data.org/v2/matches?competitions={id_list}&dateFrom={today}&dateTo={final}', headers=headers)
    return json.loads(resp.text)
def process_matches(all_ids=accepted_initials):
    matches=get_matches(all_ids)['matches']
    match_data=[]
    for i in matches:
        data={}
        data['competition']=i['competition']['name']
        data['utcdate']=i['utcDate']  #utc format - '%Y-%m-%dT%H:%M:%SZ
        data['time'] = (datetime.strptime(i['utcDate'],'%Y-%m-%dT%H:%M:%SZ')).strftime('%H:%M:%S')
        data['date'] = datetime.strptime(i['utcDate'],'%Y-%m-%dT%H:%M:%SZ').strftime('%d-%m-%Y')
        data['Home']=i['homeTeam']['name']
        data['Away']=i['awayTeam']['name']
        match_data.append(data)
    json.dump(match_data, open('matches.json', 'w'))
def add_teams():
    d={}
    for i in accepted_initials:
        link = f'{base}competitions/{i}/teams'
        r= requests.get(link, headers=headers)
        teams = json.loads(r.text)['teams']
        
        for j in teams:
            name = j['name']
            d[name]=i
        
    json.dump(d, open('teams.json','w'))