import discord
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import box, humanize_list
import asyncio
import random
from typing import Optional, Dict, List


class Paranoia(commands.Cog):
    """
    A cog for playing the social party game Paranoia in Discord.
    
    In Paranoia, players whisper questions about other players, and answers are revealed publicly
    while keeping the questions secret until the end of the round.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        
        default_guild = {
            "active_games": {},
            "custom_questions": []
        }
        
        self.config.register_guild(**default_guild)
        
        # Default questions for the game
        self.default_questions = [
            "Who would survive the longest in a zombie apocalypse?",
            "Who would be most likely to become famous?",
            "Who gives the best hugs?",
            "Who would make the best teacher?",
            "Who is most likely to become a millionaire?",
            "Who would you want on your team in a trivia contest?",
            "Who has the best sense of humor?",
            "Who would be the best travel companion?",
            "Who is most likely to forget their own birthday?",
            "Who would make the best superhero?",
            "Who is most likely to win a cooking competition?",
            "Who would be the best at keeping secrets?",
            "Who is most likely to become a professional athlete?",
            "Who would you trust to plan your birthday party?",
            "Who has the most contagious laugh?"
        ]

    @commands.group(name="paranoia", invoke_without_command=True)
    async def paranoia(self, ctx):
        """Main command group for Paranoia game."""
        await ctx.send_help(ctx.command)

    @paranoia.command(name="start")
    async def start_game(self, ctx, *players: discord.Member):
        """
        Start a new Paranoia game.
        
        Usage: `[p]paranoia start @player1 @player2 @player3`
        Minimum 3 players required.
        """
        if len(players) < 3:
            await ctx.send("❌ You need at least 3 players to start a Paranoia game!")
            return
        
        guild_data = await self.config.guild(ctx.guild).active_games()
        
        if str(ctx.channel.id) in guild_data:
            await ctx.send("❌ There's already an active game in this channel! Use `[p]paranoia stop` to end it first.")
            return
        
        # Initialize game data
        game_data = {
            "players": [p.id for p in players],
            "round": 1,
            "current_questions": {},
            "current_answers": {},
            "host": ctx.author.id,
            "status": "waiting_for_questions"
        }
        
        guild_data[str(ctx.channel.id)] = game_data
        await self.config.guild(ctx.guild).active_games.set(guild_data)
        
        player_mentions = humanize_list([p.mention for p in players])
        
        embed = discord.Embed(
            title="🎭 Paranoia Game Started!",
            description=f"**Players:** {player_mentions}\n**Round:** 1",
            color=discord.Color.red()
        )
        embed.add_field(
            name="How to Play",
            value="1. Each player will receive a random question via DM\n"
                  "2. Answer the question by thinking of another player\n"
                  "3. Submit your answer using `[p]paranoia answer @player`\n"
                  "4. Once all answers are in, they'll be revealed!",
            inline=False
        )
        
        await ctx.send(embed=embed)
        await self._send_questions(ctx, players)

    async def _send_questions(self, ctx, players):
        """Send random questions to each player via DM."""
        questions = self.default_questions.copy()
        custom_questions = await self.config.guild(ctx.guild).custom_questions()
        questions.extend(custom_questions)
        
        if len(questions) < len(players):
            questions = questions * ((len(players) // len(questions)) + 1)
        
        random.shuffle(questions)
        
        guild_data = await self.config.guild(ctx.guild).active_games()
        game_data = guild_data[str(ctx.channel.id)]
        
        for i, player in enumerate(players):
            question = questions[i]
            game_data["current_questions"][str(player.id)] = question
            
            try:
                embed = discord.Embed(
                    title="🎭 Your Paranoia Question",
                    description=f"**Question:** {question}",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="How to Answer",
                    value=f"Go to {ctx.channel.mention} and use:\n`{ctx.prefix}paranoia answer @player`",
                    inline=False
                )
                
                await player.send(embed=embed)
            except discord.Forbidden:
                await ctx.send(f"❌ Couldn't send DM to {player.mention}. They need to allow DMs from server members.")
        
        await self.config.guild(ctx.guild).active_games.set(guild_data)

    @paranoia.command(name="answer")
    async def submit_answer(self, ctx, player: discord.Member):
        """
        Submit your answer for the current round.
        
        Usage: `[p]paranoia answer @player`
        """
        guild_data = await self.config.guild(ctx.guild).active_games()
        
        if str(ctx.channel.id) not in guild_data:
            await ctx.send("❌ No active game in this channel!")
            return
        
        game_data = guild_data[str(ctx.channel.id)]
        
        if ctx.author.id not in game_data["players"]:
            await ctx.send("❌ You're not part of this game!")
            return
        
        if str(ctx.author.id) in game_data["current_answers"]:
            await ctx.send("❌ You've already submitted your answer for this round!")
            return
        
        if player.id not in game_data["players"]:
            await ctx.send("❌ That player is not part of this game!")
            return
        
        # Record the answer
        game_data["current_answers"][str(ctx.author.id)] = {
            "answer": player.id,
            "answer_name": player.display_name
        }
        
        await ctx.send(f"✅ Your answer has been recorded!")
        
        # Check if all answers are in
        if len(game_data["current_answers"]) == len(game_data["players"]):
            await self._reveal_answers(ctx, game_data)
        else:
            remaining = len(game_data["players"]) - len(game_data["current_answers"])
            await ctx.send(f"⏳ Waiting for {remaining} more answer(s)...")
        
        await self.config.guild(ctx.guild).active_games.set(guild_data)

    async def _reveal_answers(self, ctx, game_data):
        """Reveal all answers for the current round."""
        embed = discord.Embed(
            title=f"🎭 Round {game_data['round']} Results",
            color=discord.Color.green()
        )
        
        # Show answers without revealing questions yet
        for player_id, answer_data in game_data["current_answers"].items():
            player = self.bot.get_user(int(player_id))
            answer_player = self.bot.get_user(answer_data["answer"])
            
            if player and answer_player:
                embed.add_field(
                    name=f"{player.display_name}'s Answer",
                    value=answer_player.display_name,
                    inline=True
                )
        
        await ctx.send(embed=embed)
        
        # Ask if players want to reveal questions
        embed2 = discord.Embed(
            title="🤫 Reveal Questions?",
            description="React with ✅ to reveal what questions each player answered!\n"
                       "React with ➡️ to start the next round without revealing questions.",
            color=discord.Color.blue()
        )
        
        message = await ctx.send(embed=embed2)
        await message.add_reaction("✅")
        await message.add_reaction("➡️")
        
        # Store message ID for reaction handling
        game_data["reveal_message"] = message.id
        
        guild_data = await self.config.guild(ctx.guild).active_games()
        guild_data[str(ctx.channel.id)] = game_data
        await self.config.guild(ctx.guild).active_games.set(guild_data)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle reactions for question reveals and next round."""
        if user.bot:
            return
        
        guild_data = await self.config.guild(reaction.message.guild).active_games()
        channel_id = str(reaction.message.channel.id)
        
        if channel_id not in guild_data:
            return
        
        game_data = guild_data[channel_id]
        
        if game_data.get("reveal_message") != reaction.message.id:
            return
        
        if user.id not in game_data["players"] and user.id != game_data["host"]:
            return
        
        if str(reaction.emoji) == "✅":
            await self._reveal_questions(reaction.message, game_data)
        elif str(reaction.emoji) == "➡️":
            await self._next_round(reaction.message, game_data)

    async def _reveal_questions(self, message, game_data):
        """Reveal what questions each player answered."""
        embed = discord.Embed(
            title="🎭 Questions Revealed!",
            color=discord.Color.purple()
        )
        
        for player_id, answer_data in game_data["current_answers"].items():
            player = self.bot.get_user(int(player_id))
            question = game_data["current_questions"].get(str(player_id), "Unknown question")
            
            if player:
                embed.add_field(
                    name=f"{player.display_name}'s Question",
                    value=f"**Q:** {question}\n**A:** {answer_data['answer_name']}",
                    inline=False
                )
        
        await message.channel.send(embed=embed)
        
        # Offer to start next round
        embed2 = discord.Embed(
            title="Next Round?",
            description="React with ➡️ to start the next round!",
            color=discord.Color.blue()
        )
        
        next_message = await message.channel.send(embed=embed2)
        await next_message.add_reaction("➡️")
        
        game_data["reveal_message"] = next_message.id

    async def _next_round(self, message, game_data):
        """Start the next round."""
        # Clear current round data
        game_data["current_questions"] = {}
        game_data["current_answers"] = {}
        game_data["round"] += 1
        game_data["status"] = "waiting_for_questions"
        
        # Update config
        guild_data = await self.config.guild(message.guild).active_games()
        guild_data[str(message.channel.id)] = game_data
        await self.config.guild(message.guild).active_games.set(guild_data)
        
        # Get players and send new questions
        players = [self.bot.get_user(pid) for pid in game_data["players"]]
        players = [p for p in players if p is not None]
        
        embed = discord.Embed(
            title=f"🎭 Round {game_data['round']} Starting!",
            description="Check your DMs for new questions!",
            color=discord.Color.red()
        )
        
        await message.channel.send(embed=embed)
        await self._send_questions(message.channel, players)

    @paranoia.command(name="stop")
    async def stop_game(self, ctx):
        """Stop the current Paranoia game."""
        guild_data = await self.config.guild(ctx.guild).active_games()
        
        if str(ctx.channel.id) not in guild_data:
            await ctx.send("❌ No active game in this channel!")
            return
        
        game_data = guild_data[str(ctx.channel.id)]
        
        if ctx.author.id != game_data["host"] and not ctx.author.guild_permissions.manage_messages:
            await ctx.send("❌ Only the game host or someone with Manage Messages permission can stop the game!")
            return
        
        del guild_data[str(ctx.channel.id)]
        await self.config.guild(ctx.guild).active_games.set(guild_data)
        
        await ctx.send("🛑 Paranoia game stopped!")

    @paranoia.command(name="addquestion")
    async def add_question(self, ctx, *, question: str):
        """Add a custom question to the server's question pool."""
        if len(question) > 200:
            await ctx.send("❌ Questions must be 200 characters or less!")
            return
        
        custom_questions = await self.config.guild(ctx.guild).custom_questions()
        
        if question in custom_questions:
            await ctx.send("❌ That question is already in the pool!")
            return
        
        custom_questions.append(question)
        await self.config.guild(ctx.guild).custom_questions.set(custom_questions)
        
        await ctx.send(f"✅ Added question: {question}")

    @paranoia.command(name="questions")
    async def list_questions(self, ctx):
        """List all available questions (default + custom)."""
        custom_questions = await self.config.guild(ctx.guild).custom_questions()
        
        embed = discord.Embed(
            title="🎭 Available Questions",
            color=discord.Color.blue()
        )
        
        if custom_questions:
            custom_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(custom_questions)])
            embed.add_field(
                name=f"Custom Questions ({len(custom_questions)})",
                value=custom_text[:1024],
                inline=False
            )
        
        embed.add_field(
            name=f"Default Questions ({len(self.default_questions)})",
            value=f"There are {len(self.default_questions)} default questions available.",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @paranoia.command(name="status")
    async def game_status(self, ctx):
        """Check the status of the current game."""
        guild_data = await self.config.guild(ctx.guild).active_games()
        
        if str(ctx.channel.id) not in guild_data:
            await ctx.send("❌ No active game in this channel!")
            return
        
        game_data = guild_data[str(ctx.channel.id)]
        
        players = [self.bot.get_user(pid) for pid in game_data["players"]]
        players = [p.display_name for p in players if p is not None]
        
        answers_submitted = len(game_data["current_answers"])
        total_players = len(game_data["players"])
        
        embed = discord.Embed(
            title="🎭 Game Status",
            color=discord.Color.blue()
        )
        embed.add_field(name="Round", value=game_data["round"], inline=True)
        embed.add_field(name="Players", value=humanize_list(players), inline=False)
        embed.add_field(
            name="Progress", 
            value=f"{answers_submitted}/{total_players} answers submitted", 
            inline=True
        )
        
        await ctx.send(embed=embed)