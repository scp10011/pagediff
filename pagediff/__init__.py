import json
import difflib

import magic
import regex
import requests
import lxml.etree
import jsonpath_rw
from lxml.html import tostring

MIME = magic.Magic(mime=True)
SPECIAL = "|".join(("\[", "\]", '"', "'", "\s", "\t", "\n", "\r"))
UNVISIBLE = regex.compile(b"[^ -~]")
JsonpRegex = regex.compile(b"^\w*\((?<json>[\{|\[].*[\}|\]])\)$")
JsonRegex = regex.compile(b"^[\{|\[].*[\}|\]]$")
SpecialRegex = regex.compile(SPECIAL)


def jsonxpath(obj, path):
    path = jsonpath_rw.parse(path)
    value = path.find(obj)
    if not value:
        return None
    return value[0].value


def iterjson(obj, path=""):
    if isinstance(obj, list):
        for index, x in enumerate(obj):
            _path = path + "[%d]" % index
            yield x, _path
            if isinstance(x, (dict, list)):
                for o, p in iterjson(x, _path):
                    yield o, p
    elif isinstance(obj, dict):
        for index, (k, v) in enumerate(obj.items()):
            if SpecialRegex.search(k):
                k = '"%s"' % k
            _path = path + ".%s" % k if path else k
            yield v, _path
            if isinstance(v, (dict, list)):
                for o, p in iterjson(v, _path):
                    yield o, p


def json_diff(d1, d2, difference=None, sign=None):
    diff = []
    difference = difference or set()
    for dom_1, path in iterjson(d1):
        dom_2 = jsonxpath(d2, path)
        if dom_1 == dom_2:
            continue
        elif (
            isinstance(dom_2, (int, str))
            and sign
            and any(i in str(dom_2) for i in sign)
        ):
            continue
        else:
            diff.append(path)
    index, maxlen = 0, len(diff) - 1
    while index < maxlen:
        if diff[index] in diff[index + 1]:
            diff.remove(diff[index])
            maxlen -= 1
        else:
            index += 1
    diff = set(diff)
    diff.difference_update(difference)
    return diff


def xml_diff(d1, d2, difference=None, sign=None):
    diff = []
    difference = difference or set()
    tree = lxml.etree.ElementTree(d1)
    for d1_iter in d1.iter():
        xpath = tree.getpath(d1_iter)
        try:
            if tostring(d1_iter) == tostring(d2.xpath(xpath)[0]):
                continue
            else:
                diff.append(xpath)
        except IndexError:
            diff.append(xpath)
    index, maxlen = 0, len(diff) - 1
    while index < maxlen:
        if diff[index] in diff[index + 1]:
            diff.remove(diff[index])
            maxlen -= 1
        else:
            index += 1
    diff = set(diff)
    diff.difference_update(difference)
    return diff


def text_diff(d1, d2, difference=None, sign=None):
    difference = difference or set()
    diffs = difflib.ndiff(d1.split(), d2.split())
    diffs = set(filter(lambda x: x.startswith("+"), diffs))
    diffs.difference_update(difference)
    return diffs


def diff_to_text(mime, diff, dom):
    if not diff:
        return ""
    if isinstance(mime, bool):
        if isinstance(diff, lxml.etree._Element):
            return tostring(diff)
        elif isinstance(diff, (list, dict)):
            return json.dumps(diff).encode()
        else:
            return diff
    else:
        if mime == 2:
            return " ".join(map(lambda x: x.strip("- "), diff)).encode()
        elif mime == 3:
            return "\n".join(
                sum([dom.xpath(f"{i}//text()") for i in diff], [])
            ).encode()
        elif mime == 1:
            content = ""
            for path in diff:
                path_expr = jsonpath_rw.parse(path)
                content += "".join(str(i.value) for i in path_expr.find(dom)) + "\n"
            return content.encode()


def content_type(r: requests.Response):
    contenttype = r.headers.get("content-type", "").split(";")[0].strip()
    mime = MIME.from_buffer(r.content)
    if mime != contenttype and mime.split("/")[0] == "text":
        mime == contenttype
    if "json" in mime:
        if JsonRegex.match(r.content):
            return r.json()
        dom = JsonpRegex.match(r.content)
        if dom:

            dom = dom.groupdict().get("json")
            return json.loads(dom)
    elif "html" in mime:
        obj = lxml.etree.HTML(r.content) or r.content
        return obj
    elif "xml" in mime:
        obj = lxml.etree.XML(r.content)
        return obj
    elif mime.startswith("text"):
        if JsonRegex.match(r.content):
            return r.json()
        dom = JsonpRegex.match(r.content)
        if dom:
            dom = dom.groupdict().get("json")
            return json.loads(dom)
        obj = lxml.etree.HTML(r.content) or r.content
        return obj
    else:
        return UNVISIBLE.sub("", r.content).decode()
    return r.text


def tdiff(dom, dom_a=None, sign=None, ad=None):
    if type(dom_a) != type(dom):
        return True, dom
    try:
        if isinstance(dom_a, (list, dict)):
            return 1, json_diff(dom_a, dom, ad)
        elif isinstance(dom_a, str):
            return 2, text_diff(dom_a, dom, ad)
        else:
            return 3, xml_diff(dom_a, dom, ad)
    except Exception as e:
        return False, False


def request_diff(r1, r2, sign=None, ad=None):
    c1, c2 = content_type(r1), content_type(r2)
    mime, diff = tdiff(c1, c2, sign, ad)
    return diff_to_text(mime, diff, c1)
