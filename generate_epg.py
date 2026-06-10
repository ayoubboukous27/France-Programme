#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import xml.etree.ElementTree as ET
import json
import os

INPUT_XML = "guide.xml"
OUTPUT_JSON = "epg.json"

if not os.path.exists(INPUT_XML):
    raise FileNotFoundError(f"{INPUT_XML} not found")

tree = ET.parse(INPUT_XML)
root = tree.getroot()

# شعارات القنوات
channel_logos = {}

for channel in root.findall("channel"):
    channel_id = channel.get("id", "")

    icon = channel.find("icon")
    logo = ""

    if icon is not None:
        logo = icon.get("src", "")

    channel_logos[channel_id] = logo

programmes = []

for programme in root.findall("programme"):

    channel_id = programme.get("channel", "")

    title = programme.findtext("title", default="")
    subtitle = programme.findtext("sub-title", default="")
    desc = programme.findtext("desc", default="")

    icon_node = programme.find("icon")
    icon = ""

    if icon_node is not None:
        icon = icon_node.get("src", "")

    item = {
        "channel": channel_id,
        "logo": channel_logos.get(channel_id, ""),
        "icon": icon,
        "title": title,
        "programme": subtitle if subtitle else title,
        "desc": desc,
        "start": programme.get("start", ""),
        "stop": programme.get("stop", "")
    }

    programmes.append(item)

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(
        programmes,
        f,
        ensure_ascii=False,
        indent=2
    )

print(f"Extracted {len(programmes)} programmes")
print(f"Saved to {OUTPUT_JSON}")
