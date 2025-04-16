"""
YALC listeners module.
Contains all event listeners for the YALC cog.
"""
from redbot.core import commands
import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .yalc import YALC

# All event listeners are now in the main cog for Redbot compatibility.
# This file is reserved for future modularization if Redbot supports external listener classes.
