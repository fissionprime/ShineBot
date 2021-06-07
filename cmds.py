import time
import types
import random
import json
from dotenv import load_dotenv
import os
#import waiting
#from handlemsg import savecmds

NumberTypes = (types.IntType, types.LongType, types.FloatType, types.ComplexType)

load_dotenv()

CHAN = os.getenv("CHAN")
NICK = os.getenv("NICK")
ADMINS = os.getenv("ADMINS")


def chat(sock, msg):
    """
    Send a chat message to the server.
    Arguments:
    sock -- the socket over which to send the message
    msg (str)  -- the message to be sent
    """
    sock.send("PRIVMSG {0} :{1}\n".format(CHAN, msg).encode("utf-8"))
    print(NICK + ": " + str(msg))


def savecmds(filename):
    import handlemsg


    cmdsdict = {"_waiting": handlemsg.waiting, "queue": handlemsg.waiting_msgs, "commands": {}}
    cmds = handlemsg.cmdlist.items()
    for name, cmd in cmds:
        cmdsdict["commands"].update({name: cmd.__dict__})
    with open(filename, 'w') as outfile:
        json.dump(cmdsdict, outfile, indent=4)


def compareperms(permlvl, user, sock):
    #user is tuple of (username, id, perm level)
    allowed = (user[2] >= permlvl) # 's' > 'm' > 'a' is order
    if not allowed:
        chat(sock, "@%s, you do not have permission to call this command" % (user[0]))
        return False
    else: return True


class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class InputError(Error):
    """Exception raised for errors in the input.

    Attributes:
    msg  -- explanation of the error
    """

    def __init__(self, msg):
        self.msg = msg

class Command(object):
    text = False
    def __init__(self, cd = 0, last_ex = 0, perm = 0, aliases = []):
        self.name = self.__class__.__name__
        self.cd = cd
        self.last_ex = last_ex
        if isinstance(aliases, basestring):
            aliases = aliases.split(",")
        self.aliases = aliases
        self.locked = False
        self.perm = perm
        if isinstance(perm, basestring):
            if perm[0] == 'm': #mod
                self.perm = 2
            elif perm[0] in ['b', 'a']: #broadcaster, admin
                self.perm = 3
            elif perm[0] == 's': #sub
                self.perm = 1
            else:
                self.perm = 0


class TextCommand(Command):
    """a text-based command for ShineBot"""

    def __init__(self, name, mess = None, delays = None, cd = 0, perm = 0,
        aliases = [], last = 0):
        """
        Attributes:
        name (str): name of command
        mess (list[str]): list of messages. if len>1, len(mess) must
            be len(delays) + 1
        delays (list[float]): list of delays between messages. if 
            len>0, len(mess) must be len(delays) + 1			
        cd (float): cooldown since last use of command.
        perm (int): permission level required to call command
        """

        super(TextCommand, self).__init__(cd, last, perm, aliases)
        self.name = name
        self.text = True
        self.mess = mess
        self.delays = delays
        self.perm = perm
        self.formats = {"__call__":{"user": "usr","sock": "sock", "queue":"queue",
            "msg_ind": "int", "single":"bool"}}

        if self.delays and self.mess and (len(self.mess) - 1 != 
            len(self.delays)):
            raise InputError("# of messages and delays do not match")
        if self.mess:
            for elem in self.mess:
                if not isinstance(elem, basestring):
                    raise InputError("messages are not all strings")
                if self.delays:
                    for elem in self.delays:
                        if not isinstance(elem, NumberTypes):
                            raise InputError("delays are not all valid\
                                numbers")

    def __call__(self, user, sock, queue, msg_ind = None, single = True):
        """
        Calls an existing TextCommand.
        Arguments:
        user (str, int, int): tuple of (username, id, perm level)
        sock (socket): socket providing the chat connection
        queue: waiting messages list. Handled automatically
        msg_ind (int): msg index. Used if you wish to call messages
            out of order, or separately. NOTE: indexed starting with 1
        single (bool): if true, following messages will NOT be added
            to the queue. If no specified msg_ind, assumed to be False.
        """
        #user is tuple of (username, id, perm level)
        allowed = (user[2] >= self.perm) # 's' > 'm' > 'a' is order

        if time.time() >= (self.last_ex + self.cd): #off cooldown
            if not allowed:
                chat(sock, "@%s, you do not have permission to call this command" % (user[0]))
                return False
            if not self.delays and msg_ind == None and len(self.mess) != 1:
                #if no specified delays, no specified message, and multiple
                #possible messages, randomly send one of them
                chat(sock, self.mess[random.randrange(0, len(self.mess))])
            else:
                #message indices start at 1, for ease of chatters
                if msg_ind == None:
                    msg_ind = 1
                    #if no specified index in delay command, not single msg
                    single = False
                msg_ind -= 1
                try:
                    chat(sock, self.mess[msg_ind])
                except IndexError:
                    chat(sock, "command \"!%s\" has only %i messages" % (self._name, len(self.mess)))
                #should handle cases where at end of delays list too. test.
                if self.delays and len(self.delays) > msg_ind and not single: #if msgs left
                    t = time.time() + self.delays[msg_ind]
                    i = 0
                    try:
                        while queue[i][0] <= t:
                            i += 1
                    except IndexError: #queue is empty, so ignore error
                        pass
                    queue.insert(i, [[t, self.name, self.mess[msg_ind + 1]], user])
            self.last_ex = time.time() #update
        else:
            return "cooldown"
    




class addcom(Command):

    def __init__(self):
        super(addcom, self).__init__()
        self.formats = {"__call__":{"name": "str", "mess":"list(quote)",
            "cmdlist": "cmdlist", "sock":"sock","delays": "list(float)",
            "cd":"float", "perm":"int", "aliases":"str", "user":"usr"}}
        self.perm = 2
    def __call__(self, name, mess, cmdlist, sock, user, delays = None, cd = 0,
        perm = 0, aliases = []):
        #permission level should probably be a default value arg here with default value of 0
        import handlemsg

        if not compareperms(self.perm, user, sock): return False

        try:
            if handlemsg.cmdlist.get(name.lower()):
                chat(sock, "Command \"" + name + "\" already exists")
                return False
            else:
                handlemsg.cmdlist.update({name : TextCommand(name, mess, delays,
                    cd, perm, aliases)})
                for alias in handlemsg.cmdlist[name].aliases:
                    if handlemsg.cmdlist.get(alias):
                        chat(sock, "Failed to add alias \"" + alias + "\".\
                         Command already exists")
                    else:
                        handlemsg.cmdlist.update({alias : handlemsg.cmdlist[name]})
                chat(sock, "Command \"" + name + "\" added.")
            savecmds(CHAN[1:] + "_cmds.txt")
        except InputError:
            chat(sock, "Format error in messages/delays")


class editcom(Command):
    def __init__(self):
        super(editcom, self).__init__()
        self.formats = {"__call__":{"name": "str", "strings":"list(str)",
            "nums":"list(float)","user":"usr"}}
        self.perm = 2
    def __call__(self, name, strings, nums, user, **kwargs):
        """


        """
        import handlemsg

        #first check permissions
        if not compareperms(self.perm, user): return False

        #if strings[0] in add, set, del, delete
        types = ["add", "set", "del", "delete", "lock", "alias"]
        try:
            if strings[0] in types:
                if strings[0] == "add":
                    pass
                elif strings[0][:3] == "del":
                    #delete specified command
                    del handlemsg.cmdlist[name]
                    savecmds(CHAN[1:] + "_cmds.txt")
                    return True
                else: #set
                #hasattr to figure out if command has thing trying to change
                #loop through strings, nums, and then kwargs
                    pass
        except KeyError:
            chat(s, "No command \"" + m[0][0] + "\"")
            return False
        except:
            pass
        pass
    #def editmsg(self, msg_ind = None):

class poll(Command):
    def __init__(self, cd = 0, last = 0, perm = 0, aliases = []):
        super(poll, self).__init__(cd, last, perm, aliases)
        self.name = "poll"
        self.formats = {"__call__":{"sock": "sock"}}
    def __call__(self, test2, test3 = 0, test = 0):
        print str(test) + " " + str(test2) + " " + str(test3)

class reload(Command):
    def __init__(self):
        super(reload, self).__init__()
        self.perm = 2
    def __call__():
        pass

class shutdown(Command):
    def __init__(self):
        super(shutdown, self).__init__()
        self.formats = {"__call__":{"user": "usr", "sock":"sock"}}
        self.perm = 2
        self.name = "shutdown"
    def __call__(self, user, sock):
        #negative permission check
        if not compareperms(self.perm, user, sock): return False

        savecmds(CHAN[1:] + "_cmds.txt")
        #save point totals here
        exit(1)

class help(Command):
    def __init__(self):
        super(help, self).__init__()
        self.name = "help"
        self.formats = {"__call__":{"user":"usr", "name":"str", "sock":"sock"}}
        self.mess = {}
    def __call__(self, user, name, sock):
        if name not in self.mess:
            chat(sock, "@%s, no help is available for command %s" % (user[0], name))
        else:
            chat(sock, self.mess[name])

#class dice(Command):

#class bet(Command):