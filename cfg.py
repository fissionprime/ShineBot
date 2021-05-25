# cfg.py
HOST = "irc.chat.twitch.tv"              # the Twitch IRC server
PORT = 6667                         # always use port 6667!
NICK = "ShineBot_"            # your Twitch username, lowercase
PASS = "oauth:tczm9cl69qoy0vp67x5o88qfm4fuq3" # your Twitch OAuth token
CHAN = "#sarellan"                   # the channel you want to join
RATE = (100.0/30.0)
PTSNAME = "points"
ADMINS = ["fissionprime"]

waiting_msgs = []
waiting = False
cmdlist = {}