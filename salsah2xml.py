from typing import List, Set, Dict, Tuple, Optional
import os
from lxml import etree
from pathlib import Path
import requests
import argparse
from enum import Enum
import base64
from pprint import pprint
import magic
import json
import jdcal
import shutil
import sys

requests.urllib3.disable_warnings(requests.urllib3.exceptions.InsecureRequestWarning)


Valtype = {
    '1': 'text',
    '2': 'integer',
    '3': 'float',
    '4': 'date',
    '5': 'period',
    '6': 'resptr',
    '7': 'selection',
    '8': 'time',
    '9': 'interval',
    '10': 'geometry',
    '11': 'color',
    '12': 'hlist',
    '13': 'iconclass',
    '14': 'richtext',
    '15': 'geoname'
}

class ValtypeMap(Enum):
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

stags = {
    '_link': ['<a href="{}">', '<a class="salsah-link" href="IRI:{}:IRI">'],
    'bold': '<strong>',
    'strong': '<strong>',
    'underline': '<u>',
    'italic': '<em>',
    'linebreak': '<br/>',
    'strikethrough': '<strike>',
    'style': '<span gaga={}>',
    'ol': '<ol>',
    'ul': '<ul>',
    'li': '<li>',
    'sup': '<sup>',
    'sub': '<sub>',
    'p': '<p>',
    'h1': '<h1>',
    'h2': '<h2>',
    'h3': '<h3>',
    'h4': '<h4>',
    'h5': '<h5>',
    'h6': '<h6>',
}

etags = {
    '_link': '</a>',
    'bold': '</strong>',
    'strong': '</strong>',
    'underline': '</u>',
    'italic': '</em>',
    'linebreak': '',
    'strikethrough': '<strike>',
    'style': '</span',
    'ol': '</ol>',
    'ul': '</ul>',
    'li': '</li>',
    'sup': '</sup>',
    'sub': '</sub>',
    'p': '</p>',
    'h1': '</h1>',
    'h2': '</h2>',
    'h3': '</h3>',
    'h4': '</h4>',
    'h5': '</h5>',
    'h6': '</h6>',
}


def process_richtext(utf8str: str, textattr: str = None, resptrs: list = []) -> str:

    if textattr is not None:
        attributes = json.loads(textattr)
        attrlist = []
        result = ''
        for key, vals in attributes.items():
            for val in vals:
                attr = {}
                attr['tagname'] = key
                attr['type'] = 'start'
                attr['pos'] = int(val['start'])
                if val.get('href'):
                    attr['href'] = val['href']
                if val.get('resid'):
                    attr['resid'] = val['resid']
                if val.get('style'):
                    attr['style'] = val['style']
                attrlist.append(attr)
                attr = {}
                attr['tagname'] = key
                attr['type'] = 'end'
                attr['pos'] = val['end']
                attrlist.append(attr)
        attrlist = sorted(attrlist, key=lambda attr: attr['pos'])
        pos: int = 0
        stack = []
        for attr in attrlist:
            result += utf8str[pos:attr['pos']]
            if attr['type'] == 'start':
                if attr['tagname'] == '_link':
                    if attr.get('resid')is not None:
                        result += stags[attr['tagname']][1].format(attr['resid'])
                    else:
                        result += stags[attr['tagname']][0].format(attr['href'])
                else:
                    result += stags[attr['tagname']]
                stack.append(attr)
            elif attr['type'] == 'end':
                match = False
                tmpstack = []
                while True:
                    tmp = stack.pop()
                    result += etags[tmp['tagname']]
                    if tmp['tagname'] == attr['tagname'] and tmp['type'] == 'start':
                        match = True
                        break
                    else:
                        tmpstack.append(tmp)
                while len(tmpstack) > 0:
                    tmp = tmpstack.pop()
                    result += stags[tmp['tagname']]
                    stack.append(tmp)
            pos = attr['pos']
        return base64.b64encode(result.encode())
    else:
        return base64.b64encode(utf8str.encode())



class Richtext:

    def __init__(self) -> None:
        super().__init__()


class SalsahError(Exception):
    """Handles errors happening in this file"""

    def __init__(self, message: str) -> None:
        self.message = message


class Salsah:
    def __init__(
            self,
            server: str,
            user: str,
            password: str,
            filename: str,
            projectname: str,
            shortcode: str,
            resptrs: dict,
            session: requests.Session) -> None:
        """

        :param server: Server of old SALSAH (local or http://salsah.org)
        :param user: User for login to old SALSAH server
        :param password: Password for login to old SALSAH server
        :param filename:
        :param projectname: Name of the project to dump
        :param shortcode: Shortcode for Knora that is reserved for the project
        :param resptrs: XML file  containing  object information for resource pointer
        :param session: Session object
        """
        super().__init__()
        self.server: str = server
        self.user: str = user
        self.password: str = password
        self.filename = filename
        self.projectname = projectname
        self.shortcode = shortcode
        self.resptrs = resptrs
        self.session: requests.Session = session

        self.mime = magic.Magic(mime=True)
        self.selection_mapping: Dict[str,str] = {}
        self.selection_node_mapping: Dict[str, str] = {}
        self.hlist_mapping: Dict[str, str] = {}
        self.hlist_node_mapping: Dict[str, str] = {}
        self.vocabulary: str = ""

        self.root = etree.Element('salsah');
        self.mime = magic.Magic(mime=True)
        self.session = session

    def get_icon(self, iconsrc: str, name: str) -> str:
        """
        Get an icon from old SALSAH
        :param iconsrc: URL for icon in old SALSAH
        :param name: nameof the icon
        :return: Path to the icon on local disk
        """
        iconpath: str = os.path.join(assets_path, name)
        dlfile: str = session.get(iconsrc, stream=True)  # war urlretrieve()
        with open(iconpath, 'w+b') as fd:
            for chunk in dlfile.iter_content(chunk_size=128):
                fd.write(chunk)
            fd.close()

        mimetype: str = self.mime.from_file(iconpath)
        ext: str
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

    def get_project(self) -> dict:
        """
        Get project info
        :return: Project information that can be dumped as json for knora-create-ontology"
        """
        #
        # first get all system ontologies
        #
        req = self.session.get(self.server + '/api/vocabularies/0?lang=all', auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        sysvocabularies = result['vocabularies']

        #
        # get project info
        #
        req = self.session.get(self.server + '/api/projects/' + self.projectname + "?lang=all", auth=(self.user, self.password) )
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])

        project_container = {
            "prefixes": dict(map(lambda a: (a['shortname'], a['uri']), sysvocabularies)),
            "project": {
                'shortcode': self.shortcode,
                'shortname': result['project_info']['shortname'],
                'longname': result['project_info']['longname'],
            },
        }
        project_info = result['project_info']           # Is this the project_container??? Decide later
        project = {
            'shortcode': self.shortcode,
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
        else:
            project['keywords'] = [result['project_info']['shortname']]

        #
        # Get the vocabulary. The old Salsah uses only one vocabulary per project....
        # Note: the API call always returns also the system vocabularies which we have to be excluded
        #
        req = self.session.get(self.server + '/api/vocabularies/' + self.projectname, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        vocabulary = None
        for voc in result['vocabularies']:
            if int(voc['project_id']) != 0:
                vocabulary = voc

        self.vocabulary = vocabulary['shortname']
        project['lists'] = self.get_selections_of_vocabulary(vocabulary['shortname'])
        self.root.set('vocabulary', vocabulary['shortname'])

        project['ontology'] = {
            'name': vocabulary['shortname'],
            'label': vocabulary['longname'],
        }
        #
        # ToDo: not yet implemented in create_ontology
        # if vocabulary.get('description') is not None and vocabulary['description']:
        #    project['ontology']['comment'] = vocabulary['description']

        project['ontology']['resources'] = self.get_resourcetypes_of_vocabulary(vocabulary['shortname'])
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
            if property['name'].startswith('has'):
                pname = property['name']
            else:
                pname = 'has' + property['name'].capitalize()
            prop = {
                'name': pname,
                'labels': dict(map(lambda a: (a['shortname'], a['label']), property['label'])),
            }
            if property.get('description') is not None:
                prop['comments']: dict(map(lambda a: (a['shortname'], a['label']), property['description']))

            #
            # convert atributes into dict
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
                    if self.resptrs.get(salsah_restype_info[restype_id]['name']) is not None:
                        tmp = self.resptrs[salsah_restype_info[restype_id]['name']]
                        if tmp.get('salsah:part_of') is not None:
                            knora_object = tmp['salsah:part_of']
                    else:
                        knora_object = 'FIXME--Resource--FIXME'
                        print("WARNING: Resclass {} has resptr {} with no object!".format(salsah_restype_info[restype_id]['name'], property['name']))
                elif property['name'] == 'region_of':
                    knora_super = ['isRegionOf']
                    if self.resptrs.get(salsah_restype_info[restype_id]['name']) is not None:
                        tmp = self.resptrs[salsah_restype_info[restype_id]['name']]
                        if tmp.get('salsah:region_of') is not None:
                            knora_object = tmp['salsah:part_of']
                    else:
                        knora_object = 'FIXME--Resource--FIXME'
                        print("WARNING: Resclass {} has resptr {} with no object!".format(salsah_restype_info[restype_id]['name'], property['name']))
                elif property['name'] == 'resource_reference':
                    knora_super = ['hasLinkTo']
                    if self.resptrs.get(salsah_restype_info[restype_id]['name']) is not None:
                        tmp = self.resptrs[salsah_restype_info[restype_id]['name']]
                        if tmp.get('salsah:resource_reference') is not None:
                            knora_object = tmp['salsah:part_of']
                    else:
                        knora_object = 'FIXME--Resource--FIXME'
                        print("WARNING: Resclass {} has resptr {} with no object!".format(salsah_restype_info[restype_id]['name'], property['name']))
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
                    if self.resptrs.get(salsah_restype_info[restype_id]['name']) is not None:
                        tmp = self.resptrs[salsah_restype_info[restype_id]['name']]
                        if tmp.get('salsah:resource_reference') is not None:
                            knora_object = tmp['salsah:part_of']
                    else:
                        knora_object = 'FIXME--Resource--FIXME'
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
                        tmp = self.resptrs[salsah_restype_info[restype_id]['name']]
                        if tmp.get('salsah:resource_reference') is not None:
                            knora_object = tmp[property['vocabulary'] + ':' + property['name']]
                    else:
                        if salsah_restype_info.get(attrdict['restypeid']) is None:
                            tmp = self.resptrs[salsah_restype_info[restype_id]['name']]
                            if tmp.get('salsah:resource_reference') is not None:
                                knora_object = tmp[property['vocabulary'] + ':' + property['name']]
                            raise SalsahError("SALSAH-ERROR:\n\"restypeid\" is missing!")
                        knora_object = salsah_restype_info[attrdict['restypeid']]['name']
                    if knora_object is None:
                        knora_object = 'FIXME--Resource--FIXME'
                        print("WARNING: Resclass {} has resptr {} with no object!".format(salsah_restype_info[restype_id]['name'], property['name']))
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
                        gui_attributes.append('hlist=' + self.selection_mapping[attrdict[attr]])
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
                        gui_attributes.append('hlist=' + self.selection_mapping[attrdict[attr]])
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

    def get_resourcetypes_of_vocabulary(self, vocname):
        """
        Fetches Ressourcetypes and returns restypes
        """
        payload: dict = {
            'vocabulary': vocname,
            'lang': 'all'
        }
        req = self.session.get(self.server + '/api/resourcetypes/', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])

        restype_ids: list = list(map(lambda r: r['id'], result['resourcetypes']))

        salsah_restype_info: dict = {}
        for restype_id in restype_ids:
            payload: dict = {
                'lang': 'all'
            }
            req = self.session.get(self.server + '/api/resourcetypes/' + restype_id, params=payload, auth=(self.user, self.password))
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
                'name': name.capitalize(),
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

    def get_selections_of_vocabulary(self, vocname: str):
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
        req = self.session.get(self.server + '/api/selections', params=payload, auth=(self.user, self.password))
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
            req_nodes = self.session.get(self.server + '/api/selections/' + selection['id'], params=payload, auth=(self.user, self.password))
            result_nodes = req_nodes.json()
            if result_nodes['status'] != 0:
                raise SalsahError("SALSAH-ERROR:\n" + result_nodes['errormsg'])
            self.selection_node_mapping.update(dict(map(lambda a: (a['id'], a['name']), result_nodes['selection'])))
            root['nodes'] = list(map(lambda a: {
                'name': 'S_' + a['id'],
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
        req = self.session.get(self.server + '/api/hlists', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        self.hlist_node_mapping.update(dict(map(lambda a: (a['id'], a['name']), result['hlists'])))

        hlists = result['hlists']

        #
        # this is a helper function for easy recursion
        #
        def process_children(children: list) -> list:
            newnodes = []
            for node in children:
                self.hlist_node_mapping[node['id']] = node['name']
                newnode = {
                    'name': 'H_' + node['id'],
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
            req_nodes = self.session.get(self.server + '/api/hlists/' + hlist['id'], params=payload, auth=(self.user, self.password))
            result_nodes = req_nodes.json()
            if result_nodes['status'] != 0:
                raise SalsahError("SALSAH-ERROR:\n" + result_nodes['errormsg'])
            root['nodes'] = process_children(result_nodes['hlist'])
            selections_container.append(root)

        return selections_container

    def get_all_obj_ids(self, project: str, start_at: int = 0, show_nrows:int = -1):
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
        if show_nrows > 0:
            payload['show_nrows'] = show_nrows
            payload['start_at'] = start_at

        req = self.session.get(self.server + '/api/search/', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        else:
            nhits = result['nhits']
            obj_ids = list(map(lambda a: a['obj_id'], result['subjects']))
            return (nhits, obj_ids)

    def get_resource(self, res_id: int, verbose: bool = True) -> Dict:
        payload = {
            'reqtype': 'info'
        }
        req = self.session.get(self.server + '/api/resources/' + res_id, params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        firstproperty = result['resource_info']['firstproperty']

        req = self.session.get(self.server + '/api/resources/' + res_id, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        result['firstproperty'] = firstproperty
        return result

    def write_json(self, proj: Dict):
        """
        We send the dict to JSON and write it to the project-folder
        """
        json_filename = self.filename + '.json'
        pro_cont =json.dumps(proj, indent=4)
        f = open(json_filename, "w")
        f.write(pro_cont)
        f.close()

    def process_value(self, valtype: int, value: any, comment: str = None):
        if comment is None:
            valele = etree.Element('value')
        else:
            valele = etree.Element('value', {'comment': comment})

        if valtype == ValtypeMap.TEXT.value:
            valele.text = value
            valele.set('encoding', 'utf8')
        elif valtype == ValtypeMap.RICHTEXT.value:
            resptrs = value['resource_reference']
            valele.text = process_richtext(
                utf8str=value.get('utf8str').strip(),
                textattr=value.get('textattr').strip(),
                resptrs=value.get('resptrs'))
            resrefs = '|'.join(value['resource_reference'])
            valele.set('resrefs', resrefs)
            valele.set('encoding', 'hex64')
        elif valtype == ValtypeMap.COLOR.value:
            valele.text = value
        elif valtype == ValtypeMap.DATE.value:
            cal: str
            start: Tuple[int, int, int, float]
            end: Tuple[int, int, int, float]
            if value['calendar'] == 'GREGORIAN':
                cal = 'GREGORIAN'
                start = jdcal.jd2gcal(float(value['dateval1']), 0.0)
                end = jdcal.jd2gcal(float(value['dateval2']), 0.0)
            else:
                cal = 'JULIAN'
                start = jdcal.jd2jcal(float(value['dateval1']), 0.0)
                end = jdcal.jd2jcal(float(value['dateval2']), 0.0)
            p1: str = 'CE'
            if start[0] <= 0:
                start[0] = start[0] - 1
                p1 = 'BCE'

            p2: str = 'CE'
            if end[0] <= 0:
                end[0] = end[0] - 1
                p2 = 'BCE'

            startstr: str = ""
            endstr: str = ""

            if value['dateprecision1'] == 'YEAR':
                startstr = "{}:{}:{:04d}".format(cal, p1, start[0])
            elif value['dateprecision1'] == 'MONTH':
                startstr = "{}:{}:{:04d}-{:02d}".format(cal, p1, start[0], start[1])
            else:
                startstr = "{}:{}:{:04d}-{:02d}-{:02d}".format(cal, p1, start[0], start[1], start[2])

            if value['dateprecision2'] == 'YEAR':
                if start[0] != end[0]:
                    endstr = ":{}:{:04d}".format(p2, end[0])
            elif value['dateprecision2'] == 'MONTH':
                if start[0] != end[0] or start[1] != end[1]:
                    endstr = ":{}:{:04d}-{:02d}".format(p2, end[0], end[1])
            else:
                if start[0] != end[0] or start[1] != end[1] or start[2] != end[2]:
                    endstr = ":{}:{:04d}-{:02d}-{:02d}".format(p2, end[0], end[1], end[2])

            valele.text = startstr + endstr
        elif valtype == ValtypeMap.FLOAT.value:
            valele.text = value
        elif valtype == ValtypeMap.GEOMETRY.value:
            valele.text = value
        elif valtype == ValtypeMap.GEONAME.value:
            valele.text = value
        elif valtype ==ValtypeMap.HLIST.value:
            valele.text = 'H_' + value
            pass
        elif valtype == ValtypeMap.ICONCLASS.value:
            valele.text = value
        elif valtype == ValtypeMap.INTEGER.value:
            valele.text = value
        elif valtype == ValtypeMap.INTERVAL.value:
            valele.text = value
        elif valtype == ValtypeMap.PERIOD.value:
            pass
        elif valtype ==ValtypeMap.RESPTR.value:
            valele.text = value
        elif valtype == ValtypeMap.SELECTION.value:
            valele.text = 'S_' + value
        elif valtype == ValtypeMap.TIME.value:
            valele.text = value
        else:
            print('===========================')
            pprint(value)
            print('----------------------------')
        return valele                                                               # Das geht in die Resourcen

    def process_property(self, propname: str, property: Dict):
        if propname == '__location__':
            return None
        if property.get("values") is not None:
            #
            # first we strip the vocabulary off, if it's not salsah, dc, etc.
            #
            tmp = propname.split(':')
            if tmp[0] == self.vocabulary:
                propname_new = tmp[1]  # strip vocabulary
                #
                # if the propname does not start with "has", add  it to the propname. We have to do this
                # to avoid naming conflicts between resourcesand  properties which share the same
                # namespace in GraphDB
                #
                if not propname_new.startswith('has'):
                    propname_new = 'has' + propname_new.capitalize()
            else:
                propname_new = propname
            options: Dict[str, str] = {
                'name': propname_new,
                'type': Valtype.get(property["valuetype_id"])
            }
            if int(property["valuetype_id"]) == ValtypeMap.SELECTION.value:
                (dummy, sel_id) = property['attributes'].split("=")
                options['selection'] = self.selection_mapping[sel_id]
            elif int(property["valuetype_id"]) == ValtypeMap.HLIST.value:
                (dummy, hlist_id) = property['attributes'].split("=")
                options['hlist'] = self.hlist_mapping[hlist_id]
            propnode = etree.Element('property', options)
            cnt: int = 0
            for value in property["values"]:
                if property['comments'][cnt]:
                    propnode.append(self.process_value(int(property["valuetype_id"]), value, property['comments'][cnt]))
                    pass
                else:
                    propnode.append(self.process_value(int(property["valuetype_id"]), value))
                cnt += 1
            return propnode
        else:
            return None

    def process_resource(self, resource: Dict, images_path: str, download: bool = True, verbose: bool = True):
        tmp = resource["resdata"]["restype_name"].split(':')
        if tmp[0] == self.vocabulary:
            restype = tmp[1].capitalize()
        else:
            restype = resource["resdata"]["restype_name"]
        resnode = etree.Element('resource', {
            'restype': restype,
            'unique_id': resource["resdata"]["res_id"],
            'label': resource['firstproperty']
        })
        if resource["resinfo"].get('locdata') is not None:
            imgpath = os.path.join(images_path, resource["resinfo"]['locdata']['origname'])
            ext = os.path.splitext(resource["resinfo"]['locdata']['origname'])[1][1:].strip().lower()
            if ext == 'jpg' or ext == 'jpeg':
                format = 'jpg'
            elif ext == 'png':
                format = 'png'
            elif ext == 'jp2' or ext == 'jpx':
                format = 'jpx'
            else:
                format = 'tif'
            getter = resource["resinfo"]['locdata']['path'] + '&format=' + format
            if download:
                print('Downloading ' + resource["resinfo"]['locdata']['origname'] + '...')
                dlfile2 = self.session.get(getter, stream=True)     # war urlretrieve()

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
        print('Resource added. Id=' + resource["resdata"]["res_id"], flush=True)

    def write_xml(self):
        xml_filename = self.filename + '.xml'
        f = open(xml_filename, "wb")
        f.write(etree.tostring(self.root, pretty_print=True, xml_declaration=True, encoding='utf-8'))
        f.close()

def program(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("server", help="URL of the SALSAH server")
    parser.add_argument("-u", "--user", help="Username for SALSAH")
    parser.add_argument("-p", "--password", help="The password for login")
    parser.add_argument("-P", "--project", help="Shortname or ID of project")
    parser.add_argument("-s", "--shortcode", help="Knora-shortcode  of project")
    parser.add_argument("-n", "--nrows", type=int, help="number of records to get, -1 to get all")
    parser.add_argument("-S", "--start", type=int, help="Start at record with given number")
    parser.add_argument("-F", "--folder", default="-", help="Output folder")
    parser.add_argument("-r", "--resptrs_file", help="list of resptrs targets")
    parser.add_argument("-d", "--download", action="store_true", help="Download  image files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose feedback")

    args = parser.parse_args()

    if args.shortcode is None:
        print("You must give a shortcode (\"--shortcode XXXX\")!")
        exit(1)

    user = 'root' if args.user is None else args.user
    password = 'SieuPfa15' if args.password is None else args.password
    start = args.start;
    nrows = -1 if args.nrows is None else args.nrows
    project = args.project

    # page@salsah:partof=book;…

    resptrs: dict = {}
    if args.resptrs_file is not None:
        tree = etree.parse(args.resptrs_file)
        root = tree.getroot()
        for restype in root:
            restype_name = restype.attrib["name"].strip()
            props: dict = {}
            for prop in restype:
                props[prop.attrib["name"]] = prop.text.strip()
            resptrs[restype.attrib["name"]] = props


    if args.folder == '-':
        folder = args.project + ".dir"
    else:
        folder = args.folder

    assets_path = os.path.join(folder, 'assets')
    images_path = os.path.join(folder, 'images')
    outfile_path = os.path.join(folder, project)

    if os.path.exists(folder):
        shutil.rmtree(folder)
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

    con = Salsah(server=args.server, user=user, password=password, filename=outfile_path,
                projectname=args.project, shortcode=args.shortcode, resptrs=resptrs, session=session)
    proj = con.get_project()
    # proj['project']['ontology'].update({'resources': con.get_resourcetypes_of_vocabulary(proj['project']['shortname'], session)})

    con.write_json(proj)

    (nhits, res_ids) = con.get_all_obj_ids(project, start, nrows)
    print("nhits=", nhits)
    print("Got all resource id's")

    """
    Write resources to xml
    """
    resources = list(map(con.get_resource, res_ids))


    for resource in resources:
        con.process_resource(resource, images_path, args.download)

    con.write_xml()

def main():
    program(sys.argv[1:])


if __name__ == '__main__':
    program(sys.argv[1:])
