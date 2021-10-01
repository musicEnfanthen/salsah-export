from enum import Enum
from lxml import etree
from pprint import pprint
from re import sub, search
from typing import List, Dict, Tuple
import argparse
import base64
import jdcal
import json
import magic
import os
import requests
import shutil
import sys

requests.urllib3.disable_warnings(requests.urllib3.exceptions.InsecureRequestWarning)

#
# MySQL access to old salsah
#
# https://phpmyadmin.sw-zh-dasch-prod-02.prod.dasch.swiss
#

Valtype: Dict = {
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


stags: Dict = {
    '_link': ['<a href="{}">', '<a class="salsah-link" href="IRI:{}:IRI">'],
    'bold': '<strong>',
    'strong': '<strong>',
    'underline': '<u>',
    'italic': '<em>',
    'linebreak': '<br/>',
    'strikethrough': '<strike>',
    'strike': '<strike>',
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
    'h6': '<h6>'
}


etags: Dict = {
    '_link': '</a>',
    'bold': '</strong>',
    'strong': '</strong>',
    'underline': '</u>',
    'italic': '</em>',
    'linebreak': '',
    'strikethrough': '</strike>',
    'strike': '</strike>',
    'style': '</span>',
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
    'h6': '</h6>'
}


def camel_case(str: str, firstLetterCase = None):
    """
    Helper function to transform a given string str to camelCase.
    firstLetterCase can take values 'upper' and 'lower'.
    :param str: given string to transform
    :return: Transformed string (lowerCamelCase or UpperCamelCase

    :example:
    str = "transcriptionTest-for_endLess DeLuxe"
    str2 = "TranscriptionTest"

    camelCase(str, 'lower')) --> transcriptionTestForEndLessDeLuxe
    camelCase(str2, 'lower') --> transcriptionTest
    camelCase(str, 'upper') --> TranscriptionTestForEndLessDeLuxe
    camelCase(str2, 'upper') --> TranscriptionTest
    """
    s = str
    # Look for underscores, hyphens or white space
    if search(r"(_|-|\s)+", str):
        # Convert _ and - to white space
        s = sub(r"(_|-)+", " ", str)
        # Capitalize first character of a every substring (while keeping case of other letters)
        s = ' '.join(substr[:1].upper() + substr[1:] for substr in s.split(' '))
        # Remove white space
        s = s.replace(" ", "")
    if firstLetterCase == 'upper':
        # Uppercase first character of complete string
        return ''.join([s[0].upper(), s[1:]])
    elif firstLetterCase == 'lower':
        # Lowercase first character of complete string
        return ''.join([s[0].lower(), s[1:]])
    else:
        return s


def camel_case_vocabulary_resource(str):
    """
    Helper function to transform a given vocabulary resource string
    to camelCase while leaving vocabulary untouched, e.g.: vocabulary:ResourceName
    :param str: given string to transform
    :return: Transformed string
    """
    if len(str.split(':', 1)) == 2:
        tmp_voc = str.split(':', 1)[0]
        tmp_res = upper_camel_case(str.split(':', 1)[-1])
        return ''.join(tmp_voc + ':' + tmp_res)
    else:
        return upper_camel_case(str)


def lower_camel_case(str):
    return camel_case(str, 'lower')


def upper_camel_case(str):
    return camel_case(str, 'upper')





def process_richtext(utf8str: str, textattr: str = None, resptrs: List = []) -> (str, str):
    if textattr is not None:
        attributes = json.loads(textattr)
        if len(attributes) == 0:
            return 'utf8', utf8str
        attrlist: List= []
        result: str = ''
        for key, vals in attributes.items():
            for val in vals:
                attr: Dict = {}
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
                attr = {
                    'tagname': key,
                    'type': 'end',
                    'pos': val['end']
                }
                attrlist.append(attr)
        attrlist = sorted(attrlist, key=lambda attr: attr['pos'])
        pos: int = 0
        stack: List= []
        for attr in attrlist:
            result += utf8str[pos:attr['pos']]
            if attr['type'] == 'start':
                if attr['tagname'] == '_link':
                    if attr.get('resid') is not None:
                        result += stags[attr['tagname']][1].format(attr['resid'])
                    else:
                        result += stags[attr['tagname']][0].format(attr['href'])
                else:
                    result += stags[attr['tagname']]
                stack.append(attr)
            elif attr['type'] == 'end':
                match = False
                tmpstack: List= []
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
                    check_list = stags[tmp['tagname']]
                    if isinstance(check_list, list):
                        new_string = ' '.join(check_list)
                    else:
                        new_string = check_list

                    result += new_string
                    stack.append(tmp)
            pos = attr['pos']
        return 'hex64', base64.b64encode(result.encode())
    else:
        return 'utf8', utf8str


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
            assets_path: str,
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
        :param resptrs: XML file containing object information for resource pointer
        :param session: Session object
        """
        super().__init__()
        self.server: str = server
        self.user: str = user
        self.password: str = password
        self.filename: str = filename
        self.assets_path: str = assets_path
        self.projectname: str = projectname
        self.shortcode: str = shortcode
        self.resptrs: List[str] = resptrs
        self.session: requests.Session = session

        self.mime = magic.Magic(mime=True)
        self.selection_mapping: Dict[str, str] = {}
        self.selection_node_mapping: Dict[str, str] = {}
        self.hlist_mapping: Dict[str, str] = {}
        self.hlist_node_mapping: Dict[str, str] = {}
        self.vocabulary: str = ""

        # Prepare namespaces for XML root element
        default_namespace = "https://dasch.swiss/schema"
        xsi_namespace = "http://www.w3.org/2001/XMLSchema-instance"
        nsmap: Dict = {
            None: default_namespace,
            'xsi': xsi_namespace,
        }
        xsi_schema_location_qname = etree.QName(xsi_namespace, "schemaLocation")
        xsi_schema_location_url = "https://dasch.swiss/schema https://raw.githubusercontent.com/dasch-swiss/dsp-tools/main/knora/dsplib/schemas/data.xsd"

        # Create root element with namespaces for XML file
        self.root = etree.Element('knora', nsmap=nsmap)

        # Add xsi:schemaLocation attribute to root element of XML file
        self.root.set(xsi_schema_location_qname, xsi_schema_location_url)

        # Add project shortcode to root element of XML file
        self.root.set('shortcode', self.shortcode)

        self.mime = magic.Magic(mime=True)
        self.session = session

    def get_icon(self, iconsrc: str, name: str) -> str:
        """
        Get an icon from old SALSAH
        :param iconsrc: URL for icon in old SALSAH
        :param name: nameof the icon
        :return: Path to the icon on local disk
        """
        iconpath: str = os.path.join(self.assets_path, name)
        dlfile: str = self.session.get(iconsrc, stream=True)  # war urlretrieve()
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
        req = self.session.get(self.server + '/api/projects/' + self.projectname + "?lang=all",
                               auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])

        project_container: Dict = {
            "$schema": "https://raw.githubusercontent.com/dasch-swiss/dsp-tools/main/knora/dsplib/schemas/ontology.json",
            "prefixes": dict(map(lambda a: (a['shortname'], a['uri']), sysvocabularies)),
            "project": { }, # will be filled below
        }
        project_info = result['project_info']  # Is this the project_container??? Decide later
        project: Dict = {
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
        # Note: the API call always returns also the system vocabularies which have to be excluded
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
        # Add default ontology name (= project shortname) to root element of XML file
        self.root.set('default-ontology', vocabulary['shortname'])

        # Get project selections
        project['lists'] = self.get_selections_of_vocabulary(vocabulary['shortname'])

        # ToDo: not yet implemented in create_ontology
        # if vocabulary.get('description') is not None and vocabulary['description']:
        #    project['ontologies']['comment'] = vocabulary['description']

        prop, res = self.get_resourcetypes_of_vocabulary(vocabulary['shortname'])

        project['ontologies'] = [{
            'name': vocabulary['shortname'],
            'label': vocabulary['longname'],
            'properties': prop,
            'resources': res
        }]

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

        props: List= []
        cardinalities: List= []
        gui_order: int = 1

        for property in salsah_restype_info[restype_id]['properties']:
            if property['name'] == '__location__':
                continue
            if property['name'].startswith('has'):
                pname = property['name']
            else:
                pname = 'has' + property['name'].capitalize()

            prop = {
                'name': pname,
                'labels': dict(map(lambda a: (a['shortname'], a['label']), property['label']))
            }
            if property.get('description') is not None:
                prop['comments'] = dict(map(lambda a: (a['shortname'], a['description']), property['description']))

            #
            # convert attributes into dict
            #
            attrdict: Dict = {}
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
                        print("WARNING: Resclass {} has resptr {} with no object!!!".format(
                            salsah_restype_info[restype_id]['name'], property['name']))
                elif property['name'] == 'region_of':
                    knora_super = ['isRegionOf']
                    if self.resptrs.get(salsah_restype_info[restype_id]['name']) is not None:
                        tmp = self.resptrs[salsah_restype_info[restype_id]['name']]
                        if tmp.get('salsah:region_of') is not None:
                            knora_object = tmp['salsah:part_of']
                    else:
                        knora_object = 'FIXME--Resource--FIXME'
                        print("WARNING: Resclass {} has resptr {} with no object!".format(
                            salsah_restype_info[restype_id]['name'], property['name']))
                elif property['name'] == 'resource_reference':
                    knora_super = ['hasLinkTo']
                    if self.resptrs.get(salsah_restype_info[restype_id]['name']) is not None:
                        tmp = self.resptrs[salsah_restype_info[restype_id]['name']]
                        if tmp.get('salsah:resource_reference') is not None:
                            knora_object = tmp['salsah:part_of']
                    else:
                        knora_object = 'FIXME--Resource--FIXME'
                        print("WARNING: Resclass {} has resptr {} with no object!".format(
                            salsah_restype_info[restype_id]['name'], property['name']))
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
                knora_super = ['hasValue',
                               'dc:' + property['name'] if property['name'] != 'description_rt' else 'dc:description']
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
                            knora_object = tmp[property['vocabulary'] + ':' + property['name'].capitalize()]
                    else:
                        if salsah_restype_info.get(attrdict['restypeid']) is None:
                            tmp = self.resptrs[salsah_restype_info[restype_id]['name']]
                            if tmp.get('salsah:resource_reference') is not None:
                                knora_object = tmp[property['vocabulary'] + ':' + property['name'].capitalize()]
                            raise SalsahError("SALSAH-ERROR:\n\"restypeid\" is missing!")
                        (voc, restype) = salsah_restype_info[attrdict['restypeid']]['name'].split(':')
                        knora_object = voc + ':' + restype.capitalize()
                    if knora_object is None:
                        knora_object = 'FIXME--Resource--FIXME'
                        print("WARNING: Resclass {} has resptr {} with no object!".format(
                            salsah_restype_info[restype_id]['name'], property['name']))
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

            gui_attributes: Dict = {}
            if property['gui_name'] == 'text':
                gui_element = 'SimpleText'
                for attr in gui_attr_lut['text']:
                    if attrdict.get(attr):
                        if attr == 'maxlength' or attr == 'size':
                            gui_attributes[attr] = int(attrdict.get(attr))
                        else:
                            gui_attributes[attr] = attrdict.get(attr)
                        # gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'textarea':
                gui_element = 'Textarea'
                for attr in gui_attr_lut['textarea']:
                    if attrdict.get(attr):
                        if attr == 'rows' or attr == 'cols':
                            gui_attributes[attr] = int(attrdict.get(attr))
                        else:
                            gui_attributes[attr] = attrdict.get(attr)
                        # gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'pulldown':
                gui_element = 'Pulldown'
                for attr in gui_attr_lut['pulldown']:
                    if attrdict.get(attr) and attr == 'selection':
                        gui_attributes['hlist'] = self.selection_mapping[attrdict[attr]]
                        # gui_attributes.append('hlist=' + self.selection_mapping[attrdict[attr]])
            elif property['gui_name'] == 'slider':
                gui_element = 'Slider'
                for attr in gui_attr_lut['slider']:
                    if attrdict.get(attr):
                        gui_attributes[attr] = attrdict.get(attr)
                        # gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'spinbox':
                gui_element = 'Spinbox'
            elif property['gui_name'] == 'searchbox':
                gui_element = 'Searchbox'
                for attr in gui_attr_lut['searchbox']:
                    if attrdict.get(attr):
                        if attr == 'numprops':
                            gui_attributes[attr] = int(attrdict.get(attr))
                        else:
                            gui_attributes[attr] = attrdict.get(attr)
                        # gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'date':
                gui_element = 'Date'
            elif property['gui_name'] == 'geometry':
                gui_element = 'Geometry'
            elif property['gui_name'] == 'colorpicker':
                gui_element = 'Colorpicker'
                for attr in gui_attr_lut['colorpicker']:
                    if attrdict.get(attr):
                        gui_attributes[attr] = attrdict.get(attr)
                        # gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'hlist':
                gui_element = 'List'
                for attr in gui_attr_lut['hlist']:
                    if attrdict.get(attr) and attr == 'hlist':
                        gui_attributes[attr] = self.hlist_mapping[attrdict[attr]]
                        # gui_attributes.append(attr + '=' + self.hlist_mapping[attrdict[attr]])
            elif property['gui_name'] == 'radio':
                gui_element = 'Radio'
                for attr in gui_attr_lut['pulldown']:
                    if attrdict.get(attr) and attr == 'selection':
                        gui_attributes['hlist'] = self.selection_mapping[attrdict[attr]]
                        # gui_attributes.append('hlist=' + self.selection_mapping[attrdict[attr]])
            elif property['gui_name'] == 'richtext':
                gui_element = 'Richtext'
            elif property['gui_name'] == 'time':
                gui_element = 'Time'
            elif property['gui_name'] == 'interval':
                gui_element = 'Interval'
                for attr in gui_attr_lut['interval']:
                    if attrdict.get(attr):
                        gui_attributes[attr] = attrdict.get(attr)
                        # gui_attributes.append(attr + '=' + attrdict[attr])
            elif property['gui_name'] == 'geoname':
                gui_element = 'Geonames'
            else:
                raise SalsahError(
                    "SALSAH-ERROR:\n\"Invalid gui_element: " + property['gui_name'] + " by property " +
                    property['name'])

            prop['super'] = knora_super
            prop['object'] = knora_object
            prop['gui_element'] = gui_element

            if len(gui_element) > 0 and len(gui_attributes) > 0:
                prop['gui_attributes'] = gui_attributes

            props.append(prop)

            cardinalities.append({
                'propname': ':' + pname,
                'cardinality': property['occurrence'],
                'gui_order': gui_order
            })

            gui_order += 1

        return props, cardinalities

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

        restype_ids: List = list(map(lambda r: r['id'], result['resourcetypes']))

        salsah_restype_info: Dict = {}
        for restype_id in restype_ids:
            payload: dict = {
                'lang': 'all'
            }
            req = self.session.get(self.server + '/api/resourcetypes/' + restype_id, params=payload,
                                   auth=(self.user, self.password))
            result = req.json()
            if result['status'] != 0:
                raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
            salsah_restype_info[restype_id] = result['restype_info']

        restypes_container: List= []
        added_properties: Dict = {}

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

            properties, restype['cardinalities'] = self.get_properties_of_resourcetype(vocname, restype_id,
                                                                                       salsah_restype_info)
            restypes_container.append(restype)

            for property in properties:
                if property['name'] not in added_properties:
                    added_properties[property['name']] = property

        return list(added_properties.values()), restypes_container

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
            req_nodes = self.session.get(self.server + '/api/selections/' + selection['id'], params=payload,
                                         auth=(self.user, self.password))
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
        def process_children(children: List) -> List:
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
            req_nodes = self.session.get(self.server + '/api/hlists/' + hlist['id'], params=payload,
                                         auth=(self.user, self.password))
            result_nodes = req_nodes.json()
            if result_nodes['status'] != 0:
                raise SalsahError("SALSAH-ERROR:\n" + result_nodes['errormsg'])
            root['nodes'] = process_children(result_nodes['hlist'])
            selections_container.append(root)

        return selections_container

    def get_all_obj_ids(self, project: str, start_at: int = 0, show_nrows: int = -1):
        """
        Get all resource id's from project
        :param project: Project name
        :param start_at: Start at given resource
        :param show_nrows: Show n resources
        :return:
        """
        payload = {
            'searchtype': 'extended',
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
        req = self.session.get(self.server + '/api/resources/' + res_id, params=payload,
                               auth=(self.user, self.password))
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
        file_content = json.dumps(proj, indent=4)
        f = open(json_filename, "w")
        f.write(file_content)
        f.close()

    def process_value(self, valtype: int, value: any, comment: str = None):
        valele = None
        if valtype == ValtypeMap.TEXT.value:
            if value:
                valele = etree.Element('text')
                valele.text = value
                valele.set('encoding', 'utf8')
        elif valtype == ValtypeMap.RICHTEXT.value:
            if value.get('utf8str').strip():
                print("'richtext: {}".format(value.get('utf8str').strip()))
                valele = etree.Element('text')
                resptrs = value['resource_reference']
                encoding, valele.text = process_richtext(
                    utf8str=value.get('utf8str').strip(),
                    textattr=value.get('textattr').strip(),
                    resptrs=value.get('resptrs'))
                resrefs = '|'.join(value['resource_reference'])
                if len(resrefs) > 0:
                    valele.set('resrefs', resrefs)
                valele.set('encoding', encoding)
        elif valtype == ValtypeMap.COLOR.value:
            if value:
                valele = etree.Element('color')
                valele.text = value
        elif valtype == ValtypeMap.DATE.value:
            if value:
                valele = etree.Element('date')
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
            if value:
                valele = etree.Element('float')
                valele.text = value
        elif valtype == ValtypeMap.GEOMETRY.value:
            if value:
                valele = etree.Element('geometry')
                valele.text = value
        elif valtype == ValtypeMap.GEONAME.value:
            if value:
                valele = etree.Element('geoname')
                valele.text = value
        elif valtype == ValtypeMap.HLIST.value:
            if value:
                valele = etree.Element('list')
                valele.text = 'H_' + value
        elif valtype == ValtypeMap.ICONCLASS.value:
            if value:
                valele = etree.Element('iconclass')
                valele.text = value
        elif valtype == ValtypeMap.INTEGER.value:
            if value:
                valele = etree.Element('integer')
                valele.text = value
        elif valtype == ValtypeMap.INTERVAL.value:
            if value:
                valele = etree.Element('interval')
                valele.text = value
        elif valtype == ValtypeMap.PERIOD.value:
            valele = etree.Element('period')
            pass
        elif valtype == ValtypeMap.RESPTR.value:
            if value:
                valele = etree.Element('resptr')
                valele.text = value
        elif valtype == ValtypeMap.SELECTION.value:
            if value:
                valele = etree.Element('list')
                valele.text = 'S_' + value
        elif valtype == ValtypeMap.TIME.value:
            if value:
                valele = etree.Element('time')
                valele.text = value
        else:
            print('===========================')
            pprint(value)
            print('----------------------------')
        if comment is not None:
            print('Comment: ' + comment)
            valele.set('comment', comment)

        return valele  # Das geht in die Resourcen

    def process_property(self, propname: str, property: Dict):
        if propname == '__location__':
            return None
        if property.get("values") is not None:
            #
            # first we strip the vocabulary off, if it's not salsah, dc, etc.
            #
            tmp = propname.split(':')
            if tmp[0] == self.vocabulary or tmp[0] == 'dc':
                propname_new = tmp[1]  # strip vocabulary
                #
                # if the propname does not start with "has", add it to the propname. We have to do this
                # to avoid naming conflicts between resources and properties which share the same
                # namespace in GraphDB
                #
                if not propname_new.startswith('has'):
                    propname_new = 'has' + propname_new.capitalize()
            else:
                propname_new = propname
            options: Dict[str, str] = {
                'name': propname_new
            }

            if int(property["valuetype_id"]) == ValtypeMap.SELECTION.value:
                (dummy, list_id) = property['attributes'].split("=")
                options['list'] = self.selection_mapping[list_id]
            elif int(property["valuetype_id"]) == ValtypeMap.HLIST.value:
                (dummy, list_id) = property['attributes'].split("=")
                options['list'] = self.hlist_mapping[list_id]

            pname: str = None
            if Valtype.get(property["valuetype_id"]) == 'richtext':
                pname = 'text-prop'
            elif Valtype.get(property["valuetype_id"]) == 'hlist':
                pname = 'list-prop'
            elif Valtype.get(property["valuetype_id"]) == 'selection':
                pname = 'list-prop'
            else:
                pname = Valtype.get(property["valuetype_id"]) + '-prop'
            propnode = etree.Element(pname, options)
            cnt: int = 0
            for value in property["values"]:
                if property['comments'][cnt]:
                    valnode = self.process_value(int(property["valuetype_id"]), value, property['comments'][cnt])
                    if valnode is not None:
                        propnode.append(valnode)
                        cnt += 1
                else:
                    valnode = self.process_value(int(property["valuetype_id"]), value)
                    if valnode is not None:
                        propnode.append(valnode)
                        cnt += 1
            if cnt > 0:
                return propnode
            else:
                return None
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
            'id': resource["resdata"]["res_id"],
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
                dlfile2 = self.session.get(getter, stream=True)  # war urlretrieve()

                with open(imgpath, 'w+b') as fd:
                    for chunk in dlfile2.iter_content(chunk_size=128):
                        fd.write(chunk)
                    fd.close()

            image_node = etree.Element('image')
            image_node.text = imgpath
            resnode.append(image_node)

        for propname in resource["props"]:
            propnode = self.process_property(propname, resource["props"][propname])  # process_property()
            if propnode is not None:
                resnode.append(propnode)
        self.root.append(resnode)  # Das geht in die Resourcen
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
    parser.add_argument("-s", "--shortcode", default='XXXX', help="Knora-shortcode of project")
    parser.add_argument("-n", "--nrows", type=int, help="Number of records to get, -1 to get all")
    parser.add_argument("-S", "--start", type=int, help="Start at record with given number")
    parser.add_argument("-F", "--folder", default="-", help="Output folder")
    parser.add_argument("-r", "--resptrs_file", help="List of resptrs targets")
    parser.add_argument("-d", "--download", action="store_true", help="Download image files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose feedback")

    args = parser.parse_args()

    #
    # here we fetch the shortcodes from the github repository
    #
    shortcode = None
    if args.shortcode == "XXXX":
        r = requests.get(
            'https://raw.githubusercontent.com/dhlab-basel/dasch-ark-resolver-data/master/data/shortcodes.csv')
        lines = r.text.split('\r\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) > 1 and parts[1] == args.project:
                shortcode = parts[0]
                print('Found Knora project shortcode "{}" for "{}"!'.format(shortcode, parts[1]))
    else:
        shortcode = args.shortcode

    if shortcode is None:
        print("You must give a shortcode (\"--shortcode XXXX\")!")
        exit(1)

    user = 'root' if args.user is None else args.user
    password = 'SieuPfa15' if args.password is None else args.password
    start = 0 if args.start is None else args.start
    nrows = -1 if args.nrows is None else args.nrows
    project = args.project

    resptrs: Dict = {}
    if args.resptrs_file is not None:
        tree = etree.parse(args.resptrs_file)
        root = tree.getroot()
        for restype in root:
            restype_name = restype.attrib["name"].strip()
            props: Dict = {}
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
        print("Couldn't create necessary folders")
        exit(2)

    # Define session
    session = requests.Session()
    session.verify = False  # Works...

    con = Salsah(server=args.server, user=user, password=password, filename=outfile_path,
                 assets_path=assets_path, projectname=args.project, shortcode=shortcode,
                 resptrs=resptrs, session=session)
    proj = con.get_project()
    # proj['project']['ontologies'].update({'resources': con.get_resourcetypes_of_vocabulary(proj['project']['shortname'], session)})

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
