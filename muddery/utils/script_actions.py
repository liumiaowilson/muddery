"""
Default action scripts are in this model.
Action script functions must be compatible with this:

def func(character, obj, *args)
    args:
        character(object): a player character.
        obj(object): the player character's action target.
        args: other args.

"""

from muddery.utils import utils


def example(caller, obj, *args):
    """
    This is an example.
    """
    return


def learn_skill(character, obj, *args):
    """
    Teach the character a skill.
    args: skill's key
    """
    if not character:
        return

    if not args:
        return

    character.skill.learn_skill(args[0])


def give_objects(character, obj, *args):
    """
    Give some objects to the character.
    args: object's key and object's number
    """
    if not character:
        return

    if not args:
        return

    obj_key = args[0]
    number = 1
    if len(args) > 1:
        number = args[1]

    obj_list = [{"object": obj_key,
                 "number": number}]

    character.receive_objects(obj_list)


def remove_objects(character, obj, *args):
    """
    Remove some objects from the character.
    args: object's key and object's number
    """
    if not character:
        return

    if not args:
        return

    obj_key = args[0]
    number = 1
    if len(args) > 1:
        number = args[1]

    obj_list = [{"object": obj_key,
                 "number": number}]

    character.remove_objects(obj_list)


def teleport_to(character, obj, *args):
    """
    Teleport the character to specified room.
    args: target room's key
    """
    if not character:
        return

    if not args:
        return

    destination = utils.search_obj_info_key(args[0])
    if not destination:
        return
    destination = destination[0]

    character.move_to(destination)