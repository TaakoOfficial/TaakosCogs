from .zodiaccolorroles import ZodiacColorRoles

async def setup(bot):
    await bot.add_cog(ZodiacColorRoles(bot))