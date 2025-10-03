# utils.py
# Funções utilitárias para o projecto

import xml.etree.ElementTree as ET
import math

NET_FILE = "Mapa_ambienteTeste.net.xml"

def parse_net_file(netfile=NET_FILE):
    """Lê o net.xml e devolve dicts: edges (list), tls (list with ids)."""
    tree = ET.parse(netfile)
    root = tree.getroot()

    edges = []
    tls = []
    for e in root.findall("edge"):
        eid = e.get("id")
        # ignorar edges internos com ':' no id
        if eid and not eid.startswith(":"):
            edges.append(eid)

    for tl in root.findall("tlLogic"):
        tid = tl.get("id")
        if tid:
            tls.append(tid)

    return {"edges": edges, "tls": tls}

def dist(a, b):
    """Distância euclidiana 2D entre tuplos (x,y)."""
    return math.hypot(a[0]-b[0], a[1]-b[1])
