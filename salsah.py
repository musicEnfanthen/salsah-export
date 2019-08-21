from typing import List, Set, Dict, Tuple, Optional
import os
from lxml import etree
from pathlib import Path
import requests
import argparse
from enum import Enum
from pprint import pprint
import magic
import json

requests.urllib3.disable_warnings(requests.urllib3.exceptions.InsecureRequestWarning)

class Valtype(Enum):
    TEXT = 1
    INTEGER = 2
    FLOAT = 3
    DATE = 4
    PERIOD = 5
    RESPTR = 6
    SELECTION = 7
    TIME = 8
    INTERVAL = 9
    GEOMETRY = 10
    COLOR = 11
    HLIST = 12
    ICONCLASS = 13
    RICHTEXT = 14
    GEONAME = 15

class Richtext:

    def __init__(self) -> None:
        super().__init__()


class SalsahError(Exception):
    """Handles errors happening in this file"""

    def __init__(self, message):
        self.message = message


class Salsah:
    def __init__(self, server: str, user: str, password: str, session ) -> None:
        super().__init__()
        self.server = server
        self.user = user
        self.password = password
        self.session = session
        self.mime = magic.Magic(mime=True)
        self.selection_mapping = {}
        self.hlist_mapping = {}

    def get_icon(self, iconsrc: str, name: str):
        iconpath = os.path.join(assets_path, name)
        dlfile = session.get(iconsrc, stream=True)  # war urlretrieve()
        with open(iconpath, 'w+b') as fd:
            for chunk in dlfile.iter_content(chunk_size=128):
                fd.write(chunk)
            fd.close()

        mimetype = self.mime.from_file(iconpath)
        if mimetype == 'image/gif':
            ext = '.gif'
        elif mimetype == 'image/png':
            ext = '.png'
        elif mimetype == 'image/svg+xml':
            ext = '.svg'
        elif mimetype == 'image/jpeg':
            ext = '.jpg'
        elif mimetype == 'image/tiff':
            ext = '.tif'
        else:
            ext = '.img'
        os.rename(iconpath, iconpath + ext)
        return iconpath + ext

    def get_project(self, projectname: str, shortcode: str, session) -> dict:
        """
        EZ:
        Lays out the structure for the json file
        Fetches the project_info, prints and returns it; appends it to the general structure...
        Naming conventions for python-dictionaries:
        - Project: project_container
        - Project_info: project_info
        - Selections: selections_container
        - hlists: still missing: shall be appended to lists...
        - Nodes: nodes_container
        - Restypes: restypes_container
        - etc.
        - Users: users_container
        - Permissions: Nothing done so far
        - Ontology: ontology_container
        """

        #
        # first get all system ontologies
        #
        req = session.get(self.server + '/api/vocabularies/0?lang=all', auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        sysvocabularies = result['vocabularies']

        #
        # get project info
        #
        req = session.get(self.server + '/api/projects/' + projectname + "?lang=all", auth=(self.user, self.password) )
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])

        project_container = {
            "prefixes": dict(map(lambda a: (a['shortname'], a['uri']), sysvocabularies)),
            "project": {
                'shortcode': shortcode,
                'shortname': result['project_info']['shortname'],
                'longname': result['project_info']['longname'],
            },
        }
        project_info = result['project_info']           # Is this the project_container??? Decide later
        project = {
            'shortcode': shortcode,
            'shortname': project_info['shortname'],
            'longname': project_info['longname'],
            'descriptions': dict(map(lambda a: (a['shortname'], a['description']), project_info['description'])),
            'users': [{
                "username": "testuser",
                "email": "testuser@test.org",
                "givenName": "test",
                "familyName": "user",
                "password": "test",
                "lang": "en"
            }]
        }
        if project_info['keywords'] is not None:
            project['keywords'] = list(map(lambda a: a.strip(), project_info['keywords'].split(',')))

        #
        # Get the vocabulary. The old Salsah uses only one vocabulary per project....
        # Note: the API call always returns also the system vocabularies which we have to be excluded
        #
        req = session.get(self.server + '/api/vocabularies/' + projectname, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        vocabulary = None
        for voc in result['vocabularies']:
            if int(voc['project_id']) != 0:
                vocabulary = voc

        project['lists'] = self.get_selections_of_vocabulary(vocabulary['shortname'], session)

        """
        Below we set the pattern for the ontology. In the resources there is
        still some work to do: Terminology:
        : class: should be super: StillImageRepresentation instead of image
        : Maybe there is more work to do...
        """
        # project_info.update({"ontology": {
        #     "name": p_ontology,
        #     "label": "{} ontology".format(project),
        #     "resources": []
        # }})

        project['ontology'] = {
            'name': vocabulary['shortname'],
            'label': vocabulary['longname'],
        }
        #
        # ToDo: not yet implemented in create_ontology
        # if vocabulary.get('description') is not None and vocabulary['description']:
        #    project['ontology']['comment'] = vocabulary['description']

        project['ontology']['resources'] = self.get_resourcetypes_of_vocabulary(vocabulary['shortname'], session)
        project_container["project"] = project
        return project_container

    def get_properties_of_resourcetype(self, vocname: str, restype_id: int, salsah_restype_info: dict) -> list:

        gui_attr_lut = {
            'text': ['size', 'maxlength'],
            'textarea': ['width', 'rows', 'wrap'],
            'pulldown': ['selection'],
            'slider': ['stepsize'],
            'searchbox': ['numprops'],
            'colorpicker': ['ncolors'],
            'hlist': ['hlist'],
            'radio': ['selection'],
            'interval': ['duration']
        }

        props = []
        for property in salsah_restype_info[restype_id]['properties']:
            if property['name'] == '__location__':
                continue
            prop = {
                'name': property['name'],
                'labels': dict(map(lambda a: (a['shortname'], a['label']), property['label'])),
            }
            if property.get('description') is not None:
                prop['comments']: dict(map(lambda a: (a['shortname'], a['label']), property['description']))

            #
            # convert atriibutes into dict
            #
            attrdict = {}
            if property.get('attributes') is not None:
                attributes = property['attributes'].split(';')
                for attribute in attributes:
                    if attribute:
                        (key, val) = attribute.split('=')
                        attrdict[key] = val

            if property['vocabulary'] == 'salsah':
                if property['name'] == 'color':
                    knora_super = ['hasColor']
                    knora_object = 'ColorValue'
                elif property['name'] == 'comment' or property['name'] == 'comment_rt':
                    knora_super = ['hasComment']
                    knora_object = 'TextValue'
                elif property['name'] == 'external_id':
                    # ToDo: implement external_id
                    raise SalsahError("SALSAH-ERROR:\n\"external_id\" NYI!!")
                elif property['name'] == 'external_provider':
                    # ToDo: implement external_provider
                    raise SalsahError("SALSAH-ERROR:\n\"external_provider\" NYI!!")
                elif property['name'] == 'geometry':
                    knora_super = ['hasGeometry']
                    knora_object = 'GeomValue'
                elif property['name'] == 'part_of':
                    knora_super = ['isPartOf']
                    knora_object = 'Resource--FixMe'
                elif property['name'] == 'region_of':
                    knora_super = ['isRegionOf']
                    knora_object = 'Resource--FixMe'
                elif property['name'] == 'resource_reference':
                    knora_super = ['hasLinkTo']
                    knora_object = 'Resource--FixMe'
                elif property['name'] == 'interval':
                    knora_super = ['hasValue']
                    knora_object = 'IntervalValue'
                elif property['name'] == 'time':
                    # ToDo: implement TimeValue in knora-base
                    raise SalsahError("SALSAH-ERROR:\n\"TimeValue\" NYI!!")
                elif property['name'] == 'seqnum':
                    knora_super = ['seqnum']
                    knora_object = 'IntValue'
                elif property['name'] == 'sequence_of':
                    knora_super = ['isPartOf']
                    knora_object = 'Resource--FixMe'
                elif property['name'] == 'uri':
                    knora_super = ['hasValue']
                    knora_object = 'UriValue'
                else:
                    knora_super = ['hasValue']
                    knora_object = 'TextValue'
            elif property['vocabulary'] == 'dc':
                knora_super = ['hasValue', 'dc:' + property['name'] if property['name'] != 'description_rt' else 'dc:description']
                knora_object = 'TextValue'
            elif property['vocabulary'] == vocname:
                if property['vt_php_constant'] == 'VALTYPE_TEXT':
                    knora_super = ['hasValue']
                    knora_object = 'TextValue'
                elif property['vt_php_constant'] == 'VALTYPE_INTEGER':
                    knora_super = ['hasValue']
                    knora_object = 'IntValue'
                elif property['vt_php_constant'] == 'VALTYPE_FLOAT':
                    knora_super = ['hasValue']
                    knora_object = 'DecimalValue'
                elif property['vt_php_constant'] == 'VALTYPE_DATE':
                    knora_super = ['hasValue']
                    knora_object = 'DateValue'
                elif property['vt_php_constant'] == 'VALTYPE_PERIOD':
                    knora_super = ['hasValue']
                    knora_object = 'DateValue'
                elif property['vt_php_constant'] == 'VALTYPE_RESPTR':
                    knora_super = ['hasLinkTo']
                    knora_object = None
                    if attrdict.get('restypeid') is None:
                        pprint(property)
                        raise SalsahError("SALSAH-ERROR:\n\"Attribute \"restypeid\" not existing!")
                    else:
                        if salsah_restype_info.get(attrdict['restypeid']) is None:
                            pprint(property)
                            raise SalsahError("SALSAH-ERROR:\n\"restypeid\" is missing!")
                        knora_object = salsah_restype_info[attrdict['restypeid']]['name']
                    if knora_object is None:
                        knora_object = 'Resource'
                elif property['vt_php_constant'] == 'VALTYPE_SELECTION':
                    knora_super = ['hasValue']
                    knora_object = 'ListValue'
                elif property['vt_php_constant'] == 'VALTYPE_TIME':
                    knora_super = ['hasValue']
                    knora_object = 'TimeValue'
                elif property['vt_php_constant'] == 'VALTYPE_INTERVAL':
                    knora_super = ['hasValue']
                    knora_object = 'IntervalValue'
                elif property['vt_php_constant'] == 'VALTYPE_GEOMETRY':
                    knora_super = ['hasValue']
                    knora_object = 'GeomValue'
                elif property['vt_php_constant'] == 'VALTYPE_COLOR':
                    knora_super = ['hasValue']
                    knora_object = 'ColorValue'
                elif property['vt_php_constant'] == 'VALTYPE_HLIST':
                    knora_super = ['hasValue']
                    knora_object = 'ListValue'
                elif property['vt_php_constant'] == 'VALTYPE_ICONCLASS':
                    knora_super = ['hasValue']
                    knora_object = 'TextValue'
                elif property['vt_php_constant'] == 'VALTYPE_RICHTEXT':
                    knora_super = ['hasValue']
                    knora_object = 'TextValue'
                elif property['vt_php_constant'] == 'VALTYPE_GEONAME':
                    knora_super = ['hasValue']
                    knora_object = 'GeonameValue'
                else:
                    raise SalsahError(
                        "SALSAH-ERROR:\n\"Invalid vocabulary used: " + property['vocabulary'] + " by property " +
                        property['name'])
            else:
                raise SalsahError(
                    "SALSAH-ERROR:\n\"Invalid vocabulary used: " + property['vocabulary'] + " by property " +
                    property['name'])

            gui_attributes = []
            if property['gui_name'] == 'text':
                gui_element = 'SimpleText'
                for attr in gui_attr_lut['text']:
                    if attrdict.get(attr):
                        gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'textarea':
                gui_element = 'Textarea'
                for attr in gui_attr_lut['textarea']:
                    if attrdict.get(attr):
                        gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'pulldown':
                gui_element = 'Pulldown'
                for attr in gui_attr_lut['pulldown']:
                    if attrdict.get(attr) and attr == 'selection':
                        gui_attributes.append(attr + '=' + self.selection_mapping[attrdict[attr]])
            elif property['gui_name'] == 'slider':
                gui_element = 'Slider'
                for attr in gui_attr_lut['slider']:
                    if attrdict.get(attr):
                        gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'spinbox':
                gui_element = 'Spinbox'
            elif property['gui_name'] == 'searchbox':
                gui_element = 'Searchbox'
                for attr in gui_attr_lut['searchbox']:
                    if attrdict.get(attr):
                        gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'date':
                gui_element = 'Date'
            elif property['gui_name'] == 'geometry':
                gui_element = 'Geometry'
            elif property['gui_name'] == 'colorpicker':
                gui_element = 'Colorpicker'
                for attr in gui_attr_lut['colorpicker']:
                    if attrdict.get(attr):
                        gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'hlist':
                gui_element = 'List'
                for attr in gui_attr_lut['hlist']:
                    if attrdict.get(attr) and attr == 'hlist':
                        gui_attributes.append(attr + '=' + self.hlist_mapping[attrdict[attr]])
            elif property['gui_name'] == 'radio':
                gui_element = 'Radio'
                for attr in gui_attr_lut['pulldown']:
                    if attrdict.get(attr) and attr == 'selection':
                        gui_attributes.append(attr + '=' + self.selection_mapping[attrdict[attr]])
            elif property['gui_name'] == 'richtext':
                gui_element = 'Richtext'
            elif property['gui_name'] == 'time':
                gui_element = 'Time'
            elif property['gui_name'] == 'interval':
                gui_element = 'Interval'
                for attr in gui_attr_lut['interval']:
                    if attrdict.get(attr):
                        gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'geoname':
                gui_element = 'Geonames'
            else:
                raise SalsahError(
                    "SALSAH-ERROR:\n\"Invalid gui_element: " + property['gui_name'] + " by property " +
                    property['name'])

            prop['super'] = knora_super
            prop['object'] = knora_object
            prop['gui_element'] = gui_element
            if len(gui_element) > 0:
                prop['gui_attributes'] = gui_attributes
            prop['cardinality'] = property['occurrence']

            props.append(prop)
        return props

    def get_resourcetypes_of_vocabulary(self, vocname, session: requests.Session):
        """
        Fetches Ressourcetypes and returns restypes
        """
        payload: dict = {
            'vocabulary': vocname,
            'lang': 'all'
        }
        req = session.get(self.server + '/api/resourcetypes/', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])

        restype_ids: list = list(map(lambda r: r['id'], result['resourcetypes']))

        salsah_restype_info: dict = {}
        for restype_id in restype_ids:
            payload: dict = {
                'lang': 'all'
            }
            req = session.get(self.server + '/api/resourcetypes/' + restype_id, params=payload, auth=(self.user, self.password))
            result = req.json()
            if result['status'] != 0:
                raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
            salsah_restype_info[restype_id] = result['restype_info']


        restypes_container: list = []
        for restype_id in restype_ids:
            restype_info = salsah_restype_info[restype_id]
            (voc, name) = restype_info['name'].split(':')
            if voc != vocname:
                raise SalsahError("SALSAH-ERROR:\nresourcetype from other vocabulary! " + restype_info['name'])
            super = ''
            if restype_info['class'] == 'object':
                super = 'Resource'
            elif restype_info['class'] == 'image':
                super = 'StillImageRepresentation'
            elif restype_info['class'] == 'movie':
                super = 'MovingImageRepresentation'
            else:
                raise SalsahError("SALSAH-ERROR:\nResource class not supported! " + restype_info['name'])

            labels = dict(map(lambda a: (a['shortname'], a['label']), restype_info['label']))

            restype = {
                'name': name,
                'super': super,
                'labels': labels
            }

            if restype_info.get('description') is not None:
                comments = dict(map(lambda a: (a['shortname'], a['description']), restype_info['description']))
                restype['comments'] = comments

            # if restype_info.get('iconsrc') is not None:
            #     restype['iconsrc'] = self.get_icon(restype_info['iconsrc'], restype_info['name'])

            restype['properties'] = self.get_properties_of_resourcetype(vocname, restype_id, salsah_restype_info)

            restypes_container.append(restype)
        return restypes_container

    def get_selections_of_vocabulary(self, vocname: str, session: requests.Session):
        """
        Get the selections and hlists. In knora, there are only herarchical lists! A selection is
        just a hierarchical list without children...

        :param vocname: Vocabulary name
        :param session: Session object
        :return: Python list of salsah selections and hlists as knora lists
        """
        #
        # first we get the flat lists (selctions)
        #
        payload = {
            'vocabulary': vocname,
            'lang': 'all'
        }
        req = session.get(self.server + '/api/selections', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])

        selections = result['selections']

        # Let's make an empty list for the lists:
        selections_container = []

        for selection in selections:
            self.selection_mapping[selection['id']] = selection['name']
            root = {
                'name': selection['name'],
                'labels': dict(map(lambda a: (a['shortname'], a['label']), selection['label']))
            }
            if selection.get('description') is not None:
                root['comments'] = dict(map(lambda a: (a['shortname'], a['description']), selection['description']))
            payload = {'lang': 'all'}
            req_nodes = session.get(self.server + '/api/selections/' + selection['id'], params=payload, auth=(self.user, self.password))
            result_nodes = req_nodes.json()
            if result_nodes['status'] != 0:
                raise SalsahError("SALSAH-ERROR:\n" + result_nodes['errormsg'])
            root['nodes'] = list(map(lambda a: {
                'name': a['name'],
                'labels': a['label']
            }, result_nodes['selection']))
            selections_container.append(root)

        #
        # now we get the hierarchical lists (hlists)
        #
        payload = {
            'vocabulary': vocname,
            'lang': 'all'
        }
        req = session.get(self.server + '/api/hlists', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])

        hlists = result['hlists']

        #
        # this is a helper function for easy recursion
        #
        def process_children(children: list) -> list:
            newnodes = []
            for node in children:
                newnode = {
                    'name': node['name'],
                    'labels': dict(map(lambda a: (a['shortname'], a['label']), node['label']))
                }
                if node.get('children') is not None:
                    newnode['nodes'] = process_children(node['children'])
                newnodes.append(newnode)
            return newnodes

        for hlist in hlists:
            root = {
                'name': hlist['name'],
                'labels': dict(map(lambda a: (a['shortname'], a['label']), hlist['label']))
            }
            self.hlist_mapping[hlist['id']] = hlist['name']
            if hlist.get('description') is not None:
                root['comments'] = dict(map(lambda a: (a['shortname'], a['description']), hlist['description']))
            payload = {'lang': 'all'}
            req_nodes = session.get(self.server + '/api/hlists/' + hlist['id'], params=payload, auth=(self.user, self.password))
            result_nodes = req_nodes.json()
            if result_nodes['status'] != 0:
                raise SalsahError("SALSAH-ERROR:\n" + result_nodes['errormsg'])
            root['nodes'] = process_children(result_nodes['hlist'])
            selections_container.append(root)

        return selections_container

    def get_all_obj_ids(self, project: str, session, start_at: int = 0, show_nrows:int = -1):
        """
        Get all resource id's from project
        :param project: Project name
        :param start_at: Start at given resource
        :param show_nrows: Show n resources
        :return:
        """
        payload = {
            'searchtype' : 'extended',
            'filter_by_project': project
        }
        if nrows > 0:
            payload['show_nrows'] = show_nrows
            payload['start_at'] = start_at

        req = session.get(self.server + '/api/search/', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        else:
            nhits = result['nhits']
            obj_ids = list(map(lambda a: a['obj_id'], result['subjects']))
            return (nhits, obj_ids)

    def get_resource(self, res_id: int, verbose: bool = True) -> Dict:
        req = session.get(self.server + '/api/resources/' + res_id, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        else:
            return result

    def write_json(self, filename, proj: Dict):
        """
        We send the dict to JSON and write it to the project-folder
        """
        self.filename = filename
        pro_cont =json.dumps(proj, indent=4)                                            #
        f = open(self.filename, "w")
        f.write(pro_cont)
        f.close()

class XmlBuilder:

    """
    In der Funktion process_vocabulary() werden assets auf das Filesystem ge-
    schrieben. Ich habe den Teil, der das Vocabulary nach XML schreibt, aus-
    kommentiert.
    Ein Teil muss noch in die Json Funktionalität übernommen werden:
    : Assets (va. die Icons) auf das Filesystem schreiben
    : In das JSON File übernehmen, damit sie referenziert sind...
    Das ist redundant...
    """

    def __init__(self, filename, session) -> None:
        super().__init__()
        self.filename = filename
        self.root = etree.Element('salsah');
        self.mime = magic.Magic(mime=True)
        self.session = session



    #def process_vocabulary(self, session, voc: dict) -> None:
    #"""
    #Diese Fuktion umschreiben für Ausgabe von JSON
    #"""
    #    vocnode = etree.Element('vocabulary', {'id': voc['id'], 'shortname': voc['shortname']})
    #    longname = etree.Element('longname')
    #    longname.text = voc['longname']
    #    vocnode.append(longname)
    #    description = etree.Element('description')
    #    description.text = voc['description']
    #    vocnode.append(description)
    #    restypes_node = etree.Element('restypes')
    #    for restype in voc['restypes']:
    #        print("Restype: ", restype)
    #        restypes_node.append(self.process_restype(session, restype))            # process_restype()
    #    vocnode.append(restypes_node)
    #    self.root.append(vocnode)

    #def process_restype(self, session, restype: dict):
    #    """
    #    Diese Fuktion umschreiben für Ausgabe von JSON
    #    :Nur lassen was es für die Assets braucht...

    #    """
    #    restype_node = etree.Element('resource_type', {'name': restype['name'], 'label': restype['label']})
    #    if restype.get('description') is not None:
    #        description_node = etree.Element('description')
    #        description_node.text = restype['description']
    #        restype_node.append(description_node)
    #    if restype.get('iconsrc') is not None:
    #        iconsrc = restype['iconsrc']
    #        print("Iconsrc:", iconsrc)
    #        iconpath = os.path.join(assets_path, restype['name'])
    #        dlfile = session.get(restype['iconsrc'], stream=True )                  # war urlretrieve()
    #        with open(iconpath, 'w+b') as fd:
    #            for chunk in dlfile.iter_content(chunk_size=128):
    #                fd.write(chunk)
    #            fd.close()

    #        mimetype = self.mime.from_file(iconpath)
    #        if mimetype == 'image/gif':
    #            ext = '.gif'
    #        elif mimetype == 'image/png':
    #            ext = '.png'
    #        elif mimetype == 'image/svg+xml':
    #            ext = '.svg'
    #        elif mimetype == 'image/jpeg':
    #            ext = '.jpg'
    #        elif mimetype == 'image/tiff':
    #            ext = '.tif'
    #        else:
    #            ext = '.img'
    #        os.rename(iconpath, iconpath + ext)

    #        iconsrc_node = etree.Element('iconsrc', {'file': iconpath + ext})
    #        restype_node.append(iconsrc_node)
    #        for proptype in restype['properties']:
    #            restype_node.append(self.process_proptype(proptype))                # process_proptype()

    #    return restype_node                                                         # Das geht alles in Vocabulary...

    def process_proptype(self, proptype: dict):
        proptype_node = etree.Element('property_type', {
            'name': proptype['vocabulary'] + ':' + proptype['name'],
            'label': proptype['label']
        })
        etree.SubElement(proptype_node, 'occurrence', {'value': str(proptype['occurrence'])})
        if proptype.get('vt_name') is not None:
            etree.SubElement(proptype_node, 'valuetype', {'value': proptype['vt_name']})
        if proptype.get('gui_attributes') is not None:
            etree.SubElement(proptype_node, 'gui_name', {'gui_attributes': proptype['gui_attributes']})
        if proptype.get('description') is not None:
            description_node = etree.Element('description')
            description_node.text = proptype['description']
            proptype_node.append(description_node)
        return proptype_node                                                        # Das geht auch ins Vocabulary

    def process_value(self, valtype: str, value: any):
        if int(valtype) == Valtype.TEXT.value:
            valele = etree.Element('value', {'type': 'text'})
            valele.text = value
        elif int(valtype) == Valtype.RICHTEXT.value:
            valele = etree.Element('value', {'type': 'richtext'})
            subele = etree.Element('utf8str')
            subele.text = value['utf8str']
            valele.append(subele)
            subele = etree.Element('textattr')
            subele.text = value['textattr']
            for resref in value['resource_reference']:
                etree.SubElement(subele, "resref", {"id": resref})
            valele.append(subele)
        elif int(valtype) == Valtype.COLOR.value:
            valele = etree.Element('value', {'type': 'color'})
            valele.text = value
        elif int(valtype) == Valtype.DATE.value:
            valele = etree.Element('value', {'type': 'date'})
            pass
        elif int(valtype) == Valtype.FLOAT.value:
            valele = etree.Element('value', {'type': 'float'})
            valele.text = value
        elif int(valtype) == Valtype.GEOMETRY.value:
            valele = etree.Element('value', {'type': 'geometry'})
            valele.text = value
        elif int(valtype) == Valtype.GEONAME.value:
            valele = etree.Element('value', {'type': 'geoname'})
            valele.text = value
        elif int(valtype) == Valtype.HLIST.value:
            valele = etree.Element('value', {'type': 'hlist'})
            valele.text = value
        elif int(valtype) == Valtype.ICONCLASS.value:
            valele = etree.Element('value', {'type': 'iconclass'})
            valele.text = value
        elif int(valtype) == Valtype.INTEGER.value:
            valele = etree.Element('value', {'type': 'integer'})
            valele.text = value
        elif int(valtype) == Valtype.INTERVAL.value:
            valele = etree.Element('value', {'type': 'interval'})
            valele.text = value
        elif int(valtype) == Valtype.PERIOD.value:
            valele = etree.Element('value', {'type': 'period'})
            pass
        elif int(valtype) == Valtype.RESPTR.value:
            valele = etree.Element('value', {'type': 'resptr'})
            valele.text = value
        elif int(valtype) == Valtype.SELECTION.value:
            valele = etree.Element('value', {'type': 'selection'})
            valele.text = value
            pass
        elif int(valtype) == Valtype.TIME.value:
            valele = etree.Element('value', {'type': 'time'})
            valele.text = value
        elif int(valtype) == -1:
            valele = etree.Element('value', {'type': 'image'})
        else:
            print('===========================')
            pprint(value)
            print('----------------------------')
            valele = etree.Element('value', {'type': valtype})
        return valele                                                               # Das geht in die Resourcen

    def process_property(self, propname: str, property: Dict):
        if propname == '__location__':
            return None
        if property.get("values") is not None:
            propnode = etree.Element('property', {'name': propname, 'label': '' if property.get('label') is None else property['label']})
            for value in property["values"]:
                propnode.append(self.process_value(property["valuetype_id"], value))        # process_value()
            return propnode                                                             # Das geht in die Resourcen
        else:
            return None

    def process_resource(self, session, resource: Dict):
        resnode = etree.Element('resource', {
            'restype': resource["resinfo"]["restype_name"],
            'resid': resource["resdata"]["res_id"]
        })
        if resource["resinfo"].get('locdata') is not None:
            imgpath = os.path.join(images_path, resource["resinfo"]['locdata']['origname'])
            getter = resource["resinfo"]['locdata']['path'] + '&format=tif'     # Was wenn es nur ein JPEG gibt?
            print('Downloading ' + resource["resinfo"]['locdata']['origname'] + '...')
            dlfile2 = session.get(getter, stream=True )     # war urlretrieve()

            with open(imgpath, 'w+b') as fd:
                for chunk in dlfile2.iter_content(chunk_size=128):
                    fd.write(chunk)
                fd.close()

            image_node = etree.Element('image')
            image_node.text = imgpath
            resnode.append(image_node)

        for propname in resource["props"]:
            propnode = self.process_property(propname, resource["props"][propname])     # process_property()
            if propnode is not None:
                resnode.append(propnode)
        self.root.append(resnode)                                                   # Das geht in die Resourcen

    def write_xml(self):
        f = open(self.filename, "wb")
        f.write(etree.tostring(self.root, pretty_print=True, xml_declaration=True, encoding='utf-8'))
        f.close()


parser = argparse.ArgumentParser()
parser.add_argument("server", help="URL of the SALSAH server")
parser.add_argument("-u", "--user", help="Username for SALSAH")
parser.add_argument("-p", "--password", help="The password for login")
parser.add_argument("-P", "--project", help="Shortname or ID of project")
parser.add_argument("-n", "--nrows", type=int, help="number of records to get, -1 to get all")
parser.add_argument("-s", "--start", type=int, help="Start at record with given number")
parser.add_argument("-F", "--folder", default="-", help="Output folder")

args = parser.parse_args()

user = 'root' if args.user is None else args.user
password = 'SieuPfa15' if args.password is None else args.password
start = args.start;
nrows = -1 if args.nrows is None else args.nrows
project = args.project

if args.folder == '-':
    folder = args.project + ".dir"
else:
    folder = args.folder

assets_path = os.path.join(folder, 'assets')
images_path = os.path.join(folder, 'images')
outfile_path = os.path.join(folder, project + '.xml')
j_outfile_path = os.path.join(folder, project + '.json')
try:
    os.mkdir(folder)
    os.mkdir(assets_path)
    os.mkdir(images_path)
except OSError:
    print("Could'nt create necessary folders")
    exit(2)

# Define session
session = requests.Session()
session.verify = False                      # Works...



"""
Call functions to write project ontology to JSON
Append stuff and write JSON file
: To Do:
: - hlists (postcard hasn't any)
: - Write assets to file system and put them to the ontology...
"""
con = Salsah(args.server, user, password, session)
proj = con.get_project(project, '0804', session)
# proj['project']['ontology'].update({'resources': con.get_resourcetypes_of_vocabulary(proj['project']['shortname'], session)})

con.write_json(j_outfile_path, proj)

(nhits, res_ids) = con.get_all_obj_ids(project, session, start, nrows)
print("nhits=", nhits)
print("Got all resource id's")

"""
Write resources to xml
"""
resources = list(map(con.get_resource, res_ids))

xml = XmlBuilder(outfile_path, session)

for resource in resources:
    xml.process_resource(session, resource)

xml.write_xml()

print(outfile_path + ' and ' + j_outfile_path + ' written...')
#print(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='utf-8'))
