from .rolemanager import RoleManager

__red_end_user_data_statement__ = (
    "This cog stores per-guild role configuration, role-policy settings, role "
    "costs, reaction/button/select component settings, message IDs, channel "
    "IDs, role IDs, emoji keys, temporary-role expiry timestamps, and Discord "
    "user IDs for sticky and temporary role assignment. It does not store "
    "message content except optional component panel text sent directly to "
    "Discord."
)


async def setup(bot):
    await bot.add_cog(RoleManager(bot))
