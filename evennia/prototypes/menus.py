"""

OLC Prototype menu nodes

"""

import json
from django.conf import settings
from evennia.utils.evmenu import EvMenu, list_node
from evennia.utils.ansi import strip_ansi
from evennia.utils import utils
from evennia.prototypes import prototypes as protlib
from evennia.prototypes import spawner

# ------------------------------------------------------------
#
# OLC Prototype design menu
#
# ------------------------------------------------------------

_MENU_CROP_WIDTH = 15
_MENU_ATTR_LITERAL_EVAL_ERROR = (
    "|rCritical Python syntax error in your value. Only primitive Python structures are allowed.\n"
    "You also need to use correct Python syntax. Remember especially to put quotes around all "
    "strings inside lists and dicts.|n")


# Helper functions


def _get_menu_prototype(caller):
    """Return currently active menu prototype."""
    prototype = None
    if hasattr(caller.ndb._menutree, "olc_prototype"):
        prototype = caller.ndb._menutree.olc_prototype
    if not prototype:
        caller.ndb._menutree.olc_prototype = prototype = {}
        caller.ndb._menutree.olc_new = True
    return prototype


def _set_menu_prototype(caller, prototype):
    """Set the prototype with existing one"""
    caller.ndb._menutree.olc_prototype = prototype
    caller.ndb._menutree.olc_new = False
    return prototype


def _is_new_prototype(caller):
    """Check if prototype is marked as new or was loaded from a saved one."""
    return hasattr(caller.ndb._menutree, "olc_new")


def _format_option_value(prop, required=False, prototype=None, cropper=None):
    """
    Format wizard option values.

    Args:
        prop (str): Name or value to format.
        required (bool, optional): The option is required.
        prototype (dict, optional): If given, `prop` will be considered a key in this prototype.
        cropper (callable, optional): A function to crop the value to a certain width.

    Returns:
        value (str): The formatted value.
    """
    if prototype is not None:
        prop = prototype.get(prop, '')

    out = prop
    if callable(prop):
        if hasattr(prop, '__name__'):
            out = "<{}>".format(prop.__name__)
        else:
            out = repr(prop)
    if utils.is_iter(prop):
        out = ", ".join(str(pr) for pr in prop)
    if not out and required:
        out = "|rrequired"
    return " ({}|n)".format(cropper(out) if cropper else utils.crop(out, _MENU_CROP_WIDTH))


def _set_prototype_value(caller, field, value, parse=True):
    """Set prototype's field in a safe way."""
    prototype = _get_menu_prototype(caller)
    prototype[field] = value
    caller.ndb._menutree.olc_prototype = prototype
    return prototype


def _set_property(caller, raw_string, **kwargs):
    """
    Add or update a property. To be called by the 'goto' option variable.

    Args:
        caller (Object, Account): The user of the wizard.
        raw_string (str): Input from user on given node - the new value to set.

    Kwargs:
        test_parse (bool): If set (default True), parse raw_string for protfuncs and obj-refs and
            try to run result through literal_eval. The parser will be run in 'testing' mode and any
            parsing errors will shown to the user. Note that this is just for testing, the original
            given string will be what is inserted.
        prop (str): Property name to edit with `raw_string`.
        processor (callable): Converts `raw_string` to a form suitable for saving.
        next_node (str): Where to redirect to after this has run.

    Returns:
        next_node (str): Next node to go to.

    """
    prop = kwargs.get("prop", "prototype_key")
    processor = kwargs.get("processor", None)
    next_node = kwargs.get("next_node", "node_index")

    propname_low = prop.strip().lower()

    if callable(processor):
        try:
            value = processor(raw_string)
        except Exception as err:
            caller.msg("Could not set {prop} to {value} ({err})".format(
                       prop=prop.replace("_", "-").capitalize(), value=raw_string, err=str(err)))
            # this means we'll re-run the current node.
            return None
    else:
        value = raw_string

    if not value:
        return next_node

    prototype = _set_prototype_value(caller, prop, value)

    # typeclass and prototype_parent can't co-exist
    if propname_low == "typeclass":
        prototype.pop("prototype_parent", None)
    if propname_low == "prototype_parent":
        prototype.pop("typeclass", None)

    caller.ndb._menutree.olc_prototype = prototype

    try:
        # TODO simple way to get rid of the u'' markers in list reprs, remove this when on py3.
        repr_value = json.dumps(value)
    except Exception:
        repr_value = value

    out = [" Set {prop} to {value} ({typ}).".format(prop=prop, value=repr_value, typ=type(value))]

    if kwargs.get("test_parse", True):
        out.append(" Simulating prototype-func parsing ...")
        err, parsed_value = protlib.protfunc_parser(value, testing=True)
        if err:
            out.append(" |yPython `literal_eval` warning: {}|n".format(err))
        if parsed_value != value:
            out.append(" |g(Example-)value when parsed ({}):|n {}".format(
                type(parsed_value), parsed_value))
        else:
            out.append(" |gNo change when parsed.")

    caller.msg("\n".join(out))

    return next_node


def _wizard_options(curr_node, prev_node, next_node, color="|W"):
    """Creates default navigation options available in the wizard."""
    options = []
    if prev_node:
        options.append({"key": ("|wb|Wack", "b"),
                        "desc": "{color}({node})|n".format(
                            color=color, node=prev_node.replace("_", "-")),
                        "goto": "node_{}".format(prev_node)})
    if next_node:
        options.append({"key": ("|wf|Worward", "f"),
                        "desc": "{color}({node})|n".format(
                            color=color, node=next_node.replace("_", "-")),
                        "goto": "node_{}".format(next_node)})

    if "index" not in (prev_node, next_node):
        options.append({"key": ("|wi|Wndex", "i"),
                        "goto": "node_index"})

    if curr_node:
        options.append({"key": ("|wv|Walidate prototype", "v"),
                        "goto": ("node_view_prototype", {"back": curr_node})})

    return options


def _path_cropper(pythonpath):
    "Crop path to only the last component"
    return pythonpath.split('.')[-1]


def _validate_prototype(prototype):
    """Run validation on prototype"""

    txt = protlib.prototype_to_str(prototype)
    errors = "\n\n|g No validation errors found.|n (but errors could still happen at spawn-time)"
    err = False
    try:
        # validate, don't spawn
        spawner.spawn(prototype, only_validate=True)
    except RuntimeError as err:
        errors = "\n\n|r{}|n".format(err)
        err = True
    except RuntimeWarning as err:
        errors = "\n\n|y{}|n".format(err)
        err = True

    text = (txt + errors)
    return err, text


# Menu nodes

def node_index(caller):
    prototype = _get_menu_prototype(caller)

    text = (
       "|c --- Prototype wizard --- |n\n\n"
       "Define the |yproperties|n of the prototype. All prototype values can be "
       "over-ridden at the time of spawning an instance of the prototype, but some are "
       "required.\n\n'|wprototype-'-properties|n are not used in the prototype itself but are used "
       "to organize and list prototypes. The 'prototype-key' uniquely identifies the prototype "
       "and allows you to edit an existing prototype or save a new one for use by you or "
       "others later.\n\n(make choice; q to abort. If unsure, start from 1.)")

    options = []
    options.append(
        {"desc": "|WPrototype-Key|n|n{}".format(_format_option_value("Key", True, prototype, None)),
         "goto": "node_prototype_key"})
    for key in ('Typeclass', 'Prototype-parent', 'Key', 'Aliases', 'Attrs', 'Tags', 'Locks',
                'Permissions', 'Location', 'Home', 'Destination'):
        required = False
        cropper = None
        if key in ("Prototype-parent", "Typeclass"):
            required = "prototype" not in prototype and "typeclass" not in prototype
        if key == 'Typeclass':
            cropper = _path_cropper
        options.append(
            {"desc": "|w{}|n{}".format(
                key, _format_option_value(key, required, prototype, cropper=cropper)),
             "goto": "node_{}".format(key.lower())})
    required = False
    for key in ('Desc', 'Tags', 'Locks'):
        options.append(
            {"desc": "|WPrototype-{}|n|n{}".format(
                key, _format_option_value(key, required, prototype, None)),
             "goto": "node_prototype_{}".format(key.lower())})
    for key in ("Save", "Spawn", "Load"):
        options.append(
            {"key": ("|w{}|W{}".format(key[0], key[1:]), key[0]),
             "desc": "|W{}|n".format(
                key, _format_option_value(key, required, prototype, None)),
             "goto": "node_prototype_{}".format(key.lower())})

    return text, options


def node_view_prototype(caller, raw_string, **kwargs):
    """General node to view and validate a protototype"""
    prototype = kwargs.get('prototype', _get_menu_prototype(caller))
    validate = kwargs.get("validate", True)
    prev_node = kwargs.get("back", "node_index")

    if validate:
        _, text = _validate_prototype(prototype)
    else:
        text = protlib.prototype_to_str(prototype)

    options = _wizard_options(None, prev_node, None)

    return text, options


def _check_prototype_key(caller, key):
    old_prototype = protlib.search_prototype(key)
    olc_new = _is_new_prototype(caller)
    key = key.strip().lower()
    if old_prototype:
        old_prototype = old_prototype[0]
        # we are starting a new prototype that matches an existing
        if not caller.locks.check_lockstring(
                caller, old_prototype['prototype_locks'], access_type='edit'):
            # return to the node_prototype_key to try another key
            caller.msg("Prototype '{key}' already exists and you don't "
                       "have permission to edit it.".format(key=key))
            return "node_prototype_key"
        elif olc_new:
            # we are selecting an existing prototype to edit. Reset to index.
            del caller.ndb._menutree.olc_new
            caller.ndb._menutree.olc_prototype = old_prototype
            caller.msg("Prototype already exists. Reloading.")
            return "node_index"

    return _set_property(caller, key, prop='prototype_key', next_node="node_prototype_parent")


def node_prototype_key(caller):
    prototype = _get_menu_prototype(caller)
    text = ["The prototype name, or |wMeta-Key|n, uniquely identifies the prototype. "
            "It is used to find and use the prototype to spawn new entities. "
            "It is not case sensitive."]
    old_key = prototype.get('prototype_key', None)
    if old_key:
        text.append("Current key is '|w{key}|n'".format(key=old_key))
    else:
        text.append("The key is currently unset.")
    text.append("Enter text or make a choice (q for quit)")
    text = "\n\n".join(text)
    options = _wizard_options("prototype_key", "index", "prototype")
    options.append({"key": "_default",
                    "goto": _check_prototype_key})
    return text, options


def _all_prototype_parents(caller):
    """Return prototype_key of all available prototypes for listing in menu"""
    return [prototype["prototype_key"]
            for prototype in protlib.search_prototype() if "prototype_key" in prototype]


def _prototype_parent_examine(caller, prototype_name):
    """Convert prototype to a string representation for closer inspection"""
    prototypes = protlib.search_prototype(key=prototype_name)
    if prototypes:
        ret = protlib.prototype_to_str(prototypes[0])
        caller.msg(ret)
        return ret
    else:
        caller.msg("Prototype not registered.")


def _prototype_parent_select(caller, prototype):
    ret = _set_property(caller, prototype['prototype_key'],
                        prop="prototype_parent", processor=str, next_node="node_key")
    caller.msg("Selected prototype |y{}|n. Removed any set typeclass parent.".format(prototype))
    return ret


@list_node(_all_prototype_parents, _prototype_parent_select)
def node_prototype_parent(caller):
    prototype = _get_menu_prototype(caller)

    prot_parent_key = prototype.get('prototype')

    text = ["Set the prototype's |yParent Prototype|n. If this is unset, Typeclass will be used."]
    if prot_parent_key:
        prot_parent = protlib.search_prototype(prot_parent_key)
        if prot_parent:
            text.append(
                "Current parent prototype is {}:\n{}".format(protlib.prototype_to_str(prot_parent)))
        else:
            text.append("Current parent prototype |r{prototype}|n "
                        "does not appear to exist.".format(prot_parent_key))
    else:
        text.append("Parent prototype is not set")
    text = "\n\n".join(text)
    options = _wizard_options("prototype", "prototype_key", "typeclass", color="|W")
    options.append({"key": "_default",
                    "goto": _prototype_parent_examine})

    return text, options


def _all_typeclasses(caller):
    """Get name of available typeclasses."""
    return list(name for name in
                sorted(utils.get_all_typeclasses("evennia.objects.models.ObjectDB").keys())
                if name != "evennia.objects.models.ObjectDB")


def _typeclass_examine(caller, typeclass_path):
    """Show info (docstring) about given typeclass."""
    if typeclass_path is None:
        # this means we are exiting the listing
        return "node_key"

    typeclass = utils.get_all_typeclasses().get(typeclass_path)
    if typeclass:
        docstr = []
        for line in typeclass.__doc__.split("\n"):
            if line.strip():
                docstr.append(line)
            elif docstr:
                break
        docstr = '\n'.join(docstr) if docstr else "<empty>"
        txt = "Typeclass |y{typeclass_path}|n; First paragraph of docstring:\n\n{docstring}".format(
                typeclass_path=typeclass_path, docstring=docstr)
    else:
        txt = "This is typeclass |y{}|n.".format(typeclass)
    caller.msg(txt)
    return txt


def _typeclass_select(caller, typeclass):
    """Select typeclass from list and add it to prototype. Return next node to go to."""
    ret = _set_property(caller, typeclass, prop='typeclass', processor=str, next_node="node_key")
    caller.msg("Selected typeclass |y{}|n. Removed any set prototype parent.".format(typeclass))
    return ret


@list_node(_all_typeclasses, _typeclass_select)
def node_typeclass(caller):
    prototype = _get_menu_prototype(caller)
    typeclass = prototype.get("typeclass")

    text = ["Set the typeclass's parent |yTypeclass|n."]
    if typeclass:
        text.append("Current typeclass is |y{typeclass}|n.".format(typeclass=typeclass))
    else:
        text.append("Using default typeclass {typeclass}.".format(
            typeclass=settings.BASE_OBJECT_TYPECLASS))
    text = "\n\n".join(text)
    options = _wizard_options("typeclass", "prototype", "key", color="|W")
    options.append({"key": "_default",
                    "goto": _typeclass_examine})
    return text, options


def node_key(caller):
    prototype = _get_menu_prototype(caller)
    key = prototype.get("key")

    text = ["Set the prototype's name (|yKey|n.) This will retain case sensitivity."]
    if key:
        text.append("Current key value is '|y{key}|n'.".format(key=key))
    else:
        text.append("Key is currently unset.")
    text = "\n\n".join(text)
    options = _wizard_options("key", "typeclass", "aliases")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="key",
                                  processor=lambda s: s.strip(),
                                  next_node="node_aliases"))})
    return text, options


def node_aliases(caller):
    prototype = _get_menu_prototype(caller)
    aliases = prototype.get("aliases")

    text = ["Set the prototype's |yAliases|n. Separate multiple aliases with commas. "
            "they'll retain case sensitivity."]
    if aliases:
        text.append("Current aliases are '|y{aliases}|n'.".format(aliases=aliases))
    else:
        text.append("No aliases are set.")
    text = "\n\n".join(text)
    options = _wizard_options("aliases", "key", "attrs")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="aliases",
                                  processor=lambda s: [part.strip() for part in s.split(",")],
                                  next_node="node_attrs"))})
    return text, options


def _caller_attrs(caller):
    prototype = _get_menu_prototype(caller)
    attrs = prototype.get("attrs", [])
    return attrs


def _display_attribute(attr_tuple):
    """Pretty-print attribute tuple"""
    attrkey, value, category, locks, default_access = attr_tuple
    value = protlib.protfunc_parser(value)
    typ = type(value)
    out = ("Attribute key: '{attrkey}' (category: {category}, "
           "locks: {locks})\n"
           "Value (parsed to {typ}): {value}").format(
                   attrkey=attrkey,
                   category=category, locks=locks,
                   typ=typ, value=value)
    return out


def _add_attr(caller, attr_string, **kwargs):
    """
    Add new attrubute, parsing input.
    attr is entered on these forms
        attr = value
        attr;category = value
        attr;category;lockstring = value

    """
    attrname = ''
    category = None
    locks = ''

    if '=' in attr_string:
        attrname, value = (part.strip() for part in attr_string.split('=', 1))
        attrname = attrname.lower()
        nameparts = attrname.split(";", 2)
        nparts = len(nameparts)
        if nparts == 2:
            attrname, category = nameparts
        elif nparts > 2:
            attrname, category, locks = nameparts
    attr_tuple = (attrname, category, locks)

    if attrname:
        prot = _get_menu_prototype(caller)
        attrs = prot.get('attrs', [])

        try:
            # replace existing attribute with the same name in the prototype
            ind = [tup[0] for tup in attrs].index(attrname)
            attrs[ind] = attr_tuple
        except IndexError:
            attrs.append(attr_tuple)

        _set_prototype_value(caller, "attrs", attrs)

        text = kwargs.get('text')
        if not text:
            if 'edit' in kwargs:
                text = "Edited " + _display_attribute(attr_tuple)
            else:
                text = "Added " + _display_attribute(attr_tuple)
    else:
        text = "Attribute must be given as 'attrname[;category;locks] = <value>'."

    options = {"key": "_default",
               "goto": lambda caller: None}
    return text, options


def _edit_attr(caller, attrname, new_value, **kwargs):

    attr_string = "{}={}".format(attrname, new_value)

    return _add_attr(caller, attr_string, edit=True)


def _examine_attr(caller, selection):
    prot = _get_menu_prototype(caller)
    attr_tuple = prot['attrs'][selection]
    return _display_attribute(attr_tuple)


@list_node(_caller_attrs)
def node_attrs(caller):
    prot = _get_menu_prototype(caller)
    attrs = prot.get("attrs")

    text = ["Set the prototype's |yAttributes|n. Enter attributes on one of these forms:\n"
            " attrname=value\n attrname;category=value\n attrname;category;lockstring=value\n"
            "To give an attribute without a category but with a lockstring, leave that spot empty "
            "(attrname;;lockstring=value)."
            "Separate multiple attrs with commas. Use quotes to escape inputs with commas and "
            "semi-colon."]
    if attrs:
        text.append("Current attrs are '|y{attrs}|n'.".format(attrs=attrs))
    else:
        text.append("No attrs are set.")
    text = "\n\n".join(text)
    options = _wizard_options("attrs", "aliases", "tags")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="attrs",
                                  processor=lambda s: [part.strip() for part in s.split(",")],
                                  next_node="node_tags"))})
    return text, options


def _caller_tags(caller):
    prototype = _get_menu_prototype(caller)
    tags = prototype.get("tags")
    return tags


def _display_tag(tag_tuple):
    """Pretty-print attribute tuple"""
    tagkey, category, data = tag_tuple
    out = ("Tag: '{tagkey}' (category: {category}{})".format(
           tagkey=tagkey, category=category, data=", data: {}".format(data) if data else ""))
    return out


def _add_tag(caller, tag, **kwargs):
    """
    Add tags to the system, parsing  this syntax:
        tagname
        tagname;category
        tagname;category;data

    """

    tag = tag.strip().lower()
    category = None
    data = ""

    tagtuple = tag.split(";", 2)
    ntuple = len(tagtuple)

    if ntuple == 2:
        tag, category = tagtuple
    elif ntuple > 2:
        tag, category, data = tagtuple

    tag_tuple = (tag, category, data)

    if tag:
        prot = _get_menu_prototype(caller)
        tags = prot.get('tags', [])

        old_tag = kwargs.get("edit", None)

        if old_tag:
            # editing a tag means removing the old and replacing with new
            try:
                ind = [tup[0] for tup in tags].index(old_tag)
                del tags[ind]
            except IndexError:
                pass

        tags.append(tag_tuple)

        _set_prototype_value(caller, "tags", tags)

        text = kwargs.get('text')
        if not text:
            if 'edit' in kwargs:
                text = "Edited " + _display_tag(tag_tuple)
            else:
                text = "Added " + _display_tag(tag_tuple)
    else:
        text = "Tag must be given as 'tag[;category;data]."

    options = {"key": "_default",
               "goto": lambda caller: None}
    return text, options


def _edit_tag(caller, old_tag, new_tag, **kwargs):
    return _add_tag(caller, new_tag, edit=old_tag)


@list_node(_caller_tags)
def node_tags(caller):
    text = ("Set the prototype's |yTags|n. Enter tags on one of the following forms:\n"
            " tag\n tag;category\n tag;category;data\n"
            "Note that 'data' is not commonly used.")
    options = _wizard_options("tags", "attrs", "locks")
    return text, options


def node_locks(caller):
    prototype = _get_menu_prototype(caller)
    locks = prototype.get("locks")

    text = ["Set the prototype's |yLock string|n. Separate multiple locks with semi-colons. "
            "Will retain case sensitivity."]
    if locks:
        text.append("Current locks are '|y{locks}|n'.".format(locks=locks))
    else:
        text.append("No locks are set.")
    text = "\n\n".join(text)
    options = _wizard_options("locks", "tags", "permissions")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="locks",
                                  processor=lambda s: s.strip(),
                                  next_node="node_permissions"))})
    return text, options


def node_permissions(caller):
    prototype = _get_menu_prototype(caller)
    permissions = prototype.get("permissions")

    text = ["Set the prototype's |yPermissions|n. Separate multiple permissions with commas. "
            "Will retain case sensitivity."]
    if permissions:
        text.append("Current permissions are '|y{permissions}|n'.".format(permissions=permissions))
    else:
        text.append("No permissions are set.")
    text = "\n\n".join(text)
    options = _wizard_options("permissions", "destination", "location")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="permissions",
                                  processor=lambda s: [part.strip() for part in s.split(",")],
                                  next_node="node_location"))})
    return text, options


def node_location(caller):
    prototype = _get_menu_prototype(caller)
    location = prototype.get("location")

    text = ["Set the prototype's |yLocation|n"]
    if location:
        text.append("Current location is |y{location}|n.".format(location=location))
    else:
        text.append("Default location is {}'s inventory.".format(caller))
    text = "\n\n".join(text)
    options = _wizard_options("location", "permissions", "home")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="location",
                                  processor=lambda s: s.strip(),
                                  next_node="node_home"))})
    return text, options


def node_home(caller):
    prototype = _get_menu_prototype(caller)
    home = prototype.get("home")

    text = ["Set the prototype's |yHome location|n"]
    if home:
        text.append("Current home location is |y{home}|n.".format(home=home))
    else:
        text.append("Default home location (|y{home}|n) used.".format(home=settings.DEFAULT_HOME))
    text = "\n\n".join(text)
    options = _wizard_options("home", "aliases", "destination")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="home",
                                  processor=lambda s: s.strip(),
                                  next_node="node_destination"))})
    return text, options


def node_destination(caller):
    prototype = _get_menu_prototype(caller)
    dest = prototype.get("dest")

    text = ["Set the prototype's |yDestination|n. This is usually only used for Exits."]
    if dest:
        text.append("Current destination is |y{dest}|n.".format(dest=dest))
    else:
        text.append("No destination is set (default).")
    text = "\n\n".join(text)
    options = _wizard_options("destination", "home", "prototype_desc")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="dest",
                                  processor=lambda s: s.strip(),
                                  next_node="node_prototype_desc"))})
    return text, options


def node_prototype_desc(caller):

    prototype = _get_menu_prototype(caller)
    text = ["The |wPrototype-Description|n briefly describes the prototype for "
            "viewing in listings."]
    desc = prototype.get("prototype_desc", None)

    if desc:
        text.append("The current meta desc is:\n\"|w{desc}|n\"".format(desc=desc))
    else:
        text.append("Description is currently unset.")
    text = "\n\n".join(text)
    options = _wizard_options("prototype_desc", "prototype_key", "prototype_tags")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop='prototype_desc',
                                  processor=lambda s: s.strip(),
                                  next_node="node_prototype_tags"))})

    return text, options


def node_prototype_tags(caller):
    prototype = _get_menu_prototype(caller)
    text = ["|wPrototype-Tags|n can be used to classify and find prototypes. "
            "Tags are case-insensitive. "
            "Separate multiple by tags by commas."]
    tags = prototype.get('prototype_tags', [])

    if tags:
        text.append("The current tags are:\n|w{tags}|n".format(tags=tags))
    else:
        text.append("No tags are currently set.")
    text = "\n\n".join(text)
    options = _wizard_options("prototype_tags", "prototype_desc", "prototype_locks")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="prototype_tags",
                                  processor=lambda s: [
                                    str(part.strip().lower()) for part in s.split(",")],
                                  next_node="node_prototype_locks"))})
    return text, options


def node_prototype_locks(caller):
    prototype = _get_menu_prototype(caller)
    text = ["Set |wPrototype-Locks|n on the prototype. There are two valid lock types: "
            "'edit' (who can edit the prototype) and 'spawn' (who can spawn new objects with this "
            "prototype)\n(If you are unsure, leave as default.)"]
    locks = prototype.get('prototype_locks', '')
    if locks:
        text.append("Current lock is |w'{lockstring}'|n".format(lockstring=locks))
    else:
        text.append("Lock unset - if not changed the default lockstring will be set as\n"
                    "   |w'spawn:all(); edit:id({dbref}) or perm(Admin)'|n".format(dbref=caller.id))
    text = "\n\n".join(text)
    options = _wizard_options("prototype_locks", "prototype_tags", "index")
    options.append({"key": "_default",
                    "goto": (_set_property,
                             dict(prop="prototype_locks",
                                  processor=lambda s: s.strip().lower(),
                                  next_node="node_index"))})
    return text, options


def node_prototype_save(caller, **kwargs):
    """Save prototype to disk """
    # these are only set if we selected 'yes' to save on a previous pass
    accept_save = kwargs.get("accept", False)
    prototype = kwargs.get("prototype", None)

    if accept_save and prototype:
        # we already validated and accepted the save, so this node acts as a goto callback and
        # should now only return the next node
        protlib.save_prototype(**prototype)
        caller.msg("|gPrototype saved.|n")
        return "node_spawn"

    # not validated yet
    prototype = _get_menu_prototype(caller)
    error, text = _validate_prototype(prototype)

    text = [text]

    if error:
        # abort save
        text.append(
            "Validation errors were found. They need to be corrected before this prototype "
            "can be saved (or used to spawn).")
        options = _wizard_options("prototype_save", "prototype_locks", "index")
        return "\n".join(text),  options

    prototype_key = prototype['prototype_key']
    if protlib.search_prototype(prototype_key):
        text.append("Do you want to save/overwrite the existing prototype '{name}'?".format(
            name=prototype_key))
    else:
        text.append("Do you want to save the prototype as '{name}'?".format(prototype_key))

    options = (
        {"key": ("[|wY|Wes|n]", "yes", "y"),
         "goto": lambda caller:
            node_prototype_save(caller,
                                {"accept": True, "prototype": prototype})},
        {"key": ("|wN|Wo|n", "n"),
         "goto": "node_spawn"},
        {"key": "_default",
         "goto": lambda caller:
            node_prototype_save(caller,
                                {"accept": True, "prototype": prototype})})

    return "\n".join(text),  options


def _spawn(caller, **kwargs):
    """Spawn prototype"""
    prototype = kwargs["prototype"].copy()
    new_location = kwargs.get('location', None)
    if new_location:
        prototype['location'] = new_location
    obj = spawner.spawn(prototype)
    if obj:
        caller.msg("|gNew instance|n {key} ({dbref}) |gspawned.|n".format(
            key=obj.key, dbref=obj.dbref))
    else:
        caller.msg("|rError: Spawner did not return a new instance.|n")


def _update_spawned(caller, **kwargs):
    """update existing objects"""
    prototype = kwargs['prototype']
    objects = kwargs['objects']
    num_changed = spawner.batch_update_objects_with_prototype(prototype, objects=objects)
    caller.msg("|g{num} objects were updated successfully.|n".format(num=num_changed))


def node_prototype_spawn(caller, **kwargs):
    """Submenu for spawning the prototype"""

    prototype = _get_menu_prototype(caller)
    error, text = _validate_prototype(prototype)

    text = [text]

    if error:
        text.append("|rPrototype validation failed. Correct the errors before spawning.|n")
        options = _wizard_options("prototype_spawn", "prototype_locks", "index")
        return "\n".join(text), options

    # show spawn submenu options
    options = []
    prototype_key = prototype['prototype_key']
    location = prototype.get('location', None)

    if location:
        options.append(
            {"desc": "Spawn in prototype's defined location ({loc})".format(loc=location),
             "goto": (_spawn,
                      dict(prototype=prototype))})
    caller_loc = caller.location
    if location != caller_loc:
        options.append(
            {"desc": "Spawn in {caller}'s location ({loc})".format(
                caller=caller, loc=caller_loc),
             "goto": (_spawn,
                      dict(prototype=prototype, location=caller_loc))})
    if location != caller_loc != caller:
        options.append(
            {"desc": "Spawn in {caller}'s inventory".format(caller=caller),
             "goto": (_spawn,
                      dict(prototype=prototype, location=caller))})

    spawned_objects = protlib.search_objects_with_prototype(prototype_key)
    nspawned = spawned_objects.count()
    if spawned_objects:
        options.append(
            {"desc": "Update {num} existing objects with this prototype".format(num=nspawned),
             "goto": (_update_spawned,
                      dict(prototype=prototype,
                           opjects=spawned_objects))})
    options.extend(_wizard_options("prototype_spawn", "prototype_save", "index"))
    return text, options


def _prototype_load_select(caller, prototype_key):
    matches = protlib.search_prototype(key=prototype_key)
    if matches:
        prototype = matches[0]
        _set_menu_prototype(caller, prototype)
        caller.msg("|gLoaded prototype '{}'.".format(prototype_key))
        return "node_index"
    else:
        caller.msg("|rFailed to load prototype '{}'.".format(prototype_key))
        return None


@list_node(_all_prototype_parents, _prototype_load_select)
def node_prototype_load(caller, **kwargs):
    text = ["Select a prototype to load. This will replace any currently edited prototype."]
    options = _wizard_options("load", "save", "index")
    options.append({"key": "_default",
                    "goto": _prototype_parent_examine})
    return "\n".join(text), options


class OLCMenu(EvMenu):
    """
    A custom EvMenu with a different formatting for the options.

    """
    def options_formatter(self, optionlist):
        """
        Split the options into two blocks - olc options and normal options

        """
        olc_keys = ("index", "forward", "back", "previous", "next", "validate prototype")
        olc_options = []
        other_options = []
        for key, desc in optionlist:
            raw_key = strip_ansi(key)
            if raw_key in olc_keys:
                desc = " {}".format(desc) if desc else ""
                olc_options.append("|lc{}|lt{}|le{}".format(raw_key, key, desc))
            else:
                other_options.append((key, desc))

        olc_options = " | ".join(olc_options) + " | " + "|wq|Wuit" if olc_options else ""
        other_options = super(OLCMenu, self).options_formatter(other_options)
        sep = "\n\n" if olc_options and other_options else ""

        return "{}{}{}".format(olc_options, sep, other_options)


def start_olc(caller, session=None, prototype=None):
    """
    Start menu-driven olc system for prototypes.

    Args:
        caller (Object or Account): The entity starting the menu.
        session (Session, optional): The individual session to get data.
        prototype (dict, optional): Given when editing an existing
            prototype rather than creating a new one.

    """
    menudata = {"node_index": node_index,
                "node_view_prototype": node_view_prototype,
                "node_prototype_key": node_prototype_key,
                "node_prototype_parent": node_prototype_parent,
                "node_typeclass": node_typeclass,
                "node_key": node_key,
                "node_aliases": node_aliases,
                "node_attrs": node_attrs,
                "node_tags": node_tags,
                "node_locks": node_locks,
                "node_permissions": node_permissions,
                "node_location": node_location,
                "node_home": node_home,
                "node_destination": node_destination,
                "node_prototype_desc": node_prototype_desc,
                "node_prototype_tags": node_prototype_tags,
                "node_prototype_locks": node_prototype_locks,
                "node_prototype_load": node_prototype_load,
                "node_prototype_save": node_prototype_save,
                "node_prototype_spawn": node_prototype_spawn
                }
    OLCMenu(caller, menudata, startnode='node_index', session=session, olc_prototype=prototype)
