import socket
import re
import time
import numpy as np
import handlemsg
import os
from dotenv import load_dotenv


s = socket.socket()
test = 1

load_dotenv()

PASS = os.getenv("PASS")
NICK = os.getenv("NICK")
CHAN = os.getenv("CHAN")
HOST = os.getenv("HOST")
PORT = int(os.getenv("PORT"))
RATE = os.getenv("RATE")
RATES = RATE.split("/")
RATE = float(RATES[0])/float(RATES[1])
print(CHAN)





CHAT_MSG=re.compile(r"^:\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :")

connecting = True
while connecting:
    s = socket.socket()
    s.connect((HOST, PORT))
    s.send("PASS {}\r\n".format(PASS).encode("utf-8"))
    s.send("NICK {}\r\n".format(NICK).encode("utf-8"))
    s.send("JOIN {}\r\n".format(CHAN).encode("utf-8"))
    s.send("CAP REQ :twitch.tv/membership\r\n")
    s.send("CAP REQ :twitch.tv/tags\r\n")
    #s.send("CAP REQ :twitch.tv/commands\r\n")
    handlemsg.init()
    print(s)
    print("Commands Uploaded. Now chatting.")
    #handlemsg.chat(s, "test message")
    buff = ""
    while True:
        r = s.recv(1024)
        r = r.decode("utf-8")
        r = r.split("\r\n")
        #print(r)
        if buff: #leftover buffered message that previously wasn't completed
            r[0] = buff + r[0]
            buff = ""
        if r[-1] != "": #no \r\n at end of message, i.e. middle of message
            buff = r[-1]
        for response in r[:-1]:
            if len(response) == 0:
                #save commands list
                break
            if response == "PING :tmi.twitch.tv\r\n":
                s.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))

            #buffer responses here. Detect end of messages with \r\n
            #and keep and remaining output stored until next response.
            else:
                handlemsg.checkmsg(s, response)
                #username = re.search(r"\w+", response).group(0) # return the entire match
                #message = CHAT_MSG.sub("", response)
                #print(username + ": " + message).encode("utf-8")
                # if re.match(r"!(\w+)", message): #
                #     chat(test, sock=s)
                #     thing = cmds.textcommand()
                #     chat(test, sock=s)
                #use re.compile(). Goal for tomorrow is parsing for commands,
                #come up with translating !addcom into code using regexes,
                #and write commands to file/access them when called.
            time.sleep(1/RATE)