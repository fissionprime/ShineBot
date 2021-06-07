import re
import socket
import cmds
#import waiting
import json
import time
import inspect
import copy
import pyclbr
from dotenv import load_dotenv
import os

load_dotenv()

CHAN = os.getenv("CHAN")
NICK = os.getenv("NICK")
ADMINS = os.getenv("ADMINS")

CHAT_MSG=re.compile(r"(?:.*?;)*?badges=(?P<badges>.*?);(?:.*?;)*?display-name=" \
    r"(?P<usr>\w+);(?:.*?;)*?mod=(?P<mod>\d);(?:.*?;)*?subscriber=" \
    r"(?P<sub>\d);(?:.*?;)*?user-id=(?P<id>\d+);user-type=(?P<type>.*)" \
    r" :\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :(?P<mess>.+)")

waiting_msgs = []
waiting = False
cmdlist = {}

def init():
    global waiting_msgs #fmt = [time, name of command = None, "<msg>"]
    global waiting
    global cmdlist
    try:
        #cmds.savecmds(CHAN[1:] + "_cmds.txt")
        with open(CHAN[1:] + "_cmds.txt") as file:
            data = json.load(file)
            waiting = data["_waiting"]
            waiting_msgs = data["queue"]
            existingcommands = data["commands"].items()
            print existingcommands
            for name ,com in existingcommands:
                if com.get("text"):
                    cmdlist.update({com["name"] : cmds.TextCommand(com["name"],
                        com["mess"], com["delays"], com["cd"], com["perm"],
                        com["aliases"])})
                if not com.get("text"):
                    try:
                        argspec = inspect.getargspec(getattr(getattr(cmds,
                            com["name"]),"__init__"))
                        dct = copy.deepcopy(com)
                        if not argspec.keywords:
                            for key in dct.keys():
                                if key not in argspec.args:
                                    del dct[key]
                        cmdlist.update({com["name"] :
                            getattr(cmds, com["name"])(**dct)})
                        del dct
                    except AttributeError:
                        pass #no built in com with this name
                if com.get("locked"):
                    cmdlist[com["name"]].locked = True
                for alias in com["aliases"]:
                    if alias in cmdlist:
                        if cmdlist[alias].get("text"):
                            cmdlist.update({alias : cmdlist[com["name"]]})
                        classes = pyclbr.readmodule("cmds").items()
            #check for new commands
            classes = pyclbr.readmodule("cmds").items()
            for name, cmd in classes:
                if name != "TextCommand" and name not in cmdlist:
                    try: #add all classes that inherit from Command
                        #other than TextCommand
                        command = cmd.__dict__["super"][0].__dict__
                        #check if "Command" is an ancestor
                        while (command["name"] != "Command"):
                            command = command["super"][0]
                        temp = getattr(cmds, name)()
                        cmdlist.update({temp.__dict__["name"] : temp})
                    except (AttributeError, TypeError):
                        continue
    except (IOError,ValueError): #commands file is empty or nonexistent
        #dump all the hardcoded commands and include them in new file
        with open(CHAN[1:] + "_cmds.txt", 'w') as outfile:
            cmdsdict = {"_waiting": False, "queue": [], "commands": {}}
            classes = pyclbr.readmodule("cmds").items()
            for name, cmd in classes:
                if name != "TextCommand":
                    try: #add all classes that inherit from Command
                        #other than TextCommand
                        command = cmd.__dict__["super"][0].__dict__
                        #check if "Command" is an ancestor
                        while (command["name"] != "Command"):
                            command = command["super"][0]
                        temp = getattr(cmds, name)()
                        cmdsdict["commands"].update({temp.__dict__["name"] : temp.__dict__})
                        cmdlist.update({temp.__dict__["name"] : temp})
                    except (AttributeError, TypeError):
                        continue
            print cmdsdict
            json.dump(cmdsdict, outfile, indent=4)

#import points data up here too






def flatten(l, ltypes=(list, tuple)):
    """flattens a list or tuple. Code by Mike Fletcher"""
    ltype = type(l)
    l = list(l)
    i = 0
    while i < len(l):
        while isinstance(l[i], ltypes):
            if not l[i]:
                l.pop(i)
                i -= 1
                break
            else:
                l[i:i + 1] = l[i]
        i += 1
    return ltype(l)

def chat(sock, msg):
    """
    Send a chat message to the server.
    Keyword arguments:
    sock -- the socket over which to send the message
    msg  -- the message to be sent
    """
    sock.send("PRIVMSG {0} :{1}\n".format(CHAN.encode("utf-8"), msg.encode("utf-8")))
    try:
        print(NICK + ": " + str(msg))
    except:
        print("Failed to print chat message. Likely contained a unicode character.")

def ban(sock, user):
    """
    Ban a user from the current channel.
    Keyword arguments:
    sock -- the socket over which to send the ban command
    user -- the user to be banned
    """
    chat(sock, ".ban {}".format(user))

def timeout(sock, user, secs=600):
    """
    Time out a user for a set period of time.
    Keyword arguments:
    sock -- the socket over which to send the timeout command
    user -- the user to be timed out
    secs -- the length of the timeout in seconds (default 600)
    """
    chat(sock, ".timeout {}".format(user, secs))

def checkmsg(s, response):
    """
    prints any waiting messages, and parses incoming messages
    to determine if they are commands to execute
    """

    global waiting_msgs
    global waiting
    global cmdlist



    res = re.match(CHAT_MSG, response)
    message = ""
    try:
        username = res.group("usr")
        usrid = res.group("id")
        message = res.group("mess")
        print(username + ": " + message).encode("utf-8")
    except AttributeError:
        #this means the message is a message from the server
        username = re.search(r"\w+", response).group(0) # return the entire match
        message = CHAT_MSG.sub("", response)
        print(username + ": " + message).encode("utf-8")

        #print("Failed to parse message. This is expected for all non-chat messages")    
    if waiting:
        #this block means a message remained in the queue when shinebot last shut down
        t = time.time()
        if t >= waiting_msgs[0][0][0]:
            msg = waiting_msgs.pop(0)
            if msg[0][1]:
                try:
                    cmd = cmdlist[msg[0][1]]
                    perm = msg[1]
                    print cmd
                    try:
                        cmd.__call__(perm, s, waiting_msgs, 
                            msg_ind = cmd.mess.index(msg[0][2]) + 1, single=False)
                        
                    except ValueError:
                        pass
                except KeyError:
                    pass
            else:
                chat(s, msg[0][2])
            if not waiting_msgs:
                waiting = False
        #check and see if queued up message should be posted
        #if queued message is not from a TextCommand, send it
        #if it is from one, find msg_ind and execute with correct value.
    com = re.match(r"!(\w+)", message)
    if com:
        try:
            perm = userpermlvl(res)
            args = parsemsg(message)
            print args
            exec_com(s, args, perm)
            if waiting_msgs:
                waiting = True
        except:
            raise
    #raise KeyboardInterrupt
        #thing = cmds.TextCommand("testcommand", ["test"])
        #chat(s, test)

def parsemsg(r):
    """takes a chat command message and returns a parsed version"""
    quote = re.compile(r"\s?((?:\".*?\")|(?:'.*?'))\s?")
    #regex for quotes needs adjustment to handle nested parenthesis
    keywords = re.compile(r"\s?(\w+\s?=\s?\w+)\s?")
    kw = {}
    words = []
    nums = []
    flags = []
    coms = []
    quotes = []
    unparsed = []

    #take string and split by quotes. pop all list elements containing quotes
    msg = quote.split(r)
    i = 0
    while i < len(msg): #while loop since changing list elements
        quoted = False
        if msg[i].count('\"') > 1 or msg[i].count('\'') > 1:
            quoted = True
        if ((msg[i].count('\"') % 2) == 0 or (msg[i].count("\'") % 2) == 0) and quoted: #check matched quotes
            quotes.append(eval(msg.pop(i)))
        else:
            i += 1

    #split out keywords, pop all elements with '='
    for j,el in enumerate(msg):
        msg[j] = keywords.split(el)
    msg = flatten(msg)
    i = 0
    while i < len(msg): #while loop since changing list elements
        if '=' in msg[i]: #check for keywords
            entry = re.split(r'\s?=\s?',msg.pop(i))
            kw.update({entry[0]:entry[1]}) #add keywords to dict
            del msg[i]
        elif msg[i] == '' or re.match(r'/s+',msg[i]):
            del msg[i]
        else:
            i += 1

    #split according to remaining whitespace
    for j,el in enumerate(msg):
        msg[j] = re.split(r'\s+',el)
    msg = flatten(msg)
    i = 0
    while i < len(msg): #while loop since changing list elements
        if msg[i].startswith('-'): #check for flags
            try:
                for char in msg[i][1:]:
                    flags.append(char)
            except:
                unparsed.append(msg[i])
            del msg[i]
        elif msg[i].startswith('!'):
            coms.append(msg.pop(i))
        elif re.match(r'\d+(\.\d+)?',msg[i]): #input is a number
            nums.append(float(msg.pop(i)))
        elif re.match(r'\w+',msg[i]): #input is a word
            words.append(msg.pop(i))
        else:
            unparsed.append(msg.pop(i))
    return [coms, kw, words, nums, flags, quotes, unparsed]

def exec_com(s, m, user):
    """executes a parsed command
    user = (username, usrid)"""
    fmt = None
    #perm = userpermlvl() #check permission here

    #formats should be included for each command in cmds.py
    #acceptable format terms: str, float, int, quote, flag or list() of
    #any of these
    secondarycmd = None
    cmdtype = None
    curr_cmd = None
    #figure out if command exists in cmds file or if is textcommand
    try:
        curr_cmd = cmdlist[m[0][0][1:].lower()]
        #print m[0][0][1:]
        #print curr_cmd.__dict__

        if len(m[0]) > 1:
            for word in m[0][1:]:
                m[2].append(word[1:].lower())

    except KeyError: #command doesn't exist in loaded commands
        chat(s, "No command \"" + m[0][0] + "\"")
        return False
    else:
        fmt = curr_cmd.formats["__call__"]
        curr_cmd = getattr(curr_cmd, "__call__")
    params = {}
    #pair up parsed values to command args
    for arg in inspect.getargspec(curr_cmd)[0]:
        if arg in m[1]:
            #pass any non-default keyword assignments
            params.update({arg:m[1][arg]})
        elif arg == 'kwargs':
            pass
        if arg == 'self':
            continue
        islist = re.match(r'list\((.+)\)', fmt[arg])
        fmt_this_arg = fmt[arg]
        if islist:
            fmt_this_arg = islist.group(1)
        if fmt_this_arg == 'str':
            if islist:
                params.update({arg: copy.copy(m[2])})
                del m[2][:]
            elif m[2]:
                params.update({arg: m[2].pop(0).encode("utf-8")})

        elif fmt_this_arg == 'float' or fmt_this_arg == 'int':
            if islist:
                nums = copy.copy(m[3])
                for num in nums:
                    num = eval(fmt_this_arg)(num)
                params.update({arg: nums})
                del m[3][:]
            elif m[3]:
                params.update({arg: eval(fmt_this_arg)(m[3].pop(0))})

        elif fmt_this_arg == 'quote':
            if islist:
                params.update({arg:copy.copy(m[5])})
                del m[5][:]
            elif m[5]:
                params.update({arg: m[5].pop(0)})

        elif fmt_this_arg == 'flag':
            params.update({arg:copy.copy(m[4])})
            del m[4][:]

        elif fmt_this_arg == 'sock':
            params.update({arg: s})

        elif fmt_this_arg == 'queue':
            params.update({arg: waiting_msgs})

        elif fmt_this_arg == 'usr':
            params.update({arg: user})

        elif fmt_this_arg == 'cmdlist':
            params.update({arg: cmdlist})

        else: #incorrect format
            continue

    #only pass kwargs if the command wants kwargs
    if inspect.getargspec(curr_cmd).keywords:
        params.update(m[1])
    #TODO: should parsed keywords be actual kwargs, or replace default value args?

    print "executing %s, params: %s" % (curr_cmd.__name__, str(params))
    result = curr_cmd(**params)
    return result

def userpermlvl(match):
    username = match.group("usr")
    userid = int(match.group("id"))
    mod = int(match.group("mod"))
    sub = int(match.group("sub"))
    usertype = match.group("type")
    permlvl = 0
    user = username.lower()
    if user in ADMINS or user == CHAN[1:]:
        permlvl = 3
    elif usertype:
        if usertype in ["admin", "staff", "mod", "global_mod"]:
            permlvl = 2
    elif sub:
        permlvl = 1
    #else permlvl = 0
    return (username, userid, permlvl)
#pass username along with perm level to function

#def shutdown():