from .toolz import Toolz

__red_end_user_data_statement__ = (
    "This cog stores per-guild role message settings, including role IDs, channel IDs, "
    "and configured message templates. Role member exports are generated on demand and "
    "sent directly to Discord without being saved locally."
)


async def setup(bot):
    await bot.add_cog(Toolz(bot))
