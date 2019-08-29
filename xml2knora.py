from typing import List, Set, Dict, Tuple, Optional, Union
import os
import knora
from lxml import etree
import argparse
from pprint import pprint
import base64
import json
from knora import KnoraError, KnoraStandoffXml, Knora, Sipi


class MyError(BaseException):
    def __init__(self, msg: str):
        self.message = msg


class KnoraValue:
    def __init__(self, context, node):
        self.resrefs = None
        self.comment = node.get('comment')
        if node.get('resrefs') is not None:
            self.resrefs = node.attrib['resrefs'].split('|')
        if node.get('encoding') == 'hex64':
            self.value = base64.b64decode("".join(node.itertext())).decode()
        else:
            self.value = "".join(node.itertext())
        while True:
            event, subnode = next(context)
            if event == 'start':
                raise MyError(
                    'Unexpected start tag: "{}" <property> may contain only <value> tags!'.format(subnode.tag))
            else:
                if subnode.tag == 'value':
                    break
                else:
                    raise MyError('Unexpected end tag: "{}": </value> expected!'.format(subnode.tag))

    def print(self):
        print('    Value: ' + self.value)
        if self.resrefs is not None:
            for i in self.resrefs:
                print('    resref: ' + i)


class KnoraProperty:
    def __init__(self, context, node):
        self.name = node.attrib['name']
        self.type = node.attrib['type']
        self.values = []
        while True:
            event, subnode = next(context)
            if event == 'start':
                if subnode.tag == 'value':
                    self.values.append(KnoraValue(context, subnode))
                else:
                    raise MyError('Unexpected start tag: "{}" <property> may contain only <value> tags!'.format(subnode.tag))
            else:
                if subnode.tag == 'property':
                    break
                else:
                    raise MyError('Unexpected end tag: "{}": </property> expected!'.format(subnode.tag))

    def print(self):
        print('  Property: {} Type: {}'.format(self.name, self.type))
        for value in self.values:
            value.print()


class KnoraResource:
    def __init__(self, context, node):
        self.unique_id = node.attrib['unique_id']
        self.label = node.attrib['label']
        self.restype = node.attrib['restype']
        self.image = None
        self.properties = []
        while True:
            event, subnode = next(context)
            if event == 'start':
                if subnode.tag == 'property':
                    self.properties.append(KnoraProperty(context, subnode))
                elif subnode.tag == 'image':
                    self.image = node.text
                else:
                    raise MyError('Unexpected start tag: "{}" <resource> may contain only <property> or <image> tags!'.format(subnode.tag))
            else:
                if subnode.tag == 'resource':
                    break
                elif subnode.tag == 'image':
                    self.image = "".join(subnode.itertext())
                else:
                    raise MyError('Unexpected end tag: "{}" </resource> expected!'.format(subnode.tag))

    def print(self):
        print('Resource: id={} restype: {} label: {}'.format(self.unique_id, self.restype, self.label))
        if self.image is not None:
            print(' Image: ' + self.image)
        for property in self.properties:
            property.print()

    def get_resptrs(self):
        resptrs = []
        for property in self.properties:
            if property.type == 'resptr':
                for value in property.values:
                    resptrs.append(value.value)
            elif property.type == 'richtext':
                for value in property.values:
                    if value.resrefs is not None:
                        #  tmp = list(map(lambda a: int(a), value.resrefs))
                        resptrs.extend(value.resrefs)
        return resptrs

    def get_propvals(self):
        propdata = {}
        for property in self.properties:
            vals = []
            for value in property.values:
                if value.comment is None:
                    vals.append(value.value)
                else:
                    vals.append({'value': value.value, 'comment': value.comment})
            propdata[property.name] = vals if len(vals) > 1 else vals[0]
        return json.dumps(propdata, indent=4)






parser = argparse.ArgumentParser()
parser.add_argument("-s", "--server", type=str, default="http://0.0.0.0:3333", help="URL of the Knora server")
parser.add_argument("-S", "--sipi", type=str, default="http://0.0.0.0:1024", help="URL of SIPI server")
parser.add_argument("-u", "--user", default="root@example.com", help="Username for Knora")
parser.add_argument("-p", "--password", default="test", help="The password for login")
parser.add_argument("-P", "--projectcode", default="00FE", help="Project short code")
parser.add_argument("-O", "--ontoname", default="kpt", help="Shortname of ontology")
parser.add_argument("-i", "--inproject", help="Shortname or SALSAH input project")
parser.add_argument("-F", "--folder", default="-", help="Input folder")

args = parser.parse_args()

if args.folder == '-':
    folder = args.inproject + ".dir"
else:
    folder = args.folder

assets_path = os.path.join(folder, 'assets')
images_path = os.path.join(folder, 'images')
infile_path = os.path.join(folder, args.inproject) + '.xml'

context = etree.iterparse(infile_path, events=("start", "end"))
resources = []
while True:
    event, node = next(context)
    if event == 'start':
        if node.tag == 'salsah':
            vocabulary = node.attrib['vocabulary']
        elif event == 'start' and node.tag == 'resource':
            resources.append(KnoraResource(context, node))
    elif event == 'end':
        if node.tag == 'salsah':
            break;

context = None  # delete XML tree
#
# here we sort the resources according to outgoing resptrs
#
ok_resources: [KnoraResource] = []
notok_resources: [KnoraResource] = []
ok_resids : [str] = []
cnt = 0
notok_len = 9999999
while len(resources) > 0 and cnt < 100:
    for resource in resources:
        resptrs = resource.get_resptrs()
        if len(resptrs) == 0:
            ok_resources.append(resource)
            ok_resids.append(resource.unique_id)
        else:
            ok = True
            for resptr in resptrs:
                if resptr in ok_resids:
                    pass
                else:
                    ok = False;
            if ok:
                ok_resources.append(resource)
                ok_resids.append(resource.unique_id)
            else:
                notok_resources.append(resource)
    resources = notok_resources
    if not len(notok_resources) < notok_len:
        print('Cannot resolve resptr dependencies. Giving up....')
        exit(5)
    nook_len = len(notok_resources)
    notok_resources = []
    cnt += 1
    print('{}. Ordering pass Finished!'.format(cnt))

resources = ok_resources
for resource in resources:
    print('resclass=' + resource.restype)
    print('label=' + resource.label)
    print(resource.get_propvals())


