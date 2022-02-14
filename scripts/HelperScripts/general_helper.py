import copy
import datetime
import difflib
import json
import re
import unicodedata
from typing import Any, Generator, Union

from lxml import etree

from HelperScripts.warnings_handler import handle_warnings


def check_notna(string: Any) -> bool:
    return isinstance(string, str) and bool(re.search(r'\w', string))




def create_onto_list_mapping(
    onto_file: dict, 
    list_name: str,
    autocorrections = dict()
) -> dict:
    '''
    Accepts an onto file and the name of a list in this onto. Lists may be nested: Each node 
    consists of a name, a label, and optionally of a list of subnodes.
    Returns a dictionary of the form {label: name} of all list entries.
    :param onto_file: dict-like object, e.g. retrieved from json.load(open(path_to_onto))
    '''

    for numbered_json_obj in onto_file['project']['lists']:
        if numbered_json_obj['name'] == list_name:
            onto_subset = numbered_json_obj['nodes']
            break

    res = {}
    for label, name in name_label_mapper_iterator(onto_subset):
        res[label] = name

    for typo, corr in autocorrections.items():
        res[typo] = res[corr]

    res = {key: res[key] for key in sorted(res.keys())}

    return res




def name_label_mapper_iterator(onto_subset: list):
    "returns (label, name) pairs of onto list entries"
    for node in onto_subset:
        # node is the json object containing the entire onto-list
        if 'nodes' in node:
            # 'nodes' is the json sub-object containing the entries of the onto-list
            for value in name_label_mapper_iterator(node['nodes']):
                yield value
                # 'value' is a (label, name) pair of a single list entry
        if 'name' in node:
            yield (node['labels']['en'], node['name'])
                # the actual values of the name and the label




def simplify_name(value: str) -> str:
    """
    This function simplifies a given value in order to use it as node name

    Args:
        value: The value to be simplified

    Returns:
        str: The simplified value

    """
    simplified_value = str(value).lower()

    # normalize characters (p.ex. ä becomes a)
    simplified_value = unicodedata.normalize('NFKD', simplified_value)

    # replace forward slash and whitespace with a dash
    simplified_value = re.sub('[/\\s]+', '-', simplified_value)

    # delete all characters which are not letters, numbers or dashes
    simplified_value = re.sub('[^A-Za-z0-9\\-]+', '', simplified_value)

    return simplified_value





def find_date_in_string(string: str, calling_resource = '') -> Union[str, None]:

    if not isinstance(string, str):
        return None
    
    startdate: Any = None
    enddate: Any = None
    startyear: Any = None
    endyear: Any = None

    iso_date = re.search(r'((?:1[8-9][0-9][0-9])|(?:20[0-2][0-9]))[_-]([0-1][0-9])[_-]([0-3][0-9])', string)
        # template: 2021-01-01 or 2015_01_02
    eur_date_range = re.search(r'([0-3]?[0-9])[\./]([0-1]?[0-9])\.?-([0-3]?[0-9])[\./]([0-1]?[0-9])[\./]((?:1[8-9][0-9][0-9])|(?:20[0-2][0-9]))', string)
        # template: 26.2.-24.3.1948
    eur_date = list(re.finditer(r'([0-3]?[0-9])[\./]([0-1]?[0-9])[\./]((?:1[8-9][0-9][0-9])|(?:20[0-2][0-9]))', string))
        # template: 31.4.2021    5/11/2021    1.12.1973 - 6.1.1974
    monthname_date = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December) ([0-3]?[0-9]), ?((?:1[8-9][0-9][0-9])|(?:20[0-2][0-9]))', string)
        # template: March 9, 1908   March 5,1908    May 11, 1906
    year_only = re.search(r'(?:1[8-9][0-9][0-9])|(?:20[0-2][0-9])', string)
        # template: 1907    1886/7    1833/34     1849/1850


    if iso_date and iso_date.lastindex == 3:
        year = int(iso_date.group(1))
        month = int(iso_date.group(2))
        day = int(iso_date.group(3))
        if year <= 2022 and month <= 12 and day <= 31:
            startdate = datetime.date(year, month, day)
            enddate = startdate

    elif eur_date_range and eur_date_range.lastindex == 5:
        startday = int(eur_date_range.group(1))
        startmonth = int(eur_date_range.group(2))
        endday = int(eur_date_range.group(3))
        endmonth = int(eur_date_range.group(4))
        startyear = int(eur_date_range.group(5))
        endyear = startyear
        if startyear <= 2022 and startmonth <= 12 and startday <= 31:
            startdate = datetime.date(startyear, startmonth, startday)
            enddate = datetime.date(endyear, endmonth, endday)
            if not enddate >= startdate:
                handle_warnings(f'Date parsing error in resource {calling_resource}: Enddate ({enddate.isoformat()}) is earlier than startdate ({startdate.isoformat()})')
                enddate = startdate

    elif eur_date and eur_date[0].lastindex == 3:
        startyear = int(eur_date[0].group(3))
        startmonth = int(eur_date[0].group(2))
        startday = int(eur_date[0].group(1))
        if startyear <= 2022 and startmonth <= 12 and startday <= 31:
            startdate = datetime.date(startyear, startmonth, startday)
            enddate = startdate
        if len(eur_date) == 2 and eur_date[1].lastindex == 3:
            endyear = int(eur_date[1].group(3))
            endmonth = int(eur_date[1].group(2))
            endday = int(eur_date[1].group(1))
            if endyear <= 2022 and endmonth <= 12 and endday <= 31:
                enddate = datetime.date(endyear, endmonth, endday)
                if not enddate >= startdate:
                    handle_warnings(f'Date parsing error in in resource {calling_resource}: Enddate ({enddate.isoformat()}) is earlier than startdate ({startdate.isoformat()})')
                    enddate = startdate

    elif monthname_date and monthname_date.lastindex == 3:
        year = int(monthname_date.group(3))
        month = int(datetime.datetime.strptime(monthname_date.group(1), '%B').strftime('%m'))
            # parse full monthname with strptime (%B), then convert to number with strftime (%m)
        day = int(monthname_date.group(2))
        if year <= 2022 and month <= 12 and day <= 31:
            startdate = datetime.date(year, month, day)
            enddate = startdate
            
    elif year_only:
        startyear = year_only.group(0)
        endyear = startyear
        # optionally, there is a second year:
        secondyear = re.search(r'\d+/(\d+)', string)
        if secondyear:
            secondyear = secondyear.group(1)
            secondyear = startyear[0:-len(secondyear)] + secondyear
            if int(secondyear) != int(startyear) + 1:
                handle_warnings(f'Error in resource {calling_resource}: second year of {string} could not be parsed, assume {int(startyear) + 1}')
            endyear = int(startyear) + 1


    if startdate is not None and enddate is not None:
        return f'GREGORIAN:CE:{startdate.isoformat()}:CE:{enddate.isoformat()}'
    elif startyear is not None and endyear is not None:
        return f'GREGORIAN:CE:{startyear}:CE:{endyear}'
    else:
        return None


    # Fancy, because auto-extracts many date formats out of strings, but discouraged, produces too many false positives:
    # datetime_obj = parser.parse(string, fuzzy = True, ignoretz = True)





def make_xs_id_compatible(string: str) -> str:
    
    # see http://www.datypic.com/sc/xsd/t-xsd_ID.html

    if any([isinstance(string, str) == False, string == '', string == None]):
        return string
    else:
        # if start of string is neither letter nor underscore, add an underscore
        res = re.sub(r'^(?=[^A-Za-z_])', '_', string)

        # to make the xs id unique, create a pseudo-hash based on the position and kind of illegal 
        # characters found in the original string, and add it to the end of the result string 
        illegal_chars = ''
        for match in re.finditer(pattern = r'[^\d\w_\-\.]', string = string):
            illegal_chars = illegal_chars + str(ord(match.group(0))) + str(match.start())
        if illegal_chars != '':
            res = res + '_' + illegal_chars

        # replace all illegal characters by underscore
        res = re.sub(r'[^\d\w_\-\.]', '_', res)

        return res





def create_onto_excel_list_mapping(
    onto_file: dict, 
    list_name: str, 
    excel_values,
    autocorrections = dict()
) -> dict:

    """
    This function takes as arguments an onto-list (dict from json), and an excel column 
    with list-values. It creates a mapping between the two and returns it in a flat dictionary. Values 
    are only matched if the similarity is > 0.6, otherwise a warning is raised. 
    
    :params
     - onto_file: dict-like object, e.g. retrieved from json.load(open(path_to_onto))
     - list_name: position of the json-object in onto.json > project > lists
     - excel_values: iterable of strings
    """

    excel_values = {elem.strip() for elem in excel_values if check_notna(elem)}

    # read the list of the onto (works also for nested lists)
    onto_subset = list()
    for elem in onto_file['project']['lists']:
        if elem['name'] == list_name:
            onto_subset = elem['nodes']
    
    onto_label_2_name = {label: name for label, name in nested_dict_values_iterator(onto_subset)}

    # build dictionaries with the mapping, based on string similarity
    res = dict()
    for excel_value in excel_values:
        matches = difflib.get_close_matches(
            word = autocorrections.get(excel_value, re.sub(r'\s+|\W', ' ', excel_value)),
            possibilities = onto_label_2_name.keys(), 
            n = 1, 
            cutoff = 0.6
        )
        if len(matches) == 1:
            res[excel_value] = onto_label_2_name[matches[0]]
        else:
            handle_warnings(
                f'Did not find a close match to the excel list entry ***{excel_value}*** among the values in '
                + f'the onto list ***{list_name}***, please add it to the autocorrections.')
    
    res = {key: res[key] for key in sorted(res.keys())}
    return res



def nested_dict_values_iterator(dicts: list) -> Generator[tuple, None, None]:
    ''' This function accepts a list of nested dictionaries as argument
        and iteratively yields its (label, name) pairs.
        Credits: https://thispointer.com/python-iterate-loop-over-all-nested-dictionary-values/
    '''

    for dict in dicts:
        if 'nodes' in dict:
            for value in nested_dict_values_iterator(dict['nodes']):
                yield value
        if 'labels' in dict:
            label = dict['labels'].get('en', dict['labels'].get('de'))
            name = dict['name']
            yield label, name



def make_list_from_excel_multilang_single_col(
    excel_col,
    listname,
    lang_0 = 'en',
    lang_1 = 'fr',
    lang_separator = 'string that will never appear in real data: 0978q3w4$¨äöü§‘æ¶¢'
):
    '''
    save a json with the onto list produced from a single excel column that has multilang list entries in it 
    For example, if an excel column contains such values:
     - Ankara Valisi/Ankara Governor
     - Amerika Sefareti/US Consulate
    
    the parameters would be as follows: 
     - excel_col = any iterable, e.g. list, pandas.Series, set, ...
     - listname = 'institution'
     - lang_0 = 'tr'
     - lang_1 = 'en'
     - lang_separator = '/'

    '''
    list_nodes = list()
    excel_col = {elem for elem in excel_col if check_notna(elem)}

    for elem in excel_col:
        elem = elem.split(lang_separator)
        elem = [re.sub(r'\s+|\W', ' ', item.strip()) for item in elem]
        if len(elem) == 1 and elem[0] not in list_nodes:
            # don't overwrite an old entry, that would delete the translation
            list_nodes.append({'name': simplify_name(elem[0]), 'labels': {lang_0: elem[0], lang_1: elem[0]}})
        elif len(elem) > 1:
            # check if the current node is distinct enough from the existing nodes to be appended
            list_nodes_item_is_distinct = list()
            for node in list_nodes.copy():
                lang_0_matches = difflib.get_close_matches(
                    word = node['labels'][lang_0], 
                    possibilities = [elem[0], ],
                    n = 1, 
                    cutoff = 0.6
                )
                lang_1_matches = difflib.get_close_matches(
                    word = node['labels'][lang_1], 
                    possibilities = [elem[1], ],
                    n = 1, 
                    cutoff = 0.6
                )
                if len(lang_0_matches + lang_1_matches) < 2:
                    list_nodes_item_is_distinct.append(True)
                else:
                    list_nodes_item_is_distinct.append(False)
                    handle_warnings(f'List{listname}: Skipped "{elem[0]}/{elem[1]}" because "{node["labels"][lang_0]}/{node["labels"][lang_1]}" is already in list')
            if all(list_nodes_item_is_distinct):
                nodename = f'{listname}-{simplify_name(elem[0])}'
                i = 2
                while nodename in list_nodes:
                    if i == 2:
                        nodename = f'{nodename}-2'
                    else:
                        nodename = re.sub(r'-\d+$', f'-{i}', nodename)
                    i = i + 1
                list_nodes.append({'name': nodename, 'labels': {lang_0: elem[0], lang_1: elem[1]}})
    onto_list = {
        'name': listname, 
        'labels': {lang_0: listname, lang_1: listname}, 
        'comments': {lang_0: listname, lang_1: listname}, 
        'nodes': list_nodes
    }
    with open(f'{listname}_list.json', 'w') as f:
        f.write(json.dumps(onto_list, indent = 4))




def make_list_from_excel_monolang(
    excel_col,
    listname,
    lang_label = 'en',
    pseudo_lang_label = None,
    autocorrections = dict(),
):
    '''
    save a json with an onto list from an excel column (any iterable, e.g. list, pandas.Series, set, ...) 
    that has list entries in it. If you wish to add a second language label that contains the same text as 
    the main language, provide it with the parameter pseudo_lang_label.
    '''

    list_nodes = list()
    excel_col = {re.sub(r'\s+', ' ', elem.strip()) for elem in excel_col if check_notna(elem)}
    excel_col = {autocorrections.get(elem, elem) for elem in excel_col}

    for elem in excel_col:
        nodename = f'{listname}-{simplify_name(elem)}'
        i = 2
        while nodename in list_nodes:
            if i == 2:
                nodename = f'{nodename}-2'
            else:
                nodename = re.sub(r'-\d+$', f'-{i}', nodename)
            i = i + 1
        if pseudo_lang_label:
            list_nodes.append({'name': nodename, 'labels': {lang_label: elem, pseudo_lang_label: elem}})
        else:
            list_nodes.append({'name': nodename, 'labels': {lang_label: elem}})
    
    list_nodes.sort(key = lambda x: x.get('name'))
    
    if pseudo_lang_label:
        onto_list = {
            'name': listname, 
            'labels': {lang_label: listname, pseudo_lang_label: listname}, 
            'comments': {lang_label: listname, pseudo_lang_label: listname}, 
            'nodes': list_nodes
        }
    else:
        onto_list = {
            'name': listname, 
            'labels': {lang_label: listname}, 
            'comments': {lang_label: listname}, 
            'nodes': list_nodes
        }
    
    with open(f'{listname}_list.json', 'w') as f:
        f.write(json.dumps(onto_list, indent = 4))






def remove_circular_resptrs(
    root_etree_element: etree.ElementBase, 
    xml_namespace_map: dict, 
    resource_type: str, 
    resptr_prop_name: str,
    num_of_links_to_follow: int = 3
) -> etree.ElementBase:
    '''
    This function resolves circular dependencies among resources. I works only for one defined resource_type and one defined
    resptr_prop_name. It only works if the direction of the link doesn't matter, so if the resptr-prop can be inversed.

    Args:
    root_etree_element: etree.Element of the root element (<knora> tag) of the xml. It can contain many resources of 
    several types. 
    xml_namespace_map: a Python dictionary with the namespace definitions of a valid knora xml. This is necessary for 
    a correct lookup of the tags. Example: {None: 'https://dasch.swiss/schema', 'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}
    resource_type: The type of resource to search through, e.g. ':Photo' (<resource label="xyz" restype=":Photo" ...>)
    resptr_prop_name: Only links with this name will be searched, e.g. ':hasLinkTo' (<resptr-prop name=":hasLinkTo">)

    Returns:
    an etree.Element with the same knora xml, but without circular dependencies.

    Example:
    In the following input, the last link leads to circularity. So its direction is swapped: 
    Input:  res_1 :hasLinkTo res_2      res_2 :hasLinkTo res_3      res_3 :hasLinkTo res_1
    Output: res_1 :hasLinkTo res_2      res_2 :hasLinkTo res_3      res_1 :hasLinkTo res_3
    '''
    
    # build a dict of all resources and their resptr-links, e.g. {res_1: [], res_2: [res_9, res_10], ...}
    res_2_resptrs = dict()
    for resource in [x for x in root_etree_element.getiterator() if x.get('restype') == resource_type]:
        resptr_prop = [x for x in resource.findall('resptr-prop', namespaces = xml_namespace_map) if x.get('name') == resptr_prop_name]
        if len(resptr_prop) == 0:
            res_2_resptrs[resource.get('id')] = []
        else:
            resptrs = [elem.text for elem in resptr_prop[0].findall('resptr', namespaces = xml_namespace_map)]
            res_2_resptrs[resource.get('id')] = resptrs

    # build a dict that contains only the problematic resptrs
    circular_res_2_resptrs = identify_circular_resptrs(res_2_resptrs)
    if len(circular_res_2_resptrs) == 0:
        return root_etree_element
    
    # build two dicts with the changes that must be made. The keys of the dicts are the resources that contain problematic
    # resptr-links, and the values are a list of the resptr-links that must be added/removed.
    to_remove = []
    to_add = []
    resources = set(circular_res_2_resptrs.keys())
    for res in resources:
        rem, add = compute_dir_swaps_of_resource(res, circular_res_2_resptrs, num_of_links_to_follow)
        to_remove = to_remove + rem
        to_add = to_add + add
    to_remove_dict = {outer_elem[0]: [elem[1] for elem in to_remove if elem[0] == outer_elem[0]] for outer_elem in to_remove}
    to_add_dict = {outer_elem[0]: [elem[1] for elem in to_add if elem[0] == outer_elem[0]] for outer_elem in to_add}

    # iterate through the xml element, and check for every resource if it appears in one of the dicts with the changes.
    # only add resptrs if they are not already present. If the only resptr is removed from a resptr-prop, delete it.
    for resource in root_etree_element.getchildren():
        id = resource.get('id')
        resptr_prop = resource.find('resptr-prop', namespaces = xml_namespace_map)
        if resptr_prop is None:
            continue
        if id in to_add_dict:
            for elem in to_add_dict[id]:
                if elem not in [resptr.text for resptr in resptr_prop.findall('resptr', namespaces = xml_namespace_map)]:
                    new_resptr = etree.Element('resptr', permissions = 'prop-default', nsmap = xml_namespace_map)
                    new_resptr.text = elem
                    resptr_prop.append(new_resptr)
        if id in to_remove_dict:
            for resptr in resptr_prop.findall('resptr', namespaces = xml_namespace_map):
                if resptr.text in to_remove_dict[id]:
                    resptr_prop.remove(resptr)
            if len(resptr_prop.getchildren()) == 0:
                resource.remove(resource.find('resptr-prop', namespaces = xml_namespace_map))

    return root_etree_element




def compute_dir_swaps_of_resource(res: str, circular_res_2_resptrs: dict, num_of_links_to_follow: int):
    to_remove = []
    to_add = []
    chain = [res, ]
    for target1 in circular_res_2_resptrs.copy()[res]:
        chain.append(target1)
        target2_list = copy.deepcopy(circular_res_2_resptrs)[target1]
        for target2 in target2_list:
            if target2 in chain:
                # swap direction of link target1 -> target2
                to_remove.append((target1, target2))
                circular_res_2_resptrs[target1].remove(target2)
                if target1 not in circular_res_2_resptrs[target2]:
                    to_add.append((target2, target1))
                    circular_res_2_resptrs[target2].append(target1)
                continue
            chain.append(target2)
            target3_list = copy.deepcopy(circular_res_2_resptrs)[target2]
            for target3 in target3_list:
                if target3 in chain:
                    # swap direction of link target2 -> target3
                    to_remove.append((target2, target3))
                    circular_res_2_resptrs[target2].remove(target3)
                    if target2 not in circular_res_2_resptrs[target3]:
                        circular_res_2_resptrs[target3].append(target2)
                        to_add.append((target3, target2))
            chain.remove(target2)
        chain.remove(target1)

    return to_remove, to_add








def identify_circular_resptrs(res_2_resptrs: dict) -> dict:
    '''
    Purge a dict of the form {resource: [resptr_links]}, so that only the resources that can't be created remain.
    All resources and resptr_links must be strings (identifiers of the resources).
    The keys of the returned dict are the resources that can't be created, and the values are a list of the circular 
    resptr-links that prevent the resource from being created.
    '''
    ok_resources = []
    notok_resources = []
    cnt = 0
    notok_len = 9999999
    while len(res_2_resptrs) > 0 and cnt < 10000:
        for resource, resptrs in res_2_resptrs.items():
            if len(resptrs) == 0:
                ok_resources.append(resource)
            else:
                ok = True
                for resptr in resptrs:
                    if resptr not in ok_resources:
                        ok = False
                if ok:
                    ok_resources.append(resource)
                else:
                    notok_resources.append(resource)
        res_2_resptrs = {k: v for k, v in res_2_resptrs.items() if k in notok_resources}
        if len(notok_resources) == notok_len:
            result = dict()
            for notok_res in notok_resources:
                resptrs = res_2_resptrs[notok_res]
                result[notok_res] = sorted([x for x in resptrs if x not in ok_resources])
            return result
        notok_len = len(notok_resources)
        notok_resources = []
        cnt += 1
    return dict()
