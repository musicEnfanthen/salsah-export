import json
import os
import pathlib
import re
import shutil
from collections.abc import Iterable
from operator import xor
from typing import Any, Optional, Union

import pandas as pd
from lxml import etree
from lxml.builder import E

from HelperScripts.general_helper import check_notna, find_date_in_string
from HelperScripts.warnings_handler import handle_warnings

##############################
# global variables and classes
##############################
copyright_notice = '© Webern Project'
xml_namespace_map = {
    None: 'https://dasch.swiss/schema',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
}


class PropertyElement:
    value: str
    permissions: Optional[str]
    comment: Optional[str]
    encoding: Optional[str]

    def __init__(
        self, 
        value: str, 
        permissions: Optional[str] = 'prop-default', 
        comment: Optional[str] = None, 
        encoding: Optional[str] = None
    ):
        self.value = value.strip()
        self.permissions = permissions
        self.comment = comment
        self.encoding = encoding

    def __eq__(self, other):
        return all((
            self.value == other.value,
            self.permissions == other.permissions,
            self.comment == other.comment,
            self.encoding == other.encoding
        ))

    def __str__(self):
        return f'''PropertyElement with value={self.value}, permissions={self.permissions},
        comment={self.comment}, encoding={self.encoding}'''

    def __hash__(self):
        return hash(str(self))



###########
# functions
###########
def check_and_prepare_values(
    value: Union[PropertyElement, Iterable[PropertyElement], None],
    values: Union[Iterable[PropertyElement], None],
    name: str,
    calling_resource: str = ''
) -> list[PropertyElement]:
    
    assert xor(value is None, values is None), 'You cannot provide a "value" and a "values" at the same time!'
    
    if values is not None:
        valueslist = [v for v in values if v is not None]
        values_new = sorted(set(valueslist), key=lambda x: valueslist.index(x))
    
    else: 
        assert value is not None
        if isinstance(value, Iterable):
            valueslist = [v for v in value if v is not None]
            values_new = sorted(set(valueslist), key=lambda x: valueslist.index(x))
            if len(values_new) > 1:
                handle_warnings(
                    f'There are contradictory {name} values for {calling_resource}: {[v.value for v in value]}'
                )
        else:  #isinstance(value, PropertyElement)
            values_new = [value, ]
    
    return values_new


def make_root(shortcode: str, default_ontology: str) -> etree._Element:
    root = etree.Element(
        _tag='{%s}knora' % (xml_namespace_map[None]),
        attrib={
            str(etree.QName('http://www.w3.org/2001/XMLSchema-instance', 'schemaLocation')):
            'https://dasch.swiss/schema ' + \
            'https://raw.githubusercontent.com/dasch-swiss/dsp-tools/main/knora/dsplib/schemas/data.xsd',
            'shortcode': shortcode,
            'default-ontology': default_ontology
        },
        nsmap=xml_namespace_map
    )
    return root


def append_permissions(root_element: etree._Element) -> etree._Element:
    PERMISSIONS = E.permissions
    ALLOW = E.allow
    # lxml.builder.E is a more sophisticated element factory than etree.Element.
    # E.tag is equivalent to E('tag') and results in <tag>

    res_default = PERMISSIONS(id='res-default')
    res_default.append(ALLOW('V', group='UnknownUser'))
    res_default.append(ALLOW('V', group='KnownUser'))
    res_default.append(ALLOW('CR', group='Creator'))
    res_default.append(ALLOW('CR', group='ProjectAdmin'))
    root_element.append(res_default)

    res_restricted = PERMISSIONS(id='res-restricted')
    res_restricted.append(ALLOW('RV', group='UnknownUser'))
    res_restricted.append(ALLOW('V', group='KnownUser'))
    res_restricted.append(ALLOW('CR', group='Creator'))
    res_restricted.append(ALLOW('CR', group='ProjectAdmin'))
    root_element.append(res_restricted)

    prop_default = PERMISSIONS(id='prop-default')
    prop_default.append(ALLOW('V', group='UnknownUser'))
    prop_default.append(ALLOW('V', group='KnownUser'))
    prop_default.append(ALLOW('CR', group='Creator'))
    prop_default.append(ALLOW('CR', group='ProjectAdmin'))
    root_element.append(prop_default)

    prop_restricted = PERMISSIONS(id='prop-restricted')
    prop_restricted.append(ALLOW('RV', group='UnknownUser'))
    prop_restricted.append(ALLOW('V', group='KnownUser'))
    prop_restricted.append(ALLOW('CR', group='Creator'))
    prop_restricted.append(ALLOW('CR', group='ProjectAdmin'))
    root_element.append(prop_restricted)

    return root_element


def make_resource(
    label: str,
    restype: str,
    id: str,
    ark: str = None,
    permissions: str = 'res-default'
) -> etree._Element:

    kwargs = {
        'id': id,
        'label': label,
        'restype': restype,
        'permissions': permissions,
        'nsmap': xml_namespace_map
    }
    if ark is not None:
        kwargs['ark'] = ark

    resource_ = etree.Element(
        '{%s}resource' % (xml_namespace_map[None]),
        **kwargs
    )
    return resource_


def make_bitstream_prop(path: str, calling_resource: str = '') -> etree._Element:
    '''Path is the path to the file that shall be uploaded'''
    assert os.path.isfile(path), \
        f'The following is not the path to a valid file:\n' +\
        f'resource "{calling_resource}"\n' +\
        f'path     "{path}"'

    prop_ = etree.Element('{%s}bitstream' % (xml_namespace_map[None]), nsmap=xml_namespace_map)
    prop_.text = path
    return prop_


def make_boolean_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]],
    calling_resource: str = ''
) -> Union[etree._Element, etree._Comment]:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised).
    '''

    # check and validate input
    if isinstance(value, PropertyElement):
        value_new = value
    else: # isinstance(value, Iterable)
        if len(set(value)) == 0:
            value_new = PropertyElement('false')
        elif len(set(value)) == 1:
            value_new = list(value)[0]
        else:  # len(set(value)) > 1:
            handle_warnings(
                f'There are contradictory {name} values for {calling_resource}: {set(value)}'
            )
            return etree.Comment(f'TODO: {name} has contradictory boolean values')

    true_values = ('true', 'True', '1', 1, 'Yes', 'yes')
    false_values = ('false', 'False', '0', 0, 'No', 'no', '', 'None')

    if pd.isnull(value_new.value) or value_new.value in false_values:
        value_new.value = 'false'
    elif value_new.value in true_values:
        value_new.value = 'true'
    else:
        handle_warnings(
            f'{value} is an invalid boolean format for property {name} in {calling_resource}'
        )

    # make xml structure of the value
    prop_ = etree.Element(
        '{%s}boolean-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    kwargs = { 'permissions': value_new.permissions }
    if check_notna(value_new.comment):
        kwargs['comment'] = value_new.comment
    value_ = etree.Element(
        '{%s}boolean' % (xml_namespace_map[None]),
        **kwargs,
        nsmap=xml_namespace_map
    )
    value_.text = value_new.value
    prop_.append(value_)
    
    return prop_


def make_color_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # check value type
    for val in values_new:
        assert re.search(r'^#[0-9a-f]{6}$', val.value) is not None, \
            f'The following is not a valid color:\n' +\
            f'resource "{calling_resource}"\n' +\
            f'property "{name}"\n' +\
            f'value    "{val.value}"'

    prop_ = etree.Element(
        '{%s}color-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}color' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)

    return prop_


def make_date_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    DSP allows multiple dates/date ranges.
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # check value type
    for val in values_new:
        containsDate = isinstance(find_date_in_string(val.value), str)
        isDate = bool(re.search(
            r'(GREGORIAN:|JULIAN:)?(CE:|BCE:)?(\d{4})?(-\d{1,2})?(-\d{1,2})?'
            r'(:CE|:BCE)?(:\d{4})?(-\d{1,2})?(-\d{1,2})?', 
            val.value
        ))

        assert containsDate or isDate, \
            f'The following is not a valid calendar date:\n' +\
            f'resource "{calling_resource}"\n' +\
            f'property "{name}"\n' +\
            f'value    "{val.value}"'

    # make xml structure of the value
    prop_ = etree.Element(
        '{%s}date-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}date' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    
    return prop_


def make_decimal_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # check value type
    for val in values_new:
        assert str(float(val.value)) == val.value, \
            f'The following is not a valid decimal number:\n' +\
            f'resource "{calling_resource}"\n' +\
            f'property "{name}"\n' +\
            f'value    "{val.value}"'

    prop_ = etree.Element(
        '{%s}decimal-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}decimal' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    
    return prop_


def make_geometry_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    Warning: It is rather unusual to create a geometry-prop.
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # check value type
    for val in values_new:
        try:
            json.loads(val.value)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                msg = str(e) + f'The following is not a valid Geometry JSON:\n' +\
                    f'resource: "{calling_resource}"\n' +\
                    f'property: "{name}"\n' +\
                    f'value:    "{val.value}"',
                doc=e.doc,
                pos=e.pos) from e

    prop_ = etree.Element(
        '{%s}geometry-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}geometry' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    return prop_


def make_geoname_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # check value type
    for val in values_new:
        assert re.search(r'^[0-9]+$', val.value) is not None, \
            f'The following is not a valid geoname ID:\n' +\
            f'resource "{calling_resource}"\n' +\
            f'property "{name}"\n' +\
            f'value    "{val.value}"'

    prop_ = etree.Element(
        '{%s}geoname-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}geoname' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    
    return prop_


def make_integer_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # check value type
    for val in values_new:
        assert re.search(r'^\d+$', val.value) is not None, \
            f'The following is not a valid integer:\n' +\
            f'resource "{calling_resource}"\n' +\
            f'property "{name}"\n' +\
            f'value    "{val.value}"'

    prop_ = etree.Element(
        '{%s}integer-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}integer' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    
    return prop_


def make_interval_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # check value type
    for val in values_new:
        assert re.search(r'^[0-9]+\.[0-9]+:[0-9]+\.[0-9]+$', val.value) is not None, \
            f'The following is not a valid interval:\n' +\
            f'resource "{calling_resource}"\n' +\
            f'property "{name}"\n' +\
            f'value    "{val.value}"'

    prop_ = etree.Element(
        '{%s}interval-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}interval' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    
    return prop_


def make_list_prop(
    list_name: str,
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # make xml structure of the valid values
    prop_ = etree.Element(
        '{%s}list-prop' % (xml_namespace_map[None]),
        list=list_name,
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}list' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)

    return prop_


def make_resptr_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    prop_ = etree.Element(
        '{%s}resptr-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}resptr' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    
    return prop_


def make_text_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # make xml structure of the valid values
    prop_ = etree.Element(
        '{%s}text-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        if check_notna(val.encoding):
            kwargs['encoding'] = val.encoding
        else:
            kwargs['encoding'] = 'utf8'
        value_ = etree.Element(
            '{%s}text' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    
    return prop_


def make_time_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # check value type
    for val in values_new:
        assert re.search(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})?$', val.value) is not None, \
            f'The following is not a valid time:\n' +\
            f'resource "{calling_resource}"\n' +\
            f'property "{name}"\n' +\
            f'value    "{val.value}"'
    
    # make xml structure of the valid values
    prop_ = etree.Element(
        '{%s}time-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}time' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    
    return prop_


def make_uri_prop(
    name: str,
    value: Union[PropertyElement, Iterable[PropertyElement]] = None,
    values: Iterable[PropertyElement] = None,
    calling_resource: str = ''
) -> etree._Element:
    '''
    'value' can be a PropertyElement or a list of PropertyElements which should be equal 
    (otherwise a warning is raised). 
    'values' is a list of PropertyElements which must be distinct from each other.
    '''

    # check the input: prepare a list with valid values
    values_new = check_and_prepare_values(
        value=value,
        values=values,
        name=name,
        calling_resource=calling_resource
    )

    # make xml structure of the valid values
    prop_ = etree.Element(
        '{%s}uri-prop' % (xml_namespace_map[None]),
        name=name,
        nsmap=xml_namespace_map
    )
    for val in values_new:
        kwargs = { 'permissions': val.permissions }
        if check_notna(val.comment):
            kwargs['comment'] = val.comment
        value_ = etree.Element(
            '{%s}uri' % (xml_namespace_map[None]),
            **kwargs,
            nsmap=xml_namespace_map
        )
        value_.text = val.value
        prop_.append(value_)
    
    return prop_



###########################
# global variables - part 2
###########################
proptype_2_function = {
    'bitstream': make_bitstream_prop,
    'boolean-prop': make_boolean_prop,
    'color-prop': make_color_prop,
    'date-prop': make_date_prop,
    'geometry-prop': make_geometry_prop,
    'geoname-prop': make_geoname_prop,
    'integer-prop': make_integer_prop,
    'interval-prop': make_interval_prop,
    'list-prop': make_list_prop,
    'resptr-prop': make_resptr_prop,
    'text-prop': make_text_prop,
    'uri-prop': make_uri_prop
}
single_value_functions = [
    make_bitstream_prop,
    make_boolean_prop
]



###############
# main function
###############
def main():

    # general preparation
    # -------------------
    onto_file: dict[str, Any] = json.load(open('LIMC.json'))
    main_df = pd.read_csv('data/LIMC-3.csv', dtype='str', sep=';')
    # main_df.drop_duplicates(inplace = True)
    # main_df.dropna(how = 'all', inplace = True)
    max_prop_count = int(list(main_df)[-1].split('_')[0])
    root = make_root(onto_file['project']['shortcode'], onto_file['project']['shortname'])
    root = append_permissions(root)
    current_resource_id: str = ''
    
    # mock-up: if the real images are not available, create dummy images
    for file in main_df['file']:
        if pd.notna(file):
            os.makedirs(pathlib.Path(file).parent, exist_ok=True)
            #pathlib.Path(pathlib.Path(file)).touch(exist_ok=True)
            shutil.copy(src='data/Dummy.jpg', dst=file)

    # create all resources
    # --------------------
    for index, row in main_df.iterrows():

        # there are two cases: either the row is a resource-row or a property-row.
        assert xor(
            check_notna(row['id']),
            check_notna(row['prop name'])
        ), \
            f'Exactly 1 of the 2 columns "id" and "prop name" must have an entry. ' + \
            f'Excel row no. {int(str(index))+2} has too many/too less entries:\n' + \
            f'id:        "{row["id"]}"\n' + \
            f'prop name: "{row["prop name"]}"'

        # case resource-row
        if check_notna(row['id']):
            current_resource_id = str(row['id'])
            # previous resource is finished, now a new resource begins. in all cases (except for
            # the very first iteration), a previous resource exists. if it exists, append it to root.
            if 'resource' in locals():
                root.append(resource)
            kwargs_resource = {
                'restype': str(row['restype']),
                'label': str(row['label']),
                'permissions': str(row['permissions']),
                'id': str(row['id'])
            }
            if check_notna(row['ark']):
                kwargs_resource['ark'] = str(row['ark'])
            resource = make_resource(**kwargs_resource)
            
            if check_notna(row['file']):
                resource.append(make_bitstream_prop(
                    path=str(row['file']), 
                    calling_resource=current_resource_id
                ))

        # case property-row
        else: # check_notna(row['prop name']) == True
            # based on the property type, the right function has to be chosen
            make_prop_function = proptype_2_function[str(row['prop type'])]

            # every property contains i elements, which are represented in the Excel as groups of
            # columns namend {i_value, i_encoding, i_res ref, i_permissions, i_comment}. Depending
            # on the property type, some of these items are NA.
            # Thus, prepare list of PropertyElement objects, with each PropertyElement containing only
            # the existing items.
            property_elements: list[PropertyElement] = []
            for i in range(1, max_prop_count + 1):
                if check_notna(row[f'{i}_value']):
                    kwargs_propelem = {
                        'value': str(row[f'{i}_value']),
                        'permissions': str(row[f'{i}_permissions'])
                    }
                    if check_notna(row[f'{i}_comment']):
                        kwargs_propelem['comment'] = str(row[f'{i}_comment'])
                    if check_notna(row[f'{i}_encoding']):
                        kwargs_propelem['encoding'] = str(row[f'{i}_encoding'])

                    property_elements.append(PropertyElement(**kwargs_propelem))

            # create the property and append it to resource
            kwargs_propfunc = {
                'name': row['prop name'],
                'calling_resource': current_resource_id
            }
            if make_prop_function in single_value_functions or len(property_elements) == 1:
                kwargs_propfunc['value'] = property_elements
            else:
                kwargs_propfunc['values'] = property_elements
            if check_notna(row['prop list']):
                kwargs_propfunc['list_name'] = row['prop list']
            
            resource.append(make_prop_function(**kwargs_propfunc))

    # append the resource of the very last iteration of the for loop
    root.append(resource)

    # write file
    # ----------
    et = etree.ElementTree(root)
    etree.indent(et, '    ')
    with open('data/output.xml', 'wb') as f:
        et.write(f, encoding='utf-8', xml_declaration=True, pretty_print=True)


if __name__ == '__main__':
    main()
