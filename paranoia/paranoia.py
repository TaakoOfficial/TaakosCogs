from __future__ import annotations

import logging
import random
import re

import discord
from redbot.core import Config, commands
from redbot.core.utils.chat_formatting import humanize_list

from .dashboard_integration import DashboardIntegration

log = logging.getLogger("red.taakoscogs.paranoia")


class Paranoia(DashboardIntegration, commands.Cog):
    """
    A cog for playing the social party game Paranoia in Discord.

    In Paranoia, players whisper questions about other players, and answers are revealed publicly
    while keeping the questions secret until the end of the round.

    Features Tupperbox integration for roleplay communities!
    """

    CONFIG_IDENTIFIER = 1122110071725183678
    LEGACY_CONFIG_IDENTIFIER = 1234567890
    IDENTIFIER_MIGRATION_VERSION = 1

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=self.CONFIG_IDENTIFIER,
            force_registration=True,
        )
        self._legacy_config = Config.get_conf(
            self,
            identifier=self.LEGACY_CONFIG_IDENTIFIER,
            force_registration=True,
        )

        default_guild = {
            "active_games": {},
            "custom_questions": [],
            "tupperbox_support": True,
        }

        self.config.register_global(identifier_migration_version=0)
        self.config.register_guild(**default_guild)
        self._legacy_config.register_guild(**default_guild)

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
            "Who has the most contagious laugh?",
        ]

    async def cog_load(self) -> None:
        """Migrate settings from the legacy Config identifier before use."""
        await self._migrate_config_identifier()

    async def _migrate_config_identifier(self) -> None:
        """Copy legacy guild data once, retaining the old namespace for rollback."""
        if (
            await self.config.identifier_migration_version()
            >= self.IDENTIFIER_MIGRATION_VERSION
        ):
            return

        legacy_guilds = await self._legacy_config.all_guilds()
        destination_guild_ids = set((await self.config.all_guilds()).keys())
        copied = 0
        for guild_id, data in legacy_guilds.items():
            if guild_id in destination_guild_ids:
                continue
            destination = self.config.guild_from_id(guild_id)
            await destination.set(data)
            if await destination.all() != data:
                raise RuntimeError(
                    f"Paranoia Config migration verification failed for guild {guild_id}.",
                )
            copied += 1

        await self.config.identifier_migration_version.set(
            self.IDENTIFIER_MIGRATION_VERSION,
        )
        log.info(
            "Paranoia Config identifier migration completed for %d guild(s).",
            copied,
        )

    def _is_tupperbox_message(self, message: discord.Message) -> bool:
        """Check if a message is from Tupperbox."""
        if not message.webhook_id:
            return False

        # Check if the webhook name contains common Tupperbox patterns
        if message.author.name == "Tupperbox":
            return True

        # Check for Tupperbox message format indicators
        return bool(
            message.webhook_id
            and (
                message.author.discriminator == "0000"
                or hasattr(message, "interaction")
                and message.interaction is None
            ),
        )

    async def _get_tupperbox_user(
        self,
        message: discord.Message,
    ) -> discord.Member | None:
        """Extract the actual user behind a Tupperbox proxy message."""
        if not self._is_tupperbox_message(message):
            return None

        guild = message.guild
        if not guild:
            return None

        # Look for user mention or ID in message content patterns
        # Tupperbox often includes user info in specific formats
        content = message.content.lower()

        # Try to find user ID in common Tupperbox formats
        # Pattern: Looking for user IDs in various formats
        user_id_pattern = r"(?:user[:\s]*|id[:\s]*|<@!?(\d+)>|\b(\d{17,19})\b)"
        matches = re.findall(user_id_pattern, content)

        for match in matches:
            user_id = match[0] or match[1] if isinstance(
                match, tuple) else match
            if user_id and user_id.isdigit():
                try:
                    member = guild.get_member(int(user_id))
                    if member:
                        return member
                except (ValueError, AttributeError):
                    continue

        # Alternative: Look in recent message history for the triggering user
        # Check the last few messages for potential Tupperbox trigger
        try:
            async for hist_msg in message.channel.history(limit=10, before=message):
                # Look for messages that might have triggered this Tupperbox message
                if hist_msg.author.bot:
                    continue

                # Check if this could be a Tupperbox trigger
                if any(
                    prefix in hist_msg.content.lower()
                    for prefix in ["tupper:", "tb:", "proxy:"]
                ):
                    return hist_msg.author

        except discord.HTTPException:
            pass

        return None

    async def _resolve_user_from_message(
        self,
        message: discord.Message,
    ) -> discord.Member | None:
        """Resolve the actual user from a message, handling both regular and Tupperbox messages."""
        if self._is_tupperbox_message(message):
            tupperbox_support = await self.config.guild(
                message.guild,
            ).tupperbox_support()
            if tupperbox_support:
                return await self._get_tupperbox_user(message)

        # Return the message author if not a Tupperbox message or if Tupperbox support is disabled
        return message.author if isinstance(message.author, discord.Member) else None

    async def _get_display_name(
        self,
        user: discord.Member | discord.User,
        message: discord.Message | None = None,
    ) -> str:
        """Get the appropriate display name, considering Tupperbox proxies."""
        if message and self._is_tupperbox_message(message):
            # For Tupperbox messages, use the proxy name
            return message.author.display_name
        return user.display_name

    @commands.hybrid_group(name="paranoia", invoke_without_command=True)
    async def paranoia(self, ctx):
        """Main command group for Paranoia game."""
        await ctx.send_help(ctx.command)

    @paranoia.command(name="start", with_app_command=False)
    async def start_game(self, ctx, *players: discord.Member):
        """
        Start a new Paranoia game.

        Usage: `[p]paranoia start @player1 @player2 @player3`
        Minimum 3 players required.
        """
        await self._start_game(ctx, players)

    @paranoia.app_command.command(
        name="start",
        description="Start a new Paranoia game.",
    )
    @discord.app_commands.describe(
        player_1="First player",
        player_2="Second player",
        player_3="Third player",
        player_4="Optional fourth player",
        player_5="Optional fifth player",
        player_6="Optional sixth player",
        player_7="Optional seventh player",
        player_8="Optional eighth player",
        player_9="Optional ninth player",
        player_10="Optional tenth player",
    )
    @discord.app_commands.guild_only()
    async def start_game_slash(
        self,
        interaction: discord.Interaction,
        player_1: discord.Member,
        player_2: discord.Member,
        player_3: discord.Member,
        player_4: discord.Member | None = None,
        player_5: discord.Member | None = None,
        player_6: discord.Member | None = None,
        player_7: discord.Member | None = None,
        player_8: discord.Member | None = None,
        player_9: discord.Member | None = None,
        player_10: discord.Member | None = None,
    ) -> None:
        """Native slash wrapper for the variadic prefix command."""
        ctx = await commands.Context.from_interaction(interaction)
        players = tuple(
            player
            for player in (
                player_1,
                player_2,
                player_3,
                player_4,
                player_5,
                player_6,
                player_7,
                player_8,
                player_9,
                player_10,
            )
            if player is not None
        )
        await self._start_game(ctx, players)

    async def _start_game(self, ctx, players):
        """Start a game for prefix and application-command entry points."""
        # Check if command is being used in a guild context
        if not ctx.guild:
            await ctx.send(
                "❌ This command can only be used in a server channel, not in DMs!",
            )
            return

        if len(players) < 3:
            await ctx.send("❌ You need at least 3 players to start a Paranoia game!")
            return

        guild_data = await self.config.guild(ctx.guild).active_games()

        if str(ctx.channel.id) in guild_data:
            await ctx.send(
                "❌ There's already an active game in this channel! Use `[p]paranoia stop` to end it first.",
            )
            return

        # Initialize game data
        game_data = {
            "players": [p.id for p in players],
            "round": 1,
            "current_questions": {},
            "current_answers": {},
            "host": ctx.author.id,
            "status": "waiting_for_questions",
        }

        guild_data[str(ctx.channel.id)] = game_data
        await self.config.guild(ctx.guild).active_games.set(guild_data)

        player_mentions = humanize_list([p.mention for p in players])

        tupperbox_status = await self.config.guild(ctx.guild).tupperbox_support()
        tupperbox_note = (
            "\n🎭 **Tupperbox users:** Your proxy characters can participate!"
            if tupperbox_status
            else ""
        )

        embed = discord.Embed(
            title="🎭 Paranoia Game Started!",
            description=f"**Players:** {player_mentions}\n**Round:** 1{tupperbox_note}",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="How to Play",
            value="1. Each player will receive a random question via DM\n"
            "2. Answer the question by thinking of another player\n"
            "3. Submit your answer using `[p]paranoia answer @player`\n"
            "4. Once all answers are in, they'll be revealed!",
            inline=False,
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
                    color=discord.Color.orange(),
                )
                embed.add_field(
                    name="How to Answer",
                    value=f"Go to {ctx.channel.mention} and use:\n`{ctx.prefix}paranoia answer @player`\n\n"
                    "💡 **Tip:** Tupperbox users can use their proxy characters to answer!",
                    inline=False,
                )

                await player.send(embed=embed)
            except discord.Forbidden:
                await ctx.send(
                    f"❌ Couldn't send DM to {player.mention}. They need to allow DMs from server members.",
                )

        await self.config.guild(ctx.guild).active_games.set(guild_data)

    @paranoia.command(name="answer")
    async def submit_answer(self, ctx, player: discord.Member):
        """
        Submit your answer for the current round.

        Usage: `[p]paranoia answer @player`
        Works with Tupperbox proxies - the bot will detect the real user behind proxies.
        """
        # Check if command is being used in a guild context
        if not ctx.guild:
            await ctx.send(
                "❌ This command can only be used in a server channel, not in DMs!",
            )
            return

        guild_data = await self.config.guild(ctx.guild).active_games()

        if str(ctx.channel.id) not in guild_data:
            await ctx.send("❌ No active game in this channel!")
            return

        game_data = guild_data[str(ctx.channel.id)]

        # Resolve the actual user (handles Tupperbox)
        actual_user = await self._resolve_user_from_message(ctx.message)
        if not actual_user:
            await ctx.send("❌ Could not determine the user behind this message!")
            return

        if actual_user.id not in game_data["players"]:
            await ctx.send("❌ You're not part of this game!")
            return

        if str(actual_user.id) in game_data["current_answers"]:
            await ctx.send("❌ You've already submitted your answer for this round!")
            return

        if player.id not in game_data["players"]:
            await ctx.send("❌ That player is not part of this game!")
            return

        # Get appropriate display names
        answerer_name = await self._get_display_name(actual_user, ctx.message)
        answer_name = await self._get_display_name(player)

        # Record the answer
        game_data["current_answers"][str(actual_user.id)] = {
            "answer": player.id,
            "answer_name": answer_name,
            "answerer_display_name": answerer_name,
        }

        await ctx.send("✅ Your answer has been recorded!")

        # Check if all answers are in
        if len(game_data["current_answers"]) == len(game_data["players"]):
            await self._reveal_answers(ctx, game_data)
        else:
            remaining = len(game_data["players"]) - \
                            len(game_data["current_answers"])
            await ctx.send(f"⏳ Waiting for {remaining} more answer(s)...")

        await self.config.guild(ctx.guild).active_games.set(guild_data)

    async def _reveal_answers(self, ctx, game_data):
        """Reveal all answers for the current round."""
        embed = discord.Embed(
            title=f"🎭 Round {game_data['round']} Results",
            color=discord.Color.green(),
        )

        # Show answers without revealing questions yet
        for player_id, answer_data in game_data["current_answers"].items():
            player = self.bot.get_user(int(player_id))
            answer_player = self.bot.get_user(answer_data["answer"])

            if player and answer_player:
                # Use stored display names which may include Tupperbox proxy names
                answerer_name = answer_data.get(
                    "answerer_display_name",
                    player.display_name,
                )
                answer_name = answer_data.get(
                    "answer_name", answer_player.display_name)

                embed.add_field(
                    name=f"{answerer_name}'s Answer",
                    value=answer_name,
                    inline=True,
                )

        await ctx.send(embed=embed)

        # Ask if players want to reveal questions
        embed2 = discord.Embed(
            title="🤫 Reveal Questions?",
            description="React with ✅ to reveal what questions each player answered!\n"
            "React with ➡️ to start the next round without revealing questions.",
            color=discord.Color.blue(),
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

        guild = reaction.message.guild
        if guild is None or await self.bot.cog_disabled_in_guild(self, guild):
            return

        guild_data = await self.config.guild(guild).active_games()
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
            color=discord.Color.purple(),
        )

        for player_id, answer_data in game_data["current_answers"].items():
            player = self.bot.get_user(int(player_id))
            question = game_data["current_questions"].get(
                str(player_id),
                "Unknown question",
            )

            if player:
                # Use stored display names which may include Tupperbox proxy names
                answerer_name = answer_data.get(
                    "answerer_display_name",
                    player.display_name,
                )
                answer_name = answer_data.get("answer_name", "Unknown")

                embed.add_field(
                    name=f"{answerer_name}'s Question",
                    value=f"**Q:** {question}\n**A:** {answer_name}",
                    inline=False,
                )

        await message.channel.send(embed=embed)

        # Offer to start next round
        embed2 = discord.Embed(
            title="Next Round?",
            description="React with ➡️ to start the next round!",
            color=discord.Color.blue(),
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
            color=discord.Color.red(),
        )

        await message.channel.send(embed=embed)
        await self._send_questions(message.channel, players)

    @paranoia.command(name="stop")
    async def stop_game(self, ctx):
        """Stop the current Paranoia game."""
        # Check if command is being used in a guild context
        if not ctx.guild:
            await ctx.send(
                "❌ This command can only be used in a server channel, not in DMs!",
            )
            return

        guild_data = await self.config.guild(ctx.guild).active_games()

        if str(ctx.channel.id) not in guild_data:
            await ctx.send("❌ No active game in this channel!")
            return

        game_data = guild_data[str(ctx.channel.id)]

        if (
            ctx.author.id != game_data["host"]
            and not ctx.author.guild_permissions.manage_messages
        ):
            await ctx.send(
                "❌ Only the game host or someone with Manage Messages permission can stop the game!",
            )
            return

        del guild_data[str(ctx.channel.id)]
        await self.config.guild(ctx.guild).active_games.set(guild_data)

        await ctx.send("🛑 Paranoia game stopped!")

    @paranoia.command(name="addquestion")
    async def add_question(self, ctx, *, question: str):
        """Add a custom question to the server's question pool."""
        # Check if command is being used in a guild context
        if not ctx.guild:
            await ctx.send(
                "❌ This command can only be used in a server channel, not in DMs!",
            )
            return

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
        # Check if command is being used in a guild context
        if not ctx.guild:
            await ctx.send(
                "❌ This command can only be used in a server channel, not in DMs!",
            )
            return

        custom_questions = await self.config.guild(ctx.guild).custom_questions()

        embed = discord.Embed(
            title="🎭 Available Questions",
            color=discord.Color.blue(),
        )

        if custom_questions:
            custom_text = "\n".join(
                [f"{i + 1}. {q}" for i, q in enumerate(custom_questions)],
            )
            embed.add_field(
                name=f"Custom Questions ({len(custom_questions)})",
                value=custom_text[:1024],
                inline=False,
            )

        embed.add_field(
            name=f"Default Questions ({len(self.default_questions)})",
            value=f"There are {len(self.default_questions)} default questions available.",
            inline=False,
        )

        await ctx.send(embed=embed)

    @paranoia.command(name="status")
    async def game_status(self, ctx):
        """Check the status of the current game."""
        # Check if command is being used in a guild context
        if not ctx.guild:
            await ctx.send(
                "❌ This command can only be used in a server channel, not in DMs!",
            )
            return

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
            color=discord.Color.blue(),
        )
        embed.add_field(name="Round", value=game_data["round"], inline=True)
        embed.add_field(name="Players", value=humanize_list(
            players), inline=False)
        embed.add_field(
            name="Progress",
            value=f"{answers_submitted}/{total_players} answers submitted",
            inline=True,
        )

        await ctx.send(embed=embed)

    @paranoia.command(name="tupperbox")
    async def toggle_tupperbox(self, ctx, enabled: bool | None = None):
        """
        Toggle Tupperbox support for this server or check current status.

        Usage:
        `[p]paranoia tupperbox` - Check current status
        `[p]paranoia tupperbox true` - Enable Tupperbox support
        `[p]paranoia tupperbox false` - Disable Tupperbox support
        """
        # Check if command is being used in a guild context
        if not ctx.guild:
            await ctx.send(
                "❌ This command can only be used in a server channel, not in DMs!",
            )
            return

        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send(
                "❌ You need Manage Server permissions to change Tupperbox settings!",
            )
            return

        if enabled is None:
            # Check current status
            current = await self.config.guild(ctx.guild).tupperbox_support()
            status = "enabled" if current else "disabled"
            embed = discord.Embed(
                title="🎭 Tupperbox Support Status",
                description=f"Tupperbox support is currently **{status}** for this server.",
                color=discord.Color.blue(),
            )
            if current:
                embed.add_field(
                    name="What this means",
                    value="• Proxy characters can participate in games\n"
                    "• Answers will show proxy names\n"
                    "• Bot detects real users behind proxies",
                    inline=False,
                )
            await ctx.send(embed=embed)
            return

        # Set new status
        await self.config.guild(ctx.guild).tupperbox_support.set(enabled)
        status = "enabled" if enabled else "disabled"

        embed = discord.Embed(
            title="✅ Tupperbox Support Updated",
            description=f"Tupperbox support has been **{status}** for this server.",
            color=discord.Color.green(),
        )

        if enabled:
            embed.add_field(
                name="Tupperbox Features Now Active",
                value="• Proxy characters can participate in Paranoia games\n"
                "• Game results will show proxy character names\n"
                "• Bot will automatically detect real users behind proxies",
                inline=False,
            )
        else:
            embed.add_field(
                name="Tupperbox Features Disabled",
                value="• Only regular Discord users can participate\n"
                "• Proxy messages will be ignored",
                inline=False,
            )

        await ctx.send(embed=embed)
