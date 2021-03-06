"""
General Character commands usually availabe to all characters

This is adapt from evennia/evennia/commands/default/general.py.
The licence of Evennia can be found in evennia/LICENSE.txt.
"""

from django.conf import settings
from evennia.utils import utils, prettytable, logger
from evennia.commands.command import Command
from evennia import create_script
from muddery.utils.dialogue_handler import DIALOGUE_HANDLER
from muddery.utils.game_settings import GAME_SETTINGS
from muddery.utils.localized_strings_handler import _
from muddery.utils.exception import MudderyError
import traceback


class CmdLook(Command):
    """
    look at location or object

    Usage:
        {"cmd":"look",
         "args":<object's dbref>
        }

    Observes your location or objects in your vicinity.
    """
    key = "look"
    locks = "cmd:all()"

    def func(self):
        """
        Handle the looking.
        """
        caller = self.caller
        args = self.args

        if not caller.is_alive():
            caller.msg({"alert":_("You are died.")})
            return

        if args:
            # Use search to handle duplicate/nonexistant results.
            looking_at_obj = caller.search(args, location=caller.location)
            if not looking_at_obj:
                caller.msg({"alert":_("Can not find it.")})
                return
        else:
            # Observes the caller's location
            looking_at_obj = caller.location
            if not looking_at_obj:
                caller.msg({"msg":_("You have no location to look at!")})
                return

        if not hasattr(looking_at_obj, 'return_appearance'):
            # this is likely due to us having a player instead
            looking_at_obj = looking_at_obj.character

        if not looking_at_obj.access(caller, "view"):
            # The caller does not have the permission to look.
            caller.msg({"msg":_("Can not find '%s'.") % looking_at_obj.name})
            return

        if looking_at_obj == caller.location:
            # Clear caller's target.
            caller.clear_target()
            caller.show_location()
            
            if caller.is_in_combat():
                # If the caller is in combat, add combat info.
                # This happens when a player is in combat and he logout and login again.

                # Send "joined_combat" message first. It will set the player to combat status.
                caller.msg({"joined_combat": True})
                
                # Send combat infos.
                appearance = caller.ndb.combat_handler.get_appearance()
                message = {"combat_info": appearance,
                           "combat_commands": caller.get_combat_commands()}
                caller.msg(message)
        else:
            # Set caller's target
            caller.set_target(looking_at_obj)

            # Get the object's appearance.
            appearance = looking_at_obj.get_appearance(caller)
            caller.msg({"look_obj": appearance})

        # the object's at_desc() method.
        looking_at_obj.at_desc(looker=caller)


class CmdInventory(Command):
    """
    observe inventory

    Usage:
        {"cmd":"inventory",
         "args":""
        }
      
    Show everything in your inventory.
    """
    key = "inventory"
    locks = "cmd:all()"

    def func(self):
        "check inventory"
        inv = self.caller.return_inventory()
        self.caller.msg({"inventory":inv})


#------------------------------------------------------------
# Say something in the room.
#------------------------------------------------------------
class CmdSay(Command):
    """
    speak as your character

    Usage:
        {"cmd":"say",
         "args":{"channel": <channel's key>,
                 "msg": <message>
        }

    Talk to those in your current location.
    """

    key = "say"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Run the say command"

        caller = self.caller

        if not self.args:
            return

        if not "channel" in self.args:
            caller.msg({"alert":_("You should choose a channel to say.")})
            return

        if not "message" in self.args:
            caller.msg({"alert":_("You should say something.")})
            return

        channel = self.args["channel"]
        message = self.args["message"]
        caller.say(channel, message)


#------------------------------------------------------------
# goto exit
#------------------------------------------------------------

class CmdGoto(Command):
    """
    tranvese an exit

    Usage:
        {"cmd":"goto",
         "args":<exit's dbref>
        }

    Tranvese an exit, go to the destination of the exit.
    """
    key = "goto"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Move caller to the exit."
        caller = self.caller

        if not caller.is_alive():
            caller.msg({"alert":_("You are died.")})
            return

        if not self.args:
            caller.msg({"alert":_("Should appoint an exit to go.")})
            return

        obj = caller.search(self.args, location=caller.location)
        if not obj:
            # Can not find exit.
            caller.msg({"alert":_("Can not find exit.")})
            return
            
        if obj.access(self.caller, 'traverse'):
            # we may traverse the exit.
            # MudderyLockedExit handles locks in at_before_traverse().
            if obj.at_before_traverse(self.caller):
                obj.at_traverse(caller, obj.destination)
        else:
            # exit is locked
            if obj.db.err_traverse:
                # if exit has a better error message, let's use it.
                caller.msg({"alert": self.obj.db.err_traverse})
            else:
                # No shorthand error message. Call hook.
                obj.at_failed_traverse(caller)


#------------------------------------------------------------
# talk to npc
#------------------------------------------------------------

class CmdTalk(Command):
    """
    Talk to an NPC.

    Usage:
        {"cmd":"talk",
         "args":<NPC's dbref>
        }

    Begin a talk with an NPC. Show all available dialogues of this NPC.
    """
    key = "talk"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Talk to an NPC."
        caller = self.caller

        if not self.args:
            caller.msg({"alert":_("You should talk to someone.")})
            return

        npc = caller.search(self.args, location=caller.location)
        if not npc:
            # Can not find the NPC in the caller's location.
            caller.msg({"alert":_("Can not find the one to talk.")})
            return

        caller.talk_to_npc(npc)


#------------------------------------------------------------
# talk to npc
#------------------------------------------------------------

class CmdDialogue(Command):
    """
    Continue a dialogue.

    Usage:
        {"cmd":"dialogue",
         "args":{"npc":<npc's dbref>,
                 "dialogue":<current dialogue>,
                 "sentence":<current sentence>}
        }

    Dialogue and sentence refer to the current sentence. This command finishes
    current sentence and get next sentences.
    """
    key = "dialogue"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Continue a dialogue."
        caller = self.caller

        if not self.args:
            caller.msg({"alert":_("You should talk to someone.")})
            return

        npc = None
        if "npc" in self.args:
            if self.args["npc"]:
                # get NPC
                npc = caller.search(self.args["npc"], location=caller.location)
                if not npc:
                    caller.msg({"msg":_("Can not find it.")})
                    return

        # Get the current sentence.
        dialogue = ""
        sentence = 0

        have_current_dlg = False
        try:
            dialogue = self.args["dialogue"]
            sentence = int(self.args["sentence"])
            have_current_dlg = True
        except Exception, e:
            pass

        if not have_current_dlg:
            return

        caller.continue_dialogue(npc, dialogue, sentence)


#------------------------------------------------------------
# loot objects
#------------------------------------------------------------

class CmdLoot(Command):
    """
    Loot from a specified object.

    Usage:
        {"cmd":"loot",
         "args":<object's dbref>
        }

    This command pick out random objects from the loot list and give
    them to the character.
    """
    key = "loot"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Loot objects."
        caller = self.caller

        if not self.args:
            caller.msg({"alert":_("You should loot something.")})
            return

        obj = caller.search(self.args, location=caller.location)
        if not obj:
            # Can not find the specified object.
            caller.msg({"alert":_("Can not find the object to loot.")})
            return

        try:
            # do loot
            obj.loot(caller)
        except Exception, e:
            ostring = "Can not loot %s: %s" % (obj.get_data_key(), e)
            logger.log_tracemsg(ostring)


#------------------------------------------------------------
# use objects
#------------------------------------------------------------

class CmdUse(Command):
    """
    Use an object.

    Usage:
        {"cmd":"use",
         "args":<object's dbref>
        }

    Call caller's use_object function with specified object.
    Different objects can have different results.
    """
    key = "use"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Use an object."
        caller = self.caller

        if not caller.is_alive():
            caller.msg({"alert":_("You are died.")})
            return

        if not self.args:
            caller.msg({"alert":_("You should use something.")})
            return

        obj = caller.search(self.args, location=caller)
        if not obj:
            # If the caller does not have this object.
            caller.msg({"alert":_("You don't have this object.")})
            return

        result = ""
        try:
            # Use the object and get the result.
            result = caller.use_object(obj)
        except Exception, e:
            ostring = "Can not use %s: %s" % (obj.get_data_key(), e)
            logger.log_tracemsg(ostring)

        # Send result to the player.
        if not result:
            result = _("No result.")
        caller.msg({"alert":result})


#------------------------------------------------------------
# discard objects
#------------------------------------------------------------

class CmdDiscard(Command):
    """
    Discard an object.

    Usage:
        {"cmd":"discard",
         "args":<object's dbref>
        }

    Call caller's remove_objects function with specified object.
    """
    key = "discard"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Use an object."
        caller = self.caller

        if not caller.is_alive():
            caller.msg({"alert":_("You are died.")})
            return

        if not self.args:
            caller.msg({"alert":_("You should discard something.")})
            return

        obj = caller.search(self.args, location=caller)
        if not obj:
            # If the caller does not have this object.
            caller.msg({"alert":_("You don't have this object.")})
            return

        # remove used object
        try:
            caller.remove_object(obj.get_data_key(), 1)
        except Exception, e:
            caller.msg({"alert": _("Can not discard this object.")})
            logger.log_tracemsg("Can not discard object %s: %s" % (obj.get_data_key(), e))
            return


#------------------------------------------------------------
# put on equipment
#------------------------------------------------------------

class CmdEquip(Command):
    """
    Put on an equipment.

    Usage:
        {"cmd":"equip",
         "args":<object's dbref>
        }
    Put on an equipment and add its attributes to the character.
    """
    key = "equip"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Put on an equipment."
        caller = self.caller

        if not self.args:
            caller.msg({"alert":_("You should equip something.")})
            return

        obj = caller.search(self.args, location=caller)
        if not obj:
            # If the caller does not have this equipment.
            caller.msg({"alert":_("You don't have this equipment.")})
            return

        try:
            # equip
            caller.equip_object(obj)
        except MudderyError, e:
            caller.msg({"alert": str(e)})
            return
        except Exception, e:
            caller.msg({"alert": _("Can not use this equipment.")})
            logger.log_tracemsg("Can not use equipment %s: %s" % (obj.get_data_key(), e))
            return

        # Send lastest status to the player.
        message = {"alert": _("Equipped!")}
        caller.msg(message)


#------------------------------------------------------------
# take off equipment
#------------------------------------------------------------

class CmdTakeOff(Command):
    """
    Take off an equipment.

    Usage:
        {"cmd":"takeoff",
         "args":<object's dbref>
        }
    Take off an equipment and remove its attributes from the character.
    """
    key = "takeoff"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Take off an equipment."
        caller = self.caller

        if not self.args:
            caller.msg({"alert":_("You should take off something.")})
            return

        obj = caller.search(self.args, location=caller)
        if not obj:
            # If the caller does not have this equipment.
            caller.msg({"alert":_("You don't have this equipment.")})
            return

        try:
            # Take off the equipment.
            caller.take_off_equipment(obj)
        except MudderyError, e:
            caller.msg({"alert": str(e)})
            return
        except Exception, e:
            caller.msg({"alert": _("Can not take off this equipment.")})
            logger.log_tracemsg("Can not take off %s: %s" % (obj.get_data_key(), e))
            return

        # Send lastest status to the player.
        message = {"alert": _("Taken off!")}
        caller.msg(message)


#------------------------------------------------------------
# cast a skill
#------------------------------------------------------------

class CmdCastSkill(Command):
    """
    Cast a skill when the caller is not in combat.

    Usage:
        {"cmd":"castskill",
         "args":<skill's key>}
        }
        
        or:

        {"cmd":"castskill",
         "args":{"skill":<skill's key>,
                 "target":<skill's target>,
                 "combat":<cast in combat>}
        }
    
    """
    key = "castskill"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Cast a skill."
        caller = self.caller
        args = self.args

        if not caller.is_alive():
            caller.msg({"alert":_("You are died.")})
            return

        if not args:
            caller.msg({"alert":_("You should select a skill to cast.")})
            return

        # find skill
        skill_key = None
        target = None

        if isinstance(args, basestring):
            # If the args is a skill's key.
            skill_key = args
        else:
            # If the args is skill's key and target.
            if not "skill" in args:
                caller.msg({"alert":_("You should select a skill to cast.")})
                return
            skill_key = args["skill"]

            # Check combat
            if "combat" in args:
                if args["combat"]:
                    # must be in a combat
                    if not caller.is_in_combat():
                        return
            # Get target
            if "target" in args:
                target = caller.search(args["target"])

        try:
            # Prepare to cast this skill.
            caller.prepare_skill(skill_key, target)
        except Exception, e:
            caller.msg({"alert":_("Can not cast this skill.")})
            logger.log_tracemsg("Can not cast skill %s: %s" % (skill_key, e))
            return


#------------------------------------------------------------
# attack a character
#------------------------------------------------------------
class CmdAttack(Command):
    """
    initiates combat

    Usage:
        {"cmd":"attack",
         "args":<object's dbref>}
        }

    This will initiate a combat with the target. If the target is
    already in combat, the caller will join its combat.
    """
    key = "attack"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        "Handle command"

        caller = self.caller
        if not caller:
            return

        if not caller.is_alive():
            caller.msg({"alert":_("You are died.")})
            return
            
        if not caller.location or caller.location.peaceful:
            caller.msg({"alert":_("You can not attack in this place.")})
            return

        if not self.args:
            caller.msg({"alert":_("You should select a target.")})
            return

        target = caller.search(self.args)
        if not target:
            caller.msg({"alert":_("You should select a target.")})
            return

        if not target.is_alive():
            caller.msg({"alert":_("%s is died." % target.get_name())})
            return

        if caller.location != target.location:
            caller.msg({"alert":_("You can not attack %s." % target.get_name())})
            return

        # Set caller's target.
        caller.set_target(target)

        # set up combat
        if caller.is_in_combat():
            # caller is in battle
            message = {"alert": _("You are in another combat.")}
            caller.msg(message)
            return

        if target.is_in_combat():
            # caller is in battle
            message = {"alert": _("%s is in another combat." % target.name)}
            caller.msg(message)
            return

        # create a new combat handler
        chandler = create_script(settings.COMBAT_HANDLER)
        
        # set combat team and desc
        chandler.set_combat({1: [target], 2:[self.caller]}, "")
        
        self.caller.msg(_("You are attacking {c%s{n! You are in combat.") % target.get_name())
        target.msg(_("{c%s{n is attacking you! You are in combat.") % self.caller.get_name())


#------------------------------------------------------------
# give up a quest
#------------------------------------------------------------

class CmdGiveUpQuest(Command):
    """
    Give up a quest.

    Usage:
        {"cmd":"giveup_quest",
         "args":<quest's key>
        }
    Give up a quest.
    """
    key = "giveup_quest"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        """
        Give up a quest.

        Returns:
            None
        """
        caller = self.caller

        if not self.args:
            caller.msg({"alert":_("You should give up a quest.")})
            return

        quest_key = self.args

        try:
            # Take off the equipment.
            caller.quest_handler.give_up(quest_key)
        except MudderyError, e:
            caller.msg({"alert": str(e)})
            return
        except Exception, e:
            caller.msg({"alert": _("Can not give up this quest.")})
            logger.log_tracemsg("Can not give up quest %s: %s" % (quest_key, e))
            return

        # Send lastest status to the player.
        message = {"alert": _("Given up!")}
        caller.msg(message)


#------------------------------------------------------------
# unlock exit
#------------------------------------------------------------
class CmdUnlockExit(Command):
    """
    Unlock an exit.

    Usage:
        {"cmd":"unlock_exit",
         "args":<object's dbref>
        }
    A character must unlock a LockedExit before tranvese it.
    """
    key = "unlock_exit"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Open a locked exit."
        caller = self.caller

        if not self.args:
            caller.msg({"alert":_("You should unlock something.")})
            return

        obj = caller.search(self.args, location=caller)
        if not obj:
            caller.msg({"alert":_("Can not find this exit.")})
            return

        try:
            # Unlock the exit.
            if not caller.unlock_exit(obj):
                caller.msg({"alert":_("Can not open this exit.") % obj.name})
                return
        except Exception, e:
            caller.msg({"alert": _("Can not open this exit.")})
            logger.log_tracemsg("Can not open exit %s: %s" % (obj.name, e))
            return

        # The exit may have different appearance after unlocking.
        # Send the lastest appearance to the caller.
        appearance = obj.get_appearance(caller)
        caller.msg({"look_obj": appearance})


#------------------------------------------------------------
# open a shop
#------------------------------------------------------------
class CmdShopping(Command):
    """
    Open a shop.

    Usage:
        {"cmd":"shopping",
         "args":<shop's dbref>
        }
    """
    key = "shopping"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Do shopping."
        caller = self.caller

        if not self.args:
            caller.msg({"alert":_("You should shopping in someplace.")})
            return

        shop = caller.search(self.args)
        if not shop:
            caller.msg({"alert":_("Can not find this shop.")})
            return

        shop.show_shop(caller)


#------------------------------------------------------------
# buy a goods
#------------------------------------------------------------
class CmdBuy(Command):
    """
    Buy a goods.

    Usage:
        {"cmd":"buy",
         "args":<goods' dbref>}
        }
    """
    key = "buy"
    locks = "cmd:all()"
    help_cateogory = "General"

    def func(self):
        "Buy a goods."
        caller = self.caller

        if not self.args:
            caller.msg({"alert":_("You should buy something.")})
            return

        goods = caller.search(self.args)
        if not goods:
            caller.msg({"alert":_("Can not find this goods.")})
            return

        # buy goods
        try:
            goods.sell_to(caller)
        except Exception, e:
            caller.msg({"alert":_("Can not buy this goods.")})
            logger.log_err("Can not buy %s: %s" % (goods.get_data_key(), e))
            return


#------------------------------------------------------------
# connect
#------------------------------------------------------------
class CmdConnect(Command):
    """
    Connect to the game when the player has already connectd, 
    ignore it to avoid wrong command messages.

    Usage:
        {"cmd":"connect"}
    """
    key = "connect"
    locks = "cmd:all()"

    def func(self):
        """
        Just ignore it.
        """
        pass


#------------------------------------------------------------
# create
#------------------------------------------------------------
class CmdCreate(Command):
    """
    create an account when the player has already connectd,
    ignore it to avoid wrong command messages.

    Usage:
        {"cmd":"create_account"}
    """
    key = "create_account"
    locks = "cmd:all()"

    def func(self):
        """
        Just ignore it.
        """
        pass



#------------------------------------------------------------
# create and connect
#------------------------------------------------------------
class CmdCreateConnect(Command):
    """
    create an account when the player has already connectd,
    ignore it to avoid wrong command messages.

    Usage:
        {"cmd":"create_connect"}
    """
    key = "create_connect"
    locks = "cmd:all()"

    def func(self):
        """
        Just ignore it.
        """
        pass
