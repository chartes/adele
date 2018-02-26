# -*- coding: utf-8 -*-
import copy
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
NS_TI={"ti":"http://www.tei-c.org/ns/1.0"}
USERNAME="jpilla"


NOTE_TYPES={
    "INLINE" : 0
}

"""
GLOBAL
"""
note_id = 0
translation_id = 0
transcription_id = 0


"""
XPATH
"""
XPATH_TI_FACSIM_COORDS_TRANSCRIPTION="//ti:div[@type='facsimile']//ti:seg/@rend"
XPATH_TI_FACSIM_ANNO_TRANSCRIPTION="//ti:div[@type='facsimile']//ti:seg"

XPATH_TI_FACSIM_COORDS_FIGDESC="//ti:figDesc//ti:seg/@rend"
XPATH_TI_FACSIM_ANNO_FIGDESC="//ti:figDesc//ti:seg"

XPATH_TI_TRANSCRIPTION="//ti:div[@type='transcription']"
XPATH_TI_TRANSLATION="//ti:div[@type='translation']"



"""
helpers
"""
get_manifest_url = lambda id: "http://193.48.42.68/adele/iiif/manifests/man{0}.json".format(id)
get_image_id = lambda id: "http://193.48.42.68/loris/adele/dossiers/{0}.jpg/full/full/0/default.jpg".format(id)

get_insert_stmt = lambda table,fields,values: "INSERT INTO {0} ({1}) VALUES ({2});".format(table, fields, values)
get_delete_stmt = lambda table,where_clause="": "DELETE FROM {0} {1};".format(table, where_clause)

clean_entities = lambda s : s.replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<")
nullIfNone = lambda v, callback=None : "null" if v is None else callback(v) if callback is not None else v
escapeQuotes = lambda s : s.replace('"', '\\"')


def stringify_children(node):
    from lxml.etree import tounicode
    from itertools import chain
    s = ''.join(
        chunk for chunk in chain(
            (node.text,),
            chain(*((tounicode(child, with_tail=False), child.tail) for child in node.getchildren())),
            (node.tail,)) if chunk)
    s = s.replace(' xmlns="http://www.tei-c.org/ns/1.0"', '')
    return re.sub('\s+', ' ', s).rstrip()

p = re.compile("<[^>]+>((.|\s)*)<\/[^>]+>")
def get_tag_xml_content(node):
    m = re.match(p, ET.tounicode(node))
    return m.group(1) if m is not None else None

def get_text_format(div):
    verses = div.xpath("ti:l", namespaces=NS_TI)
    head = div.xpath("ti:head", namespaces=NS_TI)
    p = div.xpath("ti:p", namespaces=NS_TI)
    return {
        "verses": verses, "has_verses" : len(verses) > 0,
        "head": head, "has_head" : len(head) > 0,
        "p": p, "has_p" : len(p) > 0
    }


def extract_terms(e):
    global note_id

    terms = []
    hasTerms = False
    for term in e.xpath("//ti:term", namespaces=NS_TI):
        term_content = stringify_children(term)

        if e.text is None:
            ptr_start = 0
        else:
            ptr_start = len(e.text)
        ptr_end = ptr_start + len(term_content)

        terms.append({"content": term.get("n"),
                      "id": note_id,
                      "type_id": NOTE_TYPES["INLINE"],
                      "ptr_start": ptr_start, "ptr_end": ptr_end})
        note_id += 1

        if e.text is None:
            e.text = term_content
        else:
            e.text += term_content
        term.getparent().remove(term)
        hasTerms = True

    if not hasTerms and e.text is None:
        return ()
    else:
        return (stringify_children(e), terms)




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
            nullIfNone(t["note"], lambda t: "'{0}'".format(t))
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

def insert_transcription(dossier):
    stmts = []
    if len(dossier["transcription"]) > 0:
        content = "".join(dossier["transcription"])
        stmts = [
            get_insert_stmt("transcription",
                            "transcription_id,doc_id,user_ref,content",
                            "{0},{1},'{2}','{3}'".format(dossier["id"], dossier["id"],USERNAME,content)
                            )
        ]
    return stmts

def insert_translation(dossier):
    stmts = []
    if len(dossier["translation"]) > 0:
        content = "".join(dossier["translation"])
        stmts = [
            get_insert_stmt("translation",
                            "translation_id,doc_id,user_ref,content",
                            "{0},{1},'{2}','{3}'".format(dossier["id"], dossier["id"],USERNAME,content)
                            )
        ]
    return stmts

def insert_note(note):
    stmts = [
        get_insert_stmt("note",
                        "note_id,note_type_id,user_ref,content",
                        "{0},{1},'{2}','{3}'".format(note["id"], note["type_id"], USERNAME, note["content"]))
    ]
    return stmts

def insert_note_types():
    stmts = [
        get_insert_stmt("note_type",
                        "note_type_id,note_type_label",
                        "{0},'{1}'".format(id, label)
                        )
        for label, id in NOTE_TYPES.items()
    ]
    return stmts

def insert_transcription_has_note(dossier):
    stmts = [
        get_insert_stmt("transcriptionHasNote",
                        "transcription_id,note_id,ptr_start,ptr_end",
                        "{0},{1},{2},{3}".format(dossier["transcription_id"], note["id"],
                                                 note["ptr_start"], note["ptr_end"])
                        )
        for note in dossier["transcription_notes"]
    ]
    return stmts

def insert_translation_has_note(dossier):
    stmts = [
        get_insert_stmt("translationHasNote",
                        "translation_id,note_id,ptr_start,ptr_end",
                        "{0},{1},{2},{3}".format(dossier["translation_id"], note["id"],
                                                 note["ptr_start"], note["ptr_end"])
                        )
        for note in dossier["translation_notes"]
    ]
    return stmts

"""
validity checks
"""
check_coords_validity = lambda coords : [int(c) for c in coords.split(",")]
facsim_coords_error = []


cnt_trancription_has_verses = 0
cnt_trancription_has_head = 0
cnt_trancription_has_p = 0
cnt_translation_has_verses = 0
cnt_translation_has_head = 0
cnt_translation_has_p = 0

cnt_file_parsing_error = 0

"""
=====================================
processing
=====================================
"""
dossiers = {}
filenames = [f for f in os.listdir(ROOT) if f.endswith(".xml")]
filenames.sort()

for f in filenames:
    print(f)
    """
    Initialisation des dossiers
    """
    id = f.split(".")[0]
    dossiers[f] = {
        "id": id,
        "manifest_url": get_manifest_url(id),
        "img_id": get_image_id(id),
        "image_zone" : [],
        "transcription_notes" : [],
        "translation_notes": [],
        "transcription" : [],
        "transcription_id": transcription_id,
        "translation" : [],
        "translation_id": translation_id
    }

    transcription_id += 1
    translation_id += 1

    """
    tables image & image_zone
    """
    try:
        doc = ET.parse(os.path.join(ROOT,f))
    except:
        cnt_file_parsing_error += 1
        break

    facsim_coord_tr = doc.xpath(XPATH_TI_FACSIM_COORDS_TRANSCRIPTION, namespaces=NS_TI)
    facsim_note_tr = doc.xpath(XPATH_TI_FACSIM_ANNO_TRANSCRIPTION, namespaces=NS_TI)

    facsim_coord_figdesc = doc.xpath(XPATH_TI_FACSIM_COORDS_FIGDESC, namespaces=NS_TI)
    facsim_note_figdesc = doc.xpath(XPATH_TI_FACSIM_ANNO_FIGDESC, namespaces=NS_TI)

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
            dossiers[f]["image_zone"].append({"coords": coords_figdesc, "note": clean_entities(get_tag_xml_content(note_figdesc))})
        except ValueError:
            facsim_coords_error.append((f, coords_figdesc))

    """
    tables transcription & note & transcriptionHasNote
    """
    transcriptions = doc.xpath(XPATH_TI_TRANSCRIPTION, namespaces=NS_TI)
    if len(transcriptions) > 0:
        tf =  get_text_format(transcriptions[0])
        if tf["has_verses"]: cnt_trancription_has_verses += 1
        if tf["has_head"]:  cnt_trancription_has_head += 1
        if tf["has_p"]:  cnt_trancription_has_p += 1
        ##transcription
        for i, v in enumerate(tf["verses"]):
            extract = extract_terms(copy.deepcopy(v))
            #extracted_verse = get_tag_xml_content(v)
            if len(extract) == 2:
                verse, terms = extract
                dossiers[f]["transcription"].append(clean_entities(verse))
                dossiers[f]["transcription_notes"] += terms
            else:
                #cas des vereses auto fermants <l/>
                dossiers[f]["transcription"].append("<br/>")

    """
    tables translation & note & translationHasNote
    """
    translations = doc.xpath(XPATH_TI_TRANSLATION, namespaces=NS_TI)
    if len(translations) > 0:
        tf = get_text_format(translations[0])
        if tf["has_verses"]: cnt_translation_has_verses += 1
        if tf["has_head"]: cnt_translation_has_head += 1
        if tf["has_p"]: cnt_translation_has_p += 1
        #translation
        for i, v in enumerate(tf["verses"]):
            extract = extract_terms(copy.deepcopy(v))
            #extracted_verse = get_tag_xml_content(v)
            if len(extract) == 2:
                verse, terms = extract
                dossiers[f]["translation"].append(clean_entities(verse))
                dossiers[f]["translation_notes"] += terms
            else:
                #cas des vereses auto fermants <l/>
                dossiers[f]["translation"].append("<br/>")



"""
display
"""
print("=" * 80)
print("facsim coords error:")
pprint.pprint(set(facsim_coords_error))
print("file parsing error (nb files): {0}".format(cnt_file_parsing_error))
print("=" * 80)
print("Transcription with verses: {0}".format(cnt_trancription_has_verses))
print("Transcription with head: {0}".format(cnt_trancription_has_head))
print("Transcription with p: {0}".format(cnt_trancription_has_p))
print("Translation with verses: {0}".format(cnt_translation_has_verses))
print("Translation with head: {0}".format(cnt_translation_has_head))
print("Translation with p: {0}".format(cnt_translation_has_p))

add_sql_comment = lambda f, c="=": f.write("--" + c * 40 + "\n")


print("=" * 80)
print("SQL statements written to 'insert_statements.sql'")
with open('insert_img_stmts.sql', 'w+') as f_img,\
     open('insert_transcription_stmts.sql', 'w+') as f_transcription,\
     open('insert_translation_stmts.sql', 'w+') as f_translation,\
     open('insert_types_stmts.sql', 'w+') as f_types,\
     open('insert_notes_stmts.sql', 'w+') as f_notes:

    f_img.write(get_delete_stmt("image_zone") + "\n")
    f_img.write(get_delete_stmt("image") + "\n")

    f_transcription.write(get_delete_stmt("transcription") + "\n")
    f_translation.write(get_delete_stmt("translation") + "\n")
    f_types.write(get_delete_stmt("note_type") + "\n")
    f_notes.write(get_delete_stmt("note") + "\n")



    add_sql_comment(f_img, '#')

    for dossier in dossiers.values():
        #table image
        for i in insert_image(dossier):
            f_img.write(i + "\n")

        add_sql_comment(f_img, '-')

        #table image_zone
        for i in insert_image_zone(dossier):
            f_img.write(i + "\n")
        add_sql_comment(f_img, '=')

        #table transcription
        for t in insert_transcription(dossier):
            f_transcription.write(t + "\n")

        #table translation
        for t in insert_translation(dossier):
            f_translation.write(t + "\n")

        #table note
        for note in dossier["transcription_notes"]:
            for t in insert_note(note):
                f_notes.write(t + "\n")
        add_sql_comment(f_notes, '-')
        for note in dossier["translation_notes"]:
            for t in insert_note(note):
                f_notes.write(t + "\n")

        add_sql_comment(f_notes, '=')
        for hasNote in insert_transcription_has_note(dossier):
            f_notes.write(hasNote + "\n")
        add_sql_comment(f_notes, '-')
        for hasNote in insert_translation_has_note(dossier):
            f_notes.write(hasNote + "\n")

    #note types
    for t in insert_note_types():
        f_types.write(t + "\n")
