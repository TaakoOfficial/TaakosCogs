from .knowledgegarden import KnowledgeGarden


async def setup(bot):
    await bot.add_cog(KnowledgeGarden(bot))
