import datetime
import discord
from discord.ext import commands
import sqlite3


class Database(commands.Cog):
    """
    A cog for managing the SQLite database.
    """

    def __init__(self, bot):
        self.bot = bot
        self.db_path = "database.db"  # Path to your database file
        self.permitted_roles = bot.config.get("permitted_roles")
        self.create_table()

    def cog_check(self, ctx):  # Use cog_check for the permission check
        """
        A local check that applies to all commands in this cog.
        """
        return commands.has_any_role(*self.permitted_roles).predicate(ctx)

    def create_table(self):
        """Creates the cooldowns table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                cooldown_end_time TEXT NOT NULL,
                PRIMARY KEY (user_id, channel_id)
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS minecraft_users (
                discord_user_id INT NOT NULL,
                minecraft_username TEXT NOT NULL,
                PRIMARY KEY (discord_user_id)
            )"""
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tags (
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                use_count INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, name)
                )
            """
        )
        conn.commit()
        conn.close()

    async def run_query(self, query, params=None, fetch=False):
        """Runs a SQL query against the database.

        Args:
            query (str): The SQL query to execute.
            params (tuple, optional): Parameters to substitute into the query. Defaults to None.
            fetch (bool, optional): Whether to fetch and return the results. Defaults to False.

        Returns:
            list or None: The query results if fetch is True, otherwise None.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            conn.commit()
            if fetch:
                return cursor.fetchall()
            else:
                return None

        except Exception as e:
            print(f"Error running query: {e}")
            raise  # Re-raise the exception after logging
        finally:
            if conn:
                conn.close()

    async def insert_cooldown(self, user_id, channel_id, cooldown_expiry):
        """Inserts or updates the cooldown for a user in a channel."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO cooldowns (user_id, channel_id, cooldown_end_time)
                VALUES (?, ?, ?)
            """,
                (user_id, channel_id, cooldown_expiry.isoformat()),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error inserting cooldown into database: {e}")

    async def get_cooldown(self, user_id, channel_id):
        """Retrieves the cooldown end time for a user in a channel."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cooldown_end_time FROM cooldowns
                WHERE user_id = ? AND channel_id = ?
            """,
                (user_id, channel_id),
            )
            result = cursor.fetchone()
            conn.close()
            return datetime.datetime.fromisoformat(result[0]) if result else None
        except Exception as e:
            print(f"Error retrieving cooldown from database: {e}")
            return None

    async def get_user_level_and_xp_to_next(self, user: discord.Member):
        """
        Retrieves a user's current experience points and level, and calculates the experience needed to reach the next level.
        If the user does not exist in the database, they are added with zero experience and level.

        Args:
            user: The Discord member whose experience and level information is to be retrieved.

        Returns:
            A tuple containing the user's current experience, level, and the experience points needed to reach the next level.

        Raises:
            Exception: If there is an error during the database operation.

        Examples:
            xp, level, xp_to_next = await get_user_level_and_xp_to_next(user)
        """

        user_id = user.id

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT experience FROM experience
                WHERE user_id = ?
                """,
                (user_id,),
            )
            result = cursor.fetchone()

            if not result:
                # User not found, add them with 0 experience
                cursor.execute(
                    """
                    INSERT INTO experience (user_id, experience, level)
                    VALUES (?, 0, 0)
                    """,
                    (user_id,),
                )
                conn.commit()
                return 0, 0, 100  # Return 0 XP, 0 level, and 100 XP to next level

            xp = result[0]
            lvl = 0
            xp_needed = 5 * (lvl**2) + (50 * lvl) + 100  # XP needed for the next level

            while xp >= xp_needed:
                xp -= xp_needed  # Subtract XP needed for the current level
                lvl += 1
                xp_needed = 5 * (lvl**2) + (50 * lvl) + 100  # Calculate for next level

            xp_to_next_level = xp_needed - xp  # Remaining XP to next level

            return xp, lvl, xp_to_next_level

        except Exception as e:
            print(f"Error calculating level and XP to next level: {e}")
            return None

        finally:
            if conn:
                conn.close()

    async def insert_cooldown(self, user_id, channel_id, cooldown_expiry):
        """Inserts or updates the cooldown for a user in a channel."""
        await self.run_query(
            """
            INSERT OR REPLACE INTO cooldowns (user_id, channel_id, cooldown_end_time)
            VALUES (?, ?, ?)
            """,
            (user_id, channel_id, cooldown_expiry.isoformat()),
        )

    async def get_cooldown(self, user_id, channel_id):
        """Retrieves the cooldown end time for a user in a channel."""
        result = await self.run_query(
            """
            SELECT cooldown_end_time FROM cooldowns
            WHERE user_id = ? AND channel_id = ?
            """,
            (user_id, channel_id),
            fetch=True,  # Fetch the result
        )

        if result and result[0]:  # Added error handling for no return
            return datetime.datetime.fromisoformat(result[0][0])
        return None

    async def add_minecraft_user(self, discord_user_id, minecraft_username):
        """Adds a Minecraft user to the database."""

        if self.get_minecraft_user(discord_user_id):
            return False

        await self.run_query(
            """
            INSERT INTO minecraft_users (discord_user_id, minecraft_username)
            VALUES (?, ?)
            """,
            (discord_user_id, minecraft_username),
        )
        return True

    async def get_minecraft_user(self, discord_user_id):
        """Retrieves a Minecraft user from the database."""
        result = await self.run_query(
            """
            SELECT minecraft_username FROM minecraft_users
            WHERE discord_user_id = ?
            """,
            (discord_user_id,),
            fetch=True,
        )

        if result and result[0]:
            return result[0][0]
        return None

    async def remove_minecraft_user(self, user_input):
        """Removes a Minecraft user from the database."""

        if user_input.isdigit():
            discord_user_id = int(input)
            if not self.get_minecraft_user(discord_user_id):
                return False
            await self.run_query(
                """
                    DELETE FROM minecraft_users
                    WHERE discord_user_id = ?
                    """,
                (discord_user_id,),
            )

        else:
            minecraft_username = user_input
            result = await self.run_query(
                """
                SELECT discord_user_id FROM minecraft_users
                WHERE minecraft_username = ?
                """,
                (minecraft_username,),
            )
            if not result or not result[0]:
                return False
            discord_user_id = result[0]
            if not self.get_minecraft_user(discord_user_id):
                return False
            await self.run_query(
                """
                        DELETE FROM minecraft_users
                        WHERE discord_user_id = ?
                        """,
                (discord_user_id,),
            )

        return True

    async def add_xp(self, user_id, experience_to_give):
        """
        Adds experience points to a user's record in the database and updates their level if necessary.
        This function handles both existing users by updating their experience and level, and new users by initializing their records.

        Args:
            user_id: The ID of the user to whom experience points will be added.
            experience_to_give: The amount of experience points to add to the user's record.

        Returns:
            None

        Raises:
            Exception: If there is an error during the database operation.

        Examples:
            await add_xp(user_id=12345, experience_to_give=50)
        """

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get the user's current experience and level
            cursor.execute(
                "SELECT experience, level FROM experience WHERE user_id = ?", (user_id,)
            )
            result = cursor.fetchone()

            if result:
                current_xp, current_level = result
                new_xp = current_xp + experience_to_give

                # Calculate the new level
                new_level = current_level
                xp_needed = 5 * (new_level**2) + (50 * new_level) + 100

                while new_xp >= xp_needed:
                    new_xp -= xp_needed
                    new_level += 1
                    xp_needed = 5 * (new_level**2) + (50 * new_level) + 100

                # Update the user's experience and level if it changed
                if new_level != current_level:
                    cursor.execute(
                        "UPDATE experience SET experience = ?, level = ? WHERE user_id = ?",
                        (new_xp, new_level, user_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE experience SET experience = ? WHERE user_id = ?",
                        (new_xp, user_id),
                    )
            else:
                # If the user doesn't exist, add them to the database
                new_level = 0
                xp_needed = 5 * (new_level**2) + (50 * new_level) + 100
                while experience_to_give >= xp_needed:
                    experience_to_give -= xp_needed
                    new_level += 1
                    xp_needed = 5 * (new_level**2) + (50 * new_level) + 100

                cursor.execute(
                    """
                    INSERT INTO experience (user_id, experience, level) 
                    VALUES (?, ?, ?)
                    """,
                    (user_id, experience_to_give, new_level),
                )

            conn.commit()

        except Exception as e:
            print(f"Error adding XP to database: {e}")

        finally:
            if conn:
                conn.close()

    async def get_leaderboard(self):
        """
        Retrieves the top 100 users from the database based on their level.

        Returns:
            A list of lists, where each inner list contains the user_id and level
            of a user, sorted in descending order by level.
            Returns None if there is an error.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, level FROM experience
                ORDER BY level DESC
                LIMIT 100
                """
            )
            result = cursor.fetchall()

            return [[row[0], row[1]] for row in result]
        except Exception as e:
            print(f"Error retrieving leaderboard from database: {e}")
            return None

        finally:
            if conn:
                conn.close()

    async def reset_user_xp_level(self, user_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE experience 
                SET experience = 0, level = 0 
                WHERE user_id = ?
                """,
                (user_id,),
            )
            conn.commit()
            return True

        except Exception as e:
            print(f"Error resetting user level and experience: {e}")
            return False
        finally:
            if conn:
                conn.close()

    #####################
    ###     TAGS      ###
    #####################

    async def add_count(self, guild_id, name):
        result = await self.run_query(
            """
            UPDATE tags
            SET use_count = use_count + 1
            WHERE guild_id = ? AND name = ?
            """,
            (guild_id, name),
        )

    async def get_tag(self, guild_id, name):
        """Retrieves the content of a tag and increments the use_count."""
        try:
            # Fetch the tag content
            result = await self.run_query(
                """
                SELECT content FROM tags
                WHERE guild_id = ? AND name = ?
                """,
                (guild_id, name),
                fetch=True,
            )
            if result and result[0]:
                # Increment the use_count in parallel
                return result[0][0]
        except Exception as e:
            print(f"Error getting tag: {e}")  # Handle potential errors
        return None

    async def create_tag(self, guild_id, name, content):
        """Creates a new tag."""
        await self.run_query(
            """
            INSERT INTO tags (guild_id, name, content)
            VALUES (?, ?, ?)
            """,
            (guild_id, name, content),
        )

    async def edit_tag(self, guild_id, name, content):
        """Edits an existing tag."""
        await self.run_query(
            """
            UPDATE tags 
            SET content = ? 
            WHERE guild_id = ? AND name = ?
            """,
            (content, guild_id, name),
        )

    async def remove_tag(self, guild_id, name):
        """Deletes a tag."""
        await self.run_query(
            """
            DELETE FROM tags 
            WHERE guild_id = ? AND name = ?
            """,
            (guild_id, name),
        )

    async def get_all_tags(self, guild_id):
        """Retrieves all tag names in a guild."""
        result = await self.run_query(
            """
            SELECT name FROM tags
            WHERE guild_id = ?
            """,
            (guild_id,),
            fetch=True,
        )
        if result:
            return [row[0] for row in result]
        return []


async def setup(bot):
    await bot.add_cog(Database(bot))
