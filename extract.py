#!/usr/bin/env python3

import json, datetime
import os, sys
import re
import random
import shutil
from collections import defaultdict
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config(config_file='config.json'):
    try:
        with open(config_file) as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Config file not found at '{config_file}'")
        sys.exit(1)

def load_users(users_file, config):
    users = {}
    try:
        with open(users_file) as f:
            data = json.load(f)
            for u in data:
                id = u["id"]
                username = u["name"]
                users[id] = {'name': username}
    except FileNotFoundError:
        logging.warning(f"Users file not found at '{users_file}'. Usernames will not be resolved.")

    if 'user_colors' not in config:
        config['user_colors'] = {}

    for id, user_data in users.items():
        if id not in config['user_colors']:
            r = lambda: random.randint(200, 255)
            config['user_colors'][id] = f'#{r():x}{r():x}{r():x}'
        user_data['color'] = config['user_colors'][id]

    return users

def format_text(t, users):
    # Handle triple-quoted sections
    t = re.sub(r'```(.*?)```', r'<pre>\1</pre>', t, flags=re.DOTALL)

    n = 0
    log = ""
    while "<@" in t and n < 100:
        n+= 1
        idx = t.index("<@")
        endangle = t[idx+2:].index(">")
        id = t[idx+2:idx+endangle+2]
        log += f"Trying to replace__<@{id}>__ with @{users.get(id, {'name': '???'})['name']} at index {idx}->{endangle}"
        t = t.replace(f"<@{id}>", "@"+users.get(id, {'name': '???'})['name'])
    if n > 5:
        print(f"Lots of replacements? {t}: {log}q")

    n = 0
    while "<http" in t and n < 100:
        n += 1
        idx = t.index("<http")
        endangle = t[idx+1:].index(">")
        url = t[idx+1:idx+endangle+1]
        if "|" in url:
            (urla, urlb) = url.split("|", 1)
            t = t.replace(f"<{urlb}>", f" <a href={urla} >{urlb}</a> ")
        else:
            t = t.replace(f"<{url}>", f" <a href={url} >{url}</a> ")
    t = t.replace("’", "'")
    t = t.replace("\\n", " <br>")
    return t

from jinja2 import Environment, FileSystemLoader

def render_template(template_name, context):
    env = Environment(loader=FileSystemLoader('templates/'))
    template = env.get_template(template_name)
    return template.render(context)

def process_messages(channel_dir, users):
    try:
        files = list(os.listdir(channel_dir))
    except FileNotFoundError:
        logging.error(f"Channel directory not found at '{channel_dir}'")
        return [], {}, []
    files.sort()

    stats = {
        "count": 0,
        "wordtot": 0,
        "personwords": defaultdict(int),
        "msgcount": defaultdict(int),
        "wordcount": defaultdict(int),
        "personwordcount": defaultdict(int)
    }
    messages = []
    months = []
    last_month = None
    last_ts = 0

    for fn in files:
        if not re.match(r'\d{4}-\d{2}-\d{2}\.json$', fn):
            continue
        file_path = os.path.join(channel_dir, fn)
        try:
            with open(file_path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.error(f"Error reading or parsing file {file_path}: {e}")
            continue

        for msg in data:
            if not msg.get("ts"):
                logging.warning(f"In file {fn}, no ts in msg {msg}")
                continue

            text = msg.get("text", "---")
            text = format_text(text, users)
            userid = msg.get("user", None)

            if userid:
                user_data = users.get(userid, {'name': userid, 'color': '#ffffff'})
                username = user_data['name']
                color = user_data['color']
            else:
                userid = "bot/other"
                username = "BOT"
                color = '#ffffff'

            stats["msgcount"][username] += 1
            ts = msg["ts"]
            threadid = msg.get("thread_ts", None)

            if msg.get("user_profile", None):
                display_name = msg["user_profile"]["display_name"]
                real_name= msg["user_profile"]["real_name"]
                user = msg["user_profile"]["name"]+f"({real_name})"
            else:
                user = username

            when = datetime.datetime.fromtimestamp(int(float(ts)))
            month_id = when.strftime('%Y-%m')
            month_name = when.strftime('%B %Y')

            if month_id != last_month:
                months.append({'id': month_id, 'name': month_name})
                new_month = True
                last_month = month_id
            else:
                new_month = False

            temporal_gap = None
            if last_ts > 0:
                gap = int(float(ts)) - last_ts
                if gap > 3600 * 24: # 1 day
                    days = gap / (3600 * 24)
                    temporal_gap = f"--- {days:.1f} days ---"
            last_ts = int(float(ts))

            low = text.lower().replace(".", " ").replace("!", " ").replace("?", " ").replace(",", " ")
            words = low.split(" ")

            for w in words:
                stats["wordcount"][w] += 1
                stats["personwordcount"][f"{username}+{w}"] += 1
                stats["personwords"][username] += 1
                stats["wordtot"] += 1

            user = user.replace("é", "&eacute;").replace("í", "&iacute;")

            message_data = {
                'ts': ts,
                'user': user,
                'when': when.strftime('%Y-%m-%d %H:%M:%S'),
                'text': text,
                'is_thread_start': threadid == ts,
                'new_month': new_month,
                'month_id': month_id,
                'month_name': month_name,
                'temporal_gap': temporal_gap,
                'color': color
            }

            if threadid and threadid != ts:
                for m in messages:
                    if m['ts'] == threadid:
                        if 'replies' not in m:
                            m['replies'] = []
                        m['replies'].append(message_data)
                        break
            else:
                messages.append(message_data)

            stats["count"] += 1

    return messages, stats, months

def generate_stats(stats, users):
    stats_data = {}

    posters = list(stats["msgcount"].keys())
    posters.sort(key=lambda x: stats["msgcount"][x])
    stats_data['posters'] = {p: stats['msgcount'][p] for p in posters}

    stats_data['total_messages'] = stats['count']

    words = list(stats["wordcount"].keys())
    words.sort(key=lambda x: -1*stats["wordcount"][x])

    word_stats = {}
    for w in words:
        if stats["wordcount"][w] > 24:
            inc = 1000000 * stats["wordcount"][w] / stats["wordtot"]
            word_stats[w] = {'incidence_per_million': int(inc), 'users': {}}
            for u in users.values():
                usertot = stats["personwords"][u]
                if usertot > 400:
                    usersaycount = stats["personwordcount"][f"{u}+{w}"]
                    userrate = 1000000*((usersaycount+(inc*inc/1000000))/(usertot+inc))
                    ratio = userrate/inc
                    if ratio > 1.5 and usersaycount >= 10:
                        word_stats[w]['users'][u] = {
                            'ratio': f"{ratio:.1f}x",
                            'user_rate': userrate,
                            'user_say_count': usersaycount,
                            'user_total_words': usertot,
                            'percentage_of_word': f"{(100*usersaycount/stats['wordcount'][w]):.1f}%"
                        }
    stats_data['word_stats'] = word_stats

    user_word_stats = {}
    for u in stats["personwords"].keys():
        user_word_stats[u] = {
            'total_words': stats['personwords'][u],
            'message_count': stats['msgcount'][u],
            'percentage_of_all_words': f"{(100*stats['personwords'][u]/stats['wordtot']):.1f}%"
        }
    stats_data['user_word_stats'] = user_word_stats

    return stats_data

def main():
    config = load_config()
    users = load_users(config['users_file'], config)

    parser = argparse.ArgumentParser(description='Slack conversation extractor.')
    parser.add_argument('--channels', nargs='+', help='The channel directories to process.')
    parser.add_argument('--all-channels', action='store_true', help='Process all channels in the input directory.')
    parser.add_argument('--stats', action='store_true', help='Enable statistics generation.')
    args = parser.parse_args()

    if args.all_channels:
        input_dir = config['input_directory']
        try:
            channels = [d for d in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, d)) and any(re.match(r'\d{4}-\d{2}-\d{2}\.json$', f) for f in os.listdir(os.path.join(input_dir, d)))]
        except FileNotFoundError:
            logging.error(f"Input directory not found at '{input_dir}'")
            sys.exit(1)
    elif args.channels:
        channels = args.channels
    else:
        logging.error("Please specify channels to process using --channels or use --all-channels.")
        sys.exit(1)

    output_dir = config['output_directory']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    shutil.copy(os.path.join('templates', 'style.css'), output_dir)

    for channel in channels:
        logging.info(f"Processing channel: {channel}")
        channel_dir = os.path.join(config['input_directory'], channel)

        messages, stats, months = process_messages(channel_dir, users)

        if not messages:
            logging.warning(f"No messages found for channel: {channel}")
            continue

        output = render_template('channel.html', {'messages': messages, 'months': months})

        output_file = os.path.join(output_dir, f"{channel}.html")
        try:
            with open(output_file, 'w') as f:
                f.write(output)
            logging.info(f"Generated HTML for channel: {channel}")
        except IOError as e:
            logging.error(f"Error writing HTML file for channel {channel}: {e}")

        if args.stats:
            stats_data = generate_stats(stats, users)
            stats_file = os.path.join(output_dir, f"{channel}_stats.json")
            try:
                with open(stats_file, 'w') as f:
                    json.dump(stats_data, f, indent=4)
                logging.info(f"Generated stats for channel: {channel}")
            except IOError as e:
                logging.error(f"Error writing stats file for channel {channel}: {e}")

    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

if __name__ == '__main__':
    main()
