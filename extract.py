#!/opt/homebrew/bin/python3

# Usage
# ./extract.py channel > channel.html

import json, datetime
import os, sys
import re
from collections import defaultdict

users = {}

with open("users.json") as f:
    data = json.load(f)
    for u in data:
        id = u["id"]
        username = u["name"]
        users[id] = username


def format(t):
    #<@U0188NBJRD0>
    n = 0
    log = ""
    while "<@" in t and n < 100:
        n+= 1
        idx = t.index("<@")
        endangle = t[idx+2:].index(">")
        id = t[idx+2:idx+endangle+2]
        #print(f"Maybe ID is {id}")
        log += f"Trying to replace__<@{id}>__ with @{users.get(id, '???')} at index {idx}->{endangle}"
        t = t.replace(f"<@{id}>", "@"+users.get(id, "???"))
    if n > 5:
        print(f"Lots of replacements? {t}: {log}q")

    n = 0
    while "<http" in t and n < 100:
        n += 1
        idx = t.index("<http")
        endangle = t[idx+1:].index(">")
        url = t[idx+1:idx+endangle+1]
        if "|" in url:
            (urla, urlb) = url.split("|")
            t = t.replace(f"<{urlb}>", f" <a href={urla} >{urlb}</a> ")
        else:
            t = t.replace(f"<{url}>", f" <a href={url} >{url}</a> ")
        #print(f"Replacing url {url}<br>")
    t = t.replace("’", "'")
    t = t.replace("\\n", " <br>")
#    while re.search('.*\S{80}.*', t):
#        t = re.sub(r'(.*)(\S{40})(\S{40})(.*)', r'\1\2 <br>\3\4', t)
    return t
        
files = list(os.listdir(sys.argv[1]))
files.sort()
stats = ""
count = 0
wordtot = 0

personwords = defaultdict(int)
msgcount = defaultdict(int)
wordcount = defaultdict(int)
personwordcount = defaultdict(int)

output = ""

output += "<div>"
output += "<table rules=all border=1>"
for fn in files:
    #print(f"----------{fn}----------")
    file = sys.argv[1]+"/"+fn
    with open(file) as f:
        data = json.load(f)

        # Print the data
        #print(json.dumps(data, indent=7))
        for msg in data:
            text = msg.get("text", "---")
            text = format(text)
            userid = msg["user"]
            username = users.get(userid, userid)
            msgcount[username] += 1
            ts = msg["ts"]
            threadid = msg.get("thread_ts", None)
            if msg.get("user_profile", None):
                display_name = msg["user_profile"]["display_name"]
                real_name= msg["user_profile"]["real_name"]
                user = msg["user_profile"]["name"]+f"({real_name})"
            else:
                user = username
                #print(json.dumps(msg, indent=5))
            when = datetime.datetime.fromtimestamp(int(float(ts)))
            low = text.lower()
            low = low.replace(".", " ")
            low = low.replace("!", " ")
            low = low.replace("?", " ")
            low = low.replace(",", " ")
            words = low.split(" ")
            for w in words:
                wordcount[w] += 1
                personwordcount[f"{username}+{w}"] += 1
                personwords[username] += 1
                wordtot += 1
            user = user.replace("é", "&eacute;");
            user = user.replace("í", "&iacute;");
            if threadid and threadid != ts:
                output = output.replace(f"<thread id={threadid}>", f"<tr id={ts}><td><b>{user}</b><br><i><font color=gray><a href='#{ts}' style='color:gray'>{when}</a></font></i></td><td>{text}</td></tr><thread id={threadid}>")
            else:
                output += f"<tr id={ts}><td valign=top><b>{user}</b><br><i><font color=gray><a href='#{ts}' style='color:gray'>{when}</a></font></i></td><td>{text} <table border=1 rules=all><thread id={ts}></table></td></tr>"
            count += 1

output += "</div></table>"

print(output)
doStats= False
if doStats:
    posters = list(msgcount.keys())
    posters.sort(key=lambda x: msgcount[x])
    print( [f"{p}:{msgcount[p]}" for p in posters])
    print("<br>")
    print(f"Total messages: {count}")
    words = list(wordcount.keys())
    words.sort(key=lambda x: -1*wordcount[x])
    for w in words:
        if wordcount[w] > 24:
            inc = 1000000*wordcount[w]/wordtot
            print(f"[{w}] incidence rate per million: {int(inc)}<br>")
            for u in users.values():
                usertot = personwords[u]
                if usertot > 400:
                    usersaycount = personwordcount[f"{u}+{w}"]
                    userrate = 1000000*((usersaycount+(inc*inc/1000000))/(usertot+inc))
                    ratio = userrate/inc
                    if ratio > 1.5 and usersaycount >= 10:
                        if ratio > 4:
                            print("!!!")
                        print(f"--------{u} says \"{w}\" {ratio:.1f}x as often {userrate} ({usersaycount}/{usertot}) (said {(100*usersaycount/wordcount[w]):.1f}% of the \"{w}\"s)<br>")

    print("<p>")
    for u in personwords.keys():
        print(f"{u}: {personwords[u]}, {msgcount[u]} {(100*personwords[u]/wordtot):.1f}% of all words<br>")
