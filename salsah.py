from typing import List, Set, Dict, Tuple, Optional
import os
from lxml import etree
import requests
import argparse
from enum import Enum
from pprint import pprint
import urllib.request
import magic


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
    def __init__(self, server: str, user: str, password: str) -> None:
        super().__init__()
        self.server = server
        self.user = user
        self.password = password

    def get_project(self, project: str, shortcode: str) -> dict:
        req = requests.get(self.server + '/api/projects/' + project, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        else:
            if shortname != result['shortname']:
                raise SalsahError("EXPORT-ERROR:\nInconsistent shortname!")
            project_info = {
                'shortcode': shortcode,
                'shortname': result['shortname'],
                'longname': result['longname'],
                'descriptions': {
                    'en': result['description']
                },
                'keywords': result['keywords'] if len(result['keywords']) > 0 else []
            }


    def get_vocabularies(self, project: str):
        print(self.server + '/api/vocabularies/' + project)
        req = requests.get(self.server + '/api/vocabularies/' + project, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        else:
            return list(filter(lambda voc: int(voc['project_id']) != 0, result['vocabularies']))

    def get_resourcetypes_of_vocabulary(self, vocname):
        payload = {
            'vocabulary': vocname
        }
        req = requests.get(self.server + '/api/resourcetypes/', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        restype_ids = list(map(lambda r: r['id'], result['resourcetypes']))

        restypes: list = []
        for restype_id in restype_ids:
            req = requests.get(self.server + '/api/resourcetypes/' + restype_id, auth=(self.user, self.password))
            result = req.json()
            if result['status'] != 0:
                raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
            restypes.append(result['restype_info'])
        return restypes

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

        if nrows > 0:
            payload['show_nrows'] = show_nrows
            payload['start_at'] = start_at

        req = requests.get(self.server + '/api/search/', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        else:
            nhits = result['nhits']
            obj_ids = list(map(lambda a: a['obj_id'], result['subjects']))

            return (nhits, obj_ids)

    def get_resource(self, res_id: int, verbose: bool = True) -> Dict:
        req = requests.get(self.server + '/api/resources/' + res_id, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        else:
            print('res_id=', res_id)
            return result

class JsonBuilder:

    def __init__(self, filename) -> None:
        super().__init__()
        self.filename = filename

class XmlBuilder:

    def __init__(self, filename) -> None:
        super().__init__()
        self.filename = filename
        self.root = etree.Element('salsah');
        self.mime = magic.Magic(mime=True)


    def process_vocabulary(self, voc: dict) -> None:
        vocnode = etree.Element('vocabulary', {'id': voc['id'], 'shortname': voc['shortname']})
        longname = etree.Element('longname')
        longname.text = voc['longname']
        vocnode.append(longname)
        description = etree.Element('description')
        description.text = voc['description']
        vocnode.append(description)
        restypes_node = etree.Element('restypes')
        for restype in voc['restypes']:
            restypes_node.append(self.process_restype(restype))
        vocnode.append(restypes_node)
        self.root.append(vocnode)

    def process_restype(self, restype: dict):
        restype_node = etree.Element('resource_type', {'name': restype['name'], 'label': restype['label']})
        if restype.get('description') is not None:
            description_node = etree.Element('description')
            description_node.text = restype['description']
            restype_node.append(description_node)
        if restype.get('iconsrc') is not None:
            iconpath = os.path.join(assets_path, restype['name'])
            urllib.request.urlretrieve(restype['iconsrc'], iconpath)

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

            iconsrc_node = etree.Element('iconsrc', {'file': iconpath + ext})
            restype_node.append(iconsrc_node)
            for proptype in restype['properties']:
                restype_node.append(self.process_proptype(proptype))
        return restype_node

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
        return proptype_node

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
        return valele

    def process_property(self, propname: str, property: Dict):
        if propname == '__location__':
            return None
        if property.get("values") is not None:
            propnode = etree.Element('property', {'name': propname, 'label': '' if property.get('label') is None else property['label']})
            for value in property["values"]:
                propnode.append(self.process_value(property["valuetype_id"], value))
            return propnode
        else:
            return None

    def process_resource(self, resource: Dict):
        resnode = etree.Element('resource', {
            'restype': resource["resinfo"]["restype_name"],
            'resid': resource["resdata"]["res_id"]
        })
        if resource["resinfo"].get('locdata') is not None:
            imgpath = os.path.join(images_path, resource["resinfo"]['locdata']['origname'])
            getter = resource["resinfo"]['locdata']['path'] + '&format=tif'
            print('Downloading ' + resource["resinfo"]['locdata']['origname'] + '...')
            urllib.request.urlretrieve(getter, imgpath)
            image_node = etree.Element('image')
            image_node.text = imgpath
            resnode.append(image_node)

        for propname in resource["props"]:
            propnode = self.process_property(propname, resource["props"][propname])
            if propnode is not None:
                resnode.append(propnode)
        self.root.append(resnode)

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
try:
    os.mkdir(folder)
    os.mkdir(assets_path)
    os.mkdir(images_path)
except OSError:
    print("Could'nt create necessary folders")
    exit(2)

con = Salsah(args.server, user, password)
vocs = con.get_vocabularies(project)
pprint(vocs)

for voc in vocs:
    voc.update({'restypes': con.get_resourcetypes_of_vocabulary(voc['shortname'])})


(nhits, res_ids) = con.get_all_obj_ids(project, start, nrows)
print("nhits=", nhits)
print("Got all resource id's")
resources = list(map(con.get_resource, res_ids))


xml = XmlBuilder(outfile_path)

for voc in vocs:
    xml.process_vocabulary(voc)

for resource in resources:
    xml.process_resource(resource)

xml.write_xml()

print(outfile_path + ' written...')
#print(etree.tostring(root, pretty_print=True, xml_declaration=True, encoding='utf-8'))

