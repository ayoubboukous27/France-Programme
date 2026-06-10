import configparser
import xml.etree.ElementTree as ET

# Charger le fichier ini
config = configparser.ConfigParser()
config.read("programme-television.org.ini")

# Charger le fichier channels XML
tree = ET.parse("programme-television.org.channels.xml")
root = tree.getroot()

# Créer un nouveau XML EPG
epg_root = ET.Element("tv")

for channel in root.findall("channels/channel"):
    ch_id = channel.attrib.get("xmltv_id", channel.text)
    ch_elem = ET.SubElement(epg_root, "channel", id=ch_id)
    display_name = ET.SubElement(ch_elem, "display-name")
    display_name.text = channel.text

# Écrire le fichier EPG
tree_out = ET.ElementTree(epg_root)
tree_out.write("epg.xml", encoding="UTF-8", xml_declaration=True)
print("EPG XML généré : epg.xml")
