# -*- coding: utf-8 -*-
from xml.etree.ElementTree import tostring
import re
import os
import pprint
import lxml.etree as ET
from itertools import chain

"""
CONSTS
"""
ROOT="/Users/mrgecko/Documents/Dev/Data/adele/dossiers"

"""
XPATH
"""
XPATH_TI_FACSIM_COORDS_TRANSCRIPTION="//ti:div[@type='facsimile']//ti:seg/@rend"
XPATH_TI_FACSIM_ANNO_TRANSCRIPTION="//ti:div[@type='facsimile']//ti:seg"

XPATH_TI_FACSIM_COORDS_FIGDESC="//ti:figDesc//ti:seg/@rend"
XPATH_TI_FACSIM_ANNO_FIGDESC="//ti:figDesc//ti:seg"

"""
helpers
"""
get_manifest_url = lambda id: "http://193.48.42.68/adele/iiif/manifests/man{0}.json".format(id)
get_image_id = lambda id: "http://193.48.42.68/loris/adele/dossiers/{0}.jpg/full/full/0/default.jpg".format(id)
get_insert_stmt = lambda table,fields,values: "INSERT INTO {0} ({1}) VALUES ({2});".format(table, fields, values)
get_delete_stmt = lambda table,where_clause="": "DELETE FROM {0} {1};".format(table, where_clause)

clean = lambda s : s.replace("&amp;","&").replace("&gt;",">").replace("&lt;","<")
nullIfNone = lambda v, callback=None : "null" if v is None else callback(v) if callback is not None else v
escapeQuotes = lambda s : s.replace('"', '\\"')

p = re.compile("<[^>]+>(.*)<\/[^>]+>")
def get_tag_xml_content(node):
    m = re.match(p, ET.tounicode(node))
    return m.group(1)

#def stringify(node):
#    parts = ([node.text] +
#             list(chain((ET.tounicode(c) for c in node.getchildren()))) +
#             [node.tail])
#    parts = filter(None, parts)
#    return ''.join(parts).strip()

"""
inserts
"""
def insert_image_zone(dossier):
    values = []
    zone_id = 1
    for t in dossier["image_zone"]:
        values.append([
            dossier["manifest_url"],
            dossier["img_id"],
            str(zone_id),
            t["coords"],
            nullIfNone(t["note"], lambda t: '"{0}"'.format(escapeQuotes(t)))
        ])
        zone_id += 1
    #generate insert statements
    stmts = [ get_insert_stmt("image_zone", "manifest_url,img_id,zone_id,coords,note",
                              '"{0}","{1}",{2},"{3}",{4}'.format(*value))
        for value in values
    ]
    return stmts

def insert_image(dossier):
    stmts = [
        get_insert_stmt("image",
                        "manifest_url,img_id,doc_id",
                        '"{0}","{1}",{2}'.format(dossier["manifest_url"], dossier["img_id"], dossier["id"]))
    ]
    return stmts


"""
validity checks
"""
check_coords_validity = lambda coords : [int(c) for c in coords.split(",")]
facsim_coords_error = []


cnt_file_parsing_error = 0

"""
processing
"""
dossiers = {}
filenames = [f for f in os.listdir(ROOT) if f.endswith(".xml")]
filenames.sort()

for f in filenames:

    """
    Initialisation des dossiers
    """
    id = f.split(".")[0]
    dossiers[f] = {
        "id": id,
        "manifest_url": get_manifest_url(id),
        "img_id": get_image_id(id),
        "image_zone" : []
    }

    """
    tables image & image_zone
    """
    try:
        doc = ET.parse(os.path.join(ROOT,f))
    except:
        cnt_file_parsing_error += 1
        break

    facsim_coord_tr = doc.xpath(XPATH_TI_FACSIM_COORDS_TRANSCRIPTION, namespaces={"ti":"http://www.tei-c.org/ns/1.0"})
    facsim_note_tr = doc.xpath(XPATH_TI_FACSIM_ANNO_TRANSCRIPTION, namespaces={"ti":"http://www.tei-c.org/ns/1.0"})

    facsim_coord_figdesc = doc.xpath(XPATH_TI_FACSIM_COORDS_FIGDESC, namespaces={"ti":"http://www.tei-c.org/ns/1.0"})
    facsim_note_figdesc = doc.xpath(XPATH_TI_FACSIM_ANNO_FIGDESC, namespaces={"ti":"http://www.tei-c.org/ns/1.0"})

    # Récupérations des zones de transcription
    for coords_tr, note_tr in zip(facsim_coord_tr, facsim_note_tr):
        try:
            check_coords_validity(coords_tr)
            dossiers[f]["image_zone"].append({"coords": coords_tr, "note": None})
        except ValueError:
            facsim_coords_error.append((f, coords_tr))
    # Récupération des zones d'annotations & l'annotation associée
    for coords_figdesc, note_figdesc in zip(facsim_coord_figdesc, facsim_note_figdesc):
        try:
            check_coords_validity(coords_figdesc)
            dossiers[f]["image_zone"].append({"coords": coords_figdesc, "note": clean(get_tag_xml_content(note_figdesc))})
        except ValueError:
            facsim_coords_error.append((f, coords_figdesc))

    """
    tables transcription & transcriptionHasNote
    """



"""
display
"""
print("=" * 80)
print("facsim coords error:")
pprint.pprint(set(facsim_coords_error))
print("file parsing error (nb files): {0}".format(cnt_file_parsing_error))


add_sql_comment = lambda f, c="=" : f.write("--" + c * 40 + "\n")

print("=" * 80)
print("SQL statements written to 'insert_statements.sql'")
with open('insert_statements.sql', 'w+') as f:

    f.write(get_delete_stmt("image_zone") + "\n")
    f.write(get_delete_stmt("image") + "\n")
    add_sql_comment(f, '#')

    for dossier in dossiers.values():
        #table image
        for i in insert_image(dossier):
            f.write(i + "\n")

        add_sql_comment(f, '-')

        #table image_zone
        for i in insert_image_zone(dossier):
            f.write(i + "\n")
        add_sql_comment(f, '=')


