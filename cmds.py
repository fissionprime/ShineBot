import time
import types
import random
import json
from dotenv import load_dotenv
import os
from boltons.funcutils import wraps
from inspect import getargspec
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
    sock.send("PRIVMSG {0} :{1}\n".format(CHAN.encode("utf-8"), msg.encode("utf-8")))
    try:
        print(NICK + ": " + msg.encode("utf-8"))
    except:
        print("Failed to print chat message. Likely contained a unicode character.")


def savecmds(filename):
    import handlemsg


    cmdsdict = {"_waiting": handlemsg.waiting, "queue": handlemsg.waiting_msgs, "commands": {}}
    cmds = handlemsg.cmdlist.items()
    for name, cmd in cmds:
        cmdsdict["commands"].update({name: cmd.__dict__})
    with open(filename, 'w') as outfile:
        json.dump(cmdsdict, outfile, indent=4)


def checkperms(func):
    #decorator to check user permission level before command execution
    #note that user is tuple of (username, id, perm level)
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        argspec = getargspec(func)
        arg = argspec[0]
        if 'user' and 'sock' in arg:
            #NOTE: socket and user arguments must be named 'sock' and 'user'
            #in all methods which will be decorated
            induser = arg.index('user') - 1 #ignore 'self'
            indsock = arg.index('sock') - 1
            user = args[induser]
            sock = args[indsock]
            print user
            userperm = user[2]
            print userperm, self.perm
            if userperm >= self.perm:
                #user is permitted to use command
                print "I also got other args:", args, kwargs
                func(self, *args, **kwargs)
            else:
                chat(sock, "@%s, you do not have permission to call this command" % (user[0]))
                return False
    return wrapper




def checkexistence(name):
    #checks whether a command or alias exists under "name" and returns the command, or False
    import handlemsg
    toplevel = handlemsg.cmdlist.get(name)
    if toplevel:
        return toplevel
    else:
        #name not found at top level. Now check aliases.
        for com in handlemsg.cmdlist.values():
            if name in com.aliases:
                return com
    return False

def checkdelayvalidity(textcom):
    if textcom.delays and textcom.mess and (len(textcom.mess) - 1 != 
        len(textcom.delays)):
        raise InputError("# of messages and delays do not match")
    if textcom.mess:
        for elem in textcom.mess:
            if not isinstance(elem, basestring):
                raise InputError("messages are not all strings")
            if textcom.delays:
                for elem in textcom.delays:
                    if not isinstance(elem, NumberTypes):
                        raise InputError("delays are not all valid\
                            numbers")

    



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

        checkdelayvalidity(self)


    @checkperms
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


        if time.time() >= (self.last_ex + self.cd): #off cooldown
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
            "cd":"float", "perm":"int", "aliases":"list(str)", "user":"usr"}}
        self.perm = 2

    @checkperms
    def __call__(self, name, mess, cmdlist, sock, user, delays = None, cd = 0,
        perm = 0, aliases = []):
        #permission level should probably be a default value arg here with default value of 0
        import handlemsg

        #old permission check
        #if not compareperms(self.perm, user, sock): return False

        mess = [m.decode("utf-8") for m in mess]

        try:
            if checkexistence(name):
                chat(sock, "Command \"" + name + "\" already exists")
                return False
            else:
                handlemsg.cmdlist.update({name : TextCommand(name, mess, delays,
                    cd, perm)})
                for alias in aliases:
                    alias = alias.lower()
                    if checkexistence(alias):
                        chat(sock, "Failed to add alias \"" + alias + "\".\
                         Command already exists")
                    else:
                        print "attempting to add alias"
                        handlemsg.cmdlist[name].aliases.append(alias)
                chat(sock, "Command \"" + name + "\" successfully added.")
            savecmds(CHAN[1:] + "_cmds.txt")
        except InputError:
            chat(sock, "Format error in messages/delays")


class editcom(Command):
    def __init__(self):
        super(editcom, self).__init__()
        self.formats = {"__call__":{"name": "str", "strings":"list(str)",
            "nums":"list(float)","user":"usr", "sock":"sock", "mess":"list(quote)"}}
        self.perm = 2
    @checkperms
    def __call__(self, name, strings, nums, user, sock, mess=None, **kwargs):
        """


        """
        import handlemsg




        #define some subroutines
        def addalias(sock, command, aliases):
            aliasesadded = []
            try:
                for alias in aliases:
                    alias = alias.lower()
                    if checkexistence(alias):
                        chat(sock, "Failed to add alias \"" + alias + "\". Command already exists")
                    elif alias == 'all':
                        chat(sock, "Failed to add alias \"" + alias + "\". \"all\" is not an allowed alias")
                    else:
                        command.aliases.append(alias)
                        aliasesadded.append(alias)
                if aliasesadded:
                    chat(sock, "Added aliases " + str(aliasesadded) + " successfully.")
            except UnicodeDecodeError, UnicodeEncodeError:
                chat(sock, "Valid aliases may not contain unicode characters")
                return False
            except IndexError:
                chat(sock, "No aliases supplied")
                return False
            else:
                savecmds(CHAN[1:] + "_cmds.txt")
                return True

        def deletealias(sock, command, aliases):
            aliasesdeleted = []
            try:
                for alias in aliases:
                    alias = alias.lower()
                    if alias == 'all':
                        #delete all remaining eliases
                        aliasesdeleted.extend(command.aliases)
                        command.aliases = []
                        if aliasesdeleted:
                            chat(sock, "Deleted aliases " + str(aliasesdeleted) + " successfully.")
                        savecmds(CHAN[1:] + "_cmds.txt")
                        return True
                    elif command != checkexistence(alias):
                        chat(sock, "Failed to delete alias \"" + alias + "\". This alias belongs to a different command")
                    else:
                        res = command.aliases.remove(alias)
                        aliasesdeleted.append(alias)
                if aliasesdeleted:
                    chat(sock, "Deleted aliases " + str(aliasesdeleted) + " successfully.")
            except UnicodeDecodeError, UnicodeEncodeError:
                chat(sock, "Valid aliases may not contain unicode characters")
                return False
            except IndexError:
                chat(sock, "No aliases supplied")
                return False
            else:
                savecmds(CHAN[1:] + "_cmds.txt")
                return True

        def addmsg(sock, command, m, delay=None, ind=None):
            #add message to a command
            if not isinstance(command, TextCommand):
                pass
            pass

        def delmsg(sock, command, ind):
            if not isinstance(command, TextCommand):
                pass
            pass




        #first check permissions
        if not compareperms(self.perm, user, sock): return False

        #check if command to edit is valid
        #if 'name' is an alias, set 'command' to its parent command
        command = checkexistence(name)
        if not command:
            #send chat message
            return False

        #if strings[0] in add, set, del, delete
        types = ["add", "set", "del", "delete", "lock", "alias"]
        #try:
        if strings[0] in types:

            if strings[0] == "add":
                #check that there is a message passed to the function
                if not mess:
                    #if no message provided, only remaining valid call is "add alias"
                    if len(strings) < 2:
                        chat(sock, "No message to add")
                        return False
                    if strings[1] == "alias":
                        result = addalias(sock, command, strings[2:])
                        return result

                    chat(sock, "Unable to edit command. Invalid information supplied")
                    return False

                if command.delays:
                    #check if 'delay' was a keyword passed to function
                    #add messages here
                    if kwargs['delay']:
                        pass

            elif strings[0][:3] == "del":
                print "should try to delete"
                print command.name
                #check if deleting command or alias
                if len(strings) > 1:
                    #we don't want to delete entire command if someone typos "alias"
                    #so we fail gracefully if there are extra words that do not match "alias"
                    if strings[1] == "alias":
                        result = deletealias(sock, command, strings[2:])
                        return result
                    elif strings[1] in ['m', 'mess', 'message']:
                        #add messages here
                        pass
                    chat(sock, "As a preventative measure, deleting commands requires exact syntax.\
                        \"!editcom <command> del\" deletes the whole command. \
                        \"!editcom <command> del alias <alias1> <alias2>...\" deletes all provided aliases \
                        (replacing <alias> with \"all\" deletes all existing aliases)")

                    return False
                if nums:
                    #delete message at specified index
                    pass
                else:
                    #delete specified command entirely if no additional args provided
                    print "attempting to delete command"
                    del handlemsg.cmdlist[command.name]
                    savecmds(CHAN[1:] + "_cmds.txt")
                    chat(sock, "Command \"" + name + "\" successfully deleted.")
                    return True

            elif strings[0] == "set": #set
            #hasattr to figure out if command has thing trying to change
            #loop through strings, nums, and then kwargs
            #'set' needs to be able to change messages, delays, perms
                pass

            elif strings[0] == "lock": #lock
                pass

            elif strings[0] == "alias":
                pass

            else:
                #handle invalid input
                #reaching here means strings[0] not in types
                pass
        # except KeyError:
        #     chat(sock, "No command \"" + m[0][0] + "\"")
        #     return False
        # except:
        #     pass
        # pass
    #def editmsg(self, msg_ind = None):

class poll(Command):
    def __init__(self, cd = 0, last = 0, perm = 0, aliases = []):
        super(poll, self).__init__(cd, last, perm, aliases)
        self.name = "poll"
        self.formats = {"__call__":{"sock": "sock"}}

    @checkperms
    def __call__(self, test2, test3 = 0, test = 0):
        print str(test) + " " + str(test2) + " " + str(test3)

class reload(Command):
    def __init__(self):
        super(reload, self).__init__()
        self.perm = 2

    @checkperms
    def __call__(self):
        pass

class shutdown(Command):
    def __init__(self):
        super(shutdown, self).__init__()
        self.formats = {"__call__":{"user": "usr", "sock":"sock"}}
        self.perm = 2
        self.name = "shutdown"

    @checkperms
    def __call__(self, user, sock):
        savecmds(CHAN[1:] + "_cmds.txt")
        #save point totals here
        exit(1)

class help(Command):
    def __init__(self):
        super(help, self).__init__()
        self.name = "help"
        self.formats = {"__call__":{"user":"usr", "name":"str", "sock":"sock"}}
        self.mess = {}

    @checkperms
    def __call__(self, user, name, sock):
        if name not in self.mess:
            chat(sock, "@%s, no help is available for command %s" % (user[0], name))
        else:
            chat(sock, self.mess[name])

#class dice(Command):

#class bet(Command):