from typing import List, Set, Dict, Tuple, Optional, Union
import os
import knora
#from xml.dom import minidom, Node
from lxml import etree
import argparse
from pprint import pprint
import request

class KnoraValue:
    value: str
    comment: str

    def __init__(self, value: str = None, comment: str = None):
        self.value = value
        self.comment = comment

    @staticmethod
    def process(node: minidom.Node):
        utf8str: str = None
        textattr: str = None
        value: str = None
        comment: str = None
        if node.hasAttribute('comment'):
            comment = node.getAttribute('comment')
        for item in node.childNodes:
            value = item.nodeValue
        else:
            pass  # ToDo: Create XML string from standoff

        return KnoraValue(value, comment)

    def get_it(self) -> Union[str, Dict[str, str]]:
        if self.comment is None:
            return self.value
        else:
            return {'value': self.value, 'comment': self.comment}

class KnoraProperty:
    proptype: str
    propname: str
    values: List[KnoraValue]

    def __init__(self, proptype: str, propname: str, hlistname:str = None, values: List[KnoraValue] = None):
        self.proptype:str = proptype
        self.propname: str = propname
        self.hlistname: str = None
        self.values = values

    @staticmethod
    def process(node: minidom.Node):
        proptype: str = node.getAttribute('type')
        propname: str = node.getAttribute('name')
        hlistname: str = None
        values: List[KnoraValue] = []
        if proptype == 'selection':
            hlistname = node.getAttribute('selection')
            pass
        elif proptype == 'hlist':
            hlistname = node.getAttribute('selection')
            pass
        elif proptype == 'resptr':
            pass
        else:
            pass
        for value in node.childNodes:
            if value.nodeType == Node.ELEMENT_NODE and value.nodeName == 'value':
                values.append(KnoraValue.process(value))

        return KnoraProperty(proptype=proptype, propname=propname, hlistname = hlistname, values=values)

    def get_it(self):
        if len(self.values) > 1:
            values = list(map(lambda a: a.get_it(), self.values))
        else:
            values = self.values[0].get_it()
        return values


class KnoraResource:
    res_id: str
    restype: str
    label: str
    properties: List[KnoraProperty]
    resptr: Optional[str]

    def __init__(self, res_id: str, restype: str, label: str, properties: List[KnoraProperty] = None, stillimage: str = None):
        self.res_id = res_id
        self.restype = restype
        self.label = label
        self.properties = properties
        self.stillimage = stillimage

    @staticmethod
    def process(node: minidom.Node):
        res_id: int = int(node.getAttribute('resid'))
        restype: str = node.getAttribute('restype')
        label: str = node.getAttribute('label')
        properties: List[KnoraProperty] = []
        stillimage = None
        for propnode in node.childNodes:
            if propnode.nodeType == Node.ELEMENT_NODE:
                if propnode.nodeName == 'image':
                    stillimage = propnode.firstChild.nodeValue
                elif propnode.nodeName == 'property':
                    properties.append(KnoraProperty.process(propnode))
        return KnoraResource(res_id=res_id, restype=restype, label=label, properties=properties, stillimage=stillimage)

    def get_it(self):
        resource = {
            'restype': self.restype,
            'label': self.label,
            'stillimage': self.stillimage,
            'properties': dict(map(lambda a: (a.propname, a.get_it()), self.properties))
        }
        return resource

def program(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--server", type=str, default="http://0.0.0.0:3333", help="URL of the Knora server")
    parser.add_argument("-S", "--sipi", type=str, default="http://0.0.0.0:1024", help="URL of SIPI server")
    parser.add_argument("-u", "--user", default="root@example.com", help="Username for Knora")
    parser.add_argument("-p", "--password", default="test", help="The password for login")
    parser.add_argument("-P", "--projectcode", default="00FE", help="Project short code")
    parser.add_argument("-O", "--ontoname", default="kpt", help="Shortname of ontology")
    parser.add_argument("-i", "--inproject", help="Shortname or SALSAH input project")
    parser.add_argument("-F", "--folder", default="-", help="Input folder")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose feedback")

    args = parser.parse_args()

    if args.folder == '-':
        folder = args.inproject + ".dir"
    else:
        folder = args.folder

    assets_path = os.path.join(folder, 'assets')
    images_path = os.path.join(folder, 'images')
    infile_path = os.path.join(folder, args.inproject) + '.xml'

    projectcode = None
    if args.projectcode == "XXXX":
        r = requests.get('https://raw.githubusercontent.com/dhlab-basel/dasch-ark-resolver-data/master/data/shortcodes.csv')
        lines = r.text.split('\r\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) > 1 and parts[1] == args.inproject:
                projectcode = parts[0]
                print('Found code "{}" for project "{}"!'.format(projectcode, parts[1]))
    else:
        projectcode = args.projectcode
    if projectcode is None:
        print("No valid project code!")
        exit(3)

    context = etree.iterparse(infile_path, events=("start", "end"))
    while True:
        event, node = context.next()
        print("event: {} tag: {}".format(event, node.tag))
    exit(0)

    #xml_root = xml_doc.documentElement

    resources: List[KnoraResource] = []
    for node in xml_root.childNodes:
        if node.nodeType == Node.ELEMENT_NODE and node.nodeName == 'resource':
            resources.append(KnoraResource.process(node))

    for r in resources:
        pprint(r.get_it())

