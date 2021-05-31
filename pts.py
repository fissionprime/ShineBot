import requests
import json
import math
from dotenv import load_dotenv
import os

CLID = os.getenv("CLID")
headers = {'Accept':'application/vnd.twitchtv.v5+json'}
headers['Client-ID'] = CLID

chat = None

def twitchreq(url, header = headers):
    """
    makes a get request to the twitch api and returns a json blob
    Keyword arguments:
    url (str) -- the url to request from
    header -- header included in request
    """
    r = requests.get(url, headers=header)
    return r.json()

class getchatters(object):
    """
    retrieves list of chatters in channel, returns a list of chatters
    of specified type
    Keyword arguments:
    channel (str) -- the channel in question
    type (str) -- None (default) returns all chatters,
        other options: (moderators, global_mods, staff, admins,
        viewers)
    """
    def __init__(self, channel):
        self.last = None
        self.__call__(channel)
    def __call__(self, channel):
        url = "https://tmi.twitch.tv/group/user/" + channel + "/chatters"
        r = twitchreq(url)
        l = []
        c = r['chatters']
        l = (c['moderators'] + c['staff'] + c['admins'] +
            c['global_mods'] + c['viewers'])
        if l:
            self.last = l
            return l
        else:
            return False
def updatelist(filename, channel, time=5, ppm=5):
    """
    updates list of users, time spent in channel, and points. If file with
    this info does not already exist, creates the file.
    Keyword arguments:
    filename (str) -- file in which chatter data are stored
    channel (str) -- the channel in question
    time (int) -- time (minutes) added to each user's info on each
        call (default 5)
    ppm (int) -- points awarded per minute in channel (default 5)
    """
    global chat
    if not chat:
        chat = getchatters(channel)
    tries = 0
    while True:
        l = chat(channel)
        if l:
            break
        else:
            tries +=1
            if tries >= 6:
                if chat.last:
                    l = chat.last
                else:
                    return False

    usrs = l[0]
    info = []
    counter = 0
    for i,usr in enumerate(l[1:]):
        if counter == -1:
            counter +=1
            continue
        usrs = usrs + "," + usr
        counter += 1
        if counter == 99:
            url = "https://api.twitch.tv/kraken/users?login=" + usrs
            r = twitchreq(url)
            info.append(r)
            usrs = l[i+2]
            counter = -1
    else:
        url = "https://api.twitch.tv/kraken/users?login=" + usrs
        r = twitchreq(url)
        info.append(r)
    try:
        with open(filename) as file:
            data = json.load(file)
            usrlist = []
            for r in info:
                usrlist.append(r["users"].keys())
            for usrid in usrlist:
                result = change_usr_stats(filename,usrid,
                    ppm * time, time, data=data, loaded=True)
                if not result:
                    pass #failed somewhere
            with open(filename, 'w') as file:
                json.dump(data, file, indent=4)
            return True
    except IOError: #file doesn't exist yet
        usrs = {}
        try:
            for r in info:
                for usr in r['users']:
                    usrs.update({usr["_id"]: usr})
            usrlist = usrs.keys()
            for usrid in usrlist:
                usrs[usrid].update({'time':time, cfg.PTSNAME:(ppm * time)})
            with open(filename, 'w') as file:
                json.dump(usrs, file, indent=4)
            return True
        except:
            return False


def change_usr_stats(filename, user, pts, time=0, data=None, loaded=False,
    save=False):
    """
    gives or takes points to/from one or more users
    Keyword arguments:
    pts (int or list) -- amount of points to be awarded. If int, same amount
        given to all users. If list, len(pts) must equal len(users)
    usr -- either usrid or user dict object
    """
    if loaded == False:
        with open(filename) as file:
            data = json.load(file)
    if isinstance(user, basestring):
        user = [user]  
    for usr in user:
        try:
            if isinstance(usr, basestring):
                usr = data[usr]
            usr[cfg.PTSNAME] += pts
            usr["time"] += time

        except (AttributeError, KeyError, ValueError):
            #user doesn't exist yet
            #look up by id from twitch, add user entry
            if isinstance(usr, basestring):
                try:
                    url = "https://api.twitch.tv/kraken/users/" + usr
                    r = twitchreq(url)
                    print r
                    r.update({cfg.PTSNAME: pts, "time": time})
                    data.update({r["_id"]:r})
                except:
                    raise
                    return False
    if save:
        with open(filename, 'w') as file:
            json.dump(data, file, indent=4)
    return True