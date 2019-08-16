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

    def get_project(self, project: str, session ):
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

        print(self.server + '/api/projects/' + project)
        req = session.get(self.server + '/api/projects/' + project + "?lang=all", auth=(self.user, self.password) )
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        else:
            p_ontology = project + "-ontology"
            project_container = {"prefixes": {
                "foaf": "http://xmlns.com/foaf/0.1/",
                "dcterms": "http://purl.org/dc/terms/"
                },
                "project": "",
            }
            project_info = result['project_info']           # Is this the project_container??? Decide later
            project_info.update({"shortcode": "0814"})      # Project Schortcode: Manually, later to be imported from the csv File
            project_info.update({"lists": ""})              # Create a node which can be updated later (get_selections, get_hlists)
            """
            Users: This is still a dummy user...
            """
            project_info.update({"users": [
                {
                    "username": "testuser",
                    "email": "testuser@test.org",
                    "givenName": "test",
                    "familyName": "user",
                    "password": "test",
                    "lang": "en"
                }
                ]
            ,})
            """
            Below we set the pattern for the ontology. In the resources there is
            still some work to do: Terminology:
            : class: should be super: StillImageRepresentation instead of image
            : Maybe there is more work to do...
            """
            project_info.update({"ontology": {
                "name": p_ontology,
                "label": "",
                "resources": []
            }})
            project_container["project"] = project_info
            return project_container

    def get_resourcetypes_of_vocabulary(self, vocname, session):
        """
        Fetches Ressourcetypes and returns restypes
        """
        payload = {
            'vocabulary': vocname
        }
        req = session.get(self.server + '/api/resourcetypes/', params=payload, auth=(self.user, self.password))
        result = req.json()
        if result['status'] != 0:
            raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
        restype_ids = list(map(lambda r: r['id'], result['resourcetypes']))

        restypes_container: list = []
        for restype_id in restype_ids:
            print("Restype_id", restype_id)
            req = session.get(self.server + '/api/resourcetypes/' + restype_id, auth=(self.user, self.password))
            result = req.json()
            #print("Result :", result)
            if result['status'] != 0:
                raise SalsahError("SALSAH-ERROR:\n" + result['errormsg'])
            restypes_container.append(result['restype_info'])
        return restypes_container

    def get_selections_of_vocabulary(self, vocname, session):
        """
        Requests the API for selections of the project
        Calls each single selecion and nests the nodes inside
        Is inserted into the project_container afterwards...
        """
        payload = {
            'vocabulary': vocname
        }
        req = session.get(self.server + '/api/selections?vocabulary=', params=payload, auth=(self.user, self.password))
        result = req.json()

        # Let's create a list with the selection ids:
        selection_ids = list(map(lambda b: b['id'], result['selections']))
        print("Test: \n", selection_ids)

        ceiling = len(selection_ids)
        #print("Dach: ", ceiling)
        max = ceiling - 1
        #print("Max: ", max)

        """Let's make a dict container for the lists: """
        selections_container = []

        for i in range(ceiling):
            id = selection_ids[i]
            proj_selections = result['selections'][i]
            proj_selections.update({"nodes": ""})
            selections_container.append(proj_selections)
            req_nodes = session.get(self.server + '/api/selections/' + id, auth=(self.user, self.password))
            """Selections einzeln ausgeben und nachher den "nodes" Knoten anhängen"""
            result_nodes = req_nodes.json()
            result_sel = result_nodes['selection']
            selections_container[i].update({"nodes":result_sel})

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
proj = con.get_project(project, session)
pprint(proj)
proj['project'].update({'lists': con.get_selections_of_vocabulary(proj['project']['shortname'], session)})
proj['project']['ontology'].update({'resources': con.get_resourcetypes_of_vocabulary(proj['project']['shortname'], session)})

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
