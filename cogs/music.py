import discord
from discord.ext import commands

import asyncio
import itertools
import sys
import traceback
import random
import cogs.database as db
from pqdict import nsmallest
from cogs.music_player import MusicPlayer
from ytdlsource import YTDLSource
from async_timeout import timeout
from functools import partial
from youtube_dl import YoutubeDL

class Music(commands.Cog):

    __slots__ = ('bot', 'players', 'databases')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.databases = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
            del self.databases[guild.id]
        except KeyError:
            pass

    async def __local_check(self, ctx):
        # A local check which applies to all commands in this cog.
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    async def __error(self, ctx, error):
        # A local error handler for all errors arising from commands in this cog.
        if isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.send('This command can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, InvalidVoiceChannel):
            await ctx.send('Error connecting to Voice Channel. '
                           'Please make sure you are in a valid channel or provide me with one')

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    def get_player(self, ctx):
    # Retrieve the guild player, or generate one.
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    def get_database(self, ctx):
        try:
            database = self.databases[ctx.guild.id]
        except KeyError:
            database = db.Database(ctx)
            self.databases[ctx.guild.id] = database
            db.session.execute(db.Database.insert_pref(self, db.Guild.__table__), {'id': database._guild.id, 'name': database._guild.name})
            for track in db.session.query(db.Track).filter_by(guild_id=database._guild.id):
                db.session.delete(track)

        return database

    async def is_empty(self, ctx):

        player = self.get_player(ctx)

        while True:

            await asyncio.sleep(3)

            if len(player.pq) == 0 and player.loop_queue == True:
                await self.loop_queue_(ctx)
            elif player.loop_queue == False: break
            else: continue

    @commands.command(name='join', help='Connects the bot to your current channel')
    async def join(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()

    @commands.max_concurrency(1, wait=True)
    @commands.command(name='play', help='Connects to your channel and play an audio from youtube [search or url]', aliases=['p'])
    async def play_(self, ctx, *, search: str):

        await ctx.trigger_typing()

        await Music.join(self, ctx)

        player = self.get_player(ctx)
        player.wait = True

        database = self.get_database(ctx)

        # If download is True, source will be a discord.FFmpegPCMAudio with a VolumeTransformer.
        source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=True)

        for t in player.pq.items():
            if source.title == t[0].title:
                return await ctx.send('The audio is already on the queue')
            else: continue

        player.value = player.value + 1
        player.pq.additem(source, player.value)

        db.session.execute(db.Database.insert_pref(self, db.Track.__table__), {'index': player.value, 'web_url': source.web_url, 'title': source.title,
        'duration': source.duration, 'guild_id': database._guild.id})

        db.session.commit()

        await ctx.message.add_reaction('✅')
        await ctx.send(f'```ini\n[Added {source.title} to the Queue]\n```', delete_after=30)

        player.wait = False

    @commands.max_concurrency(1, wait=True)
    @commands.command(name='next', help='Skips to the next song on the queue')
    async def skip_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        # if voice.is_playing() and len(player.pq) > 0:
        voice.stop()
        await ctx.message.add_reaction('⏭️')
        # else:
        #     await ctx.send('There is no audio on the queue', delete_after=10)

    @commands.command(name='pause', help='Pauses the audio currently being played')
    async def pause(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_playing():
            voice.pause()
            await ctx.message.add_reaction('⏸️')
        elif voice.is_paused():
            await ctx.send('The audio is already paused', delete_after=10)
        else:
            await ctx.send('There is no audio playing right now', delete_after=10)

    @commands.command(name='resume', help='Resumes the audio currently playing')
    async def resume(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_paused():
            voice.resume()
            await ctx.message.add_reaction('✅')
        elif voice.is_playing():
            await ctx.send('The audio is already playing', delete_after=10)
        else:
            await ctx.send('There is no audio being played right now', delete_after=10)

    @commands.command(name='queue', help='Show the audios currently queued', aliases=['q', 'playlist'])
    async def queue_info_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        queue = [(index, title) for index, title in db.session.query(db.Track.index, db.Track.title).filter(db.Track.guild_id==database._guild.id).order_by(db.Track.index)]

        if len(queue) == 0:
            return await ctx.send('There is no audio on the queue. Use the command !play or !p to queue audios', delete_after=20)

        fmt = '\n'.join([f'{track[0]} - {track[1]}' for track in queue])

        embed = discord.Embed(title=f'Your queue', description=fmt)

        await ctx.send(embed=embed)

    @commands.command(name='playing_now', help='Shows the current audio playing', aliases=['pn', 'now', 'currentaudio', 'playing'])
    async def now_playing_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice_channel = ctx.voice_client

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('I am not playing anything right now. Use the command !play or !p to add audios to the queue')

        try:
            # Remove our previous now_playing message.
            await player.np.delete()
        except discord.HTTPException:
            pass

        player.np = await ctx.send('Playing: {a} - Requested by: <@{b}>'.format(a=voice_channel.source.title, b=voice_channel.source.requester.author.id))

    @commands.command(name='volume', help='Changes the volume between 1 and 100', aliases=['vol'])
    async def change_volume_(self, ctx, *, vol: float):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice_channel = ctx.voice_client

        if not 0 < vol < 101:
            return await ctx.send('Please, use number only between 1 and 100')

        player = self.get_player(ctx)

        if voice_channel.source:
            voice_channel.source.volume = vol / 100

        player.volume = vol / 100

        await ctx.send(f'The volume is now on **{vol}%**')

    @commands.command(name='stop', help='ATTENTION!!! This command will destroy your playlist and all changes made')
    async def stop_(self, ctx):

        player = self.get_player(ctx)
        player.loop_queue = False

        await self.cleanup(ctx.guild)

        await ctx.message.add_reaction('⏹️')

    @commands.command(name='remove', help='[track position] Deletes the audio specified by the user', aliases=['re'])
    async def remove_(self, ctx, *, delete):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        try:
            to_delete = database.search(delete)
            title = to_delete.title
            index = to_delete.index

            try:
                title_to_del = [k for k,v in player.pq.items() if k.title == title]
                del player.pq[title_to_del[0]]
            except IndexError:
                pass

            db.session.delete(to_delete)
            database.update_index(index)

            await ctx.send('The audio {} was removed from the queue'.format(title))

            db.session.commit()
        except AttributeError:
            return await ctx.send('The audio is not on the queue', delete_after=10)

        await ctx.message.add_reaction('❌')

        if player.value > 0:
            player.value = player.value - 1

    @commands.command(name='clear', help='Deletes all audios from the queue')
    async def clear_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        player.pq.clear()
        database.clean_database()

        player.value = 0

        await ctx.send('All audios have been removed', delete_after=5)

    @commands.command(name='jump', help='[track position] Skips to the specified audio', aliases=['j'])
    async def jump_(self, ctx, *, jump):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        try:
            to_jump = database.search(jump)
            title = to_jump.title
            index = to_jump.index

            print(title, index)

            audio = [k for k,v in player.pq.items() if k.title == title]

            if len(audio) == 0:
                if player.loop_queue == True:
                    player.loop_queue = False
                player.pq.clear()
                await ctx.send('Going back in time...', delete_after = 15)
                for track in db.session.query(db.Track).filter(db.Track.index >= index, db.Track.guild_id == database._guild.id):
                    source = await YTDLSource.create_source(ctx, track.title, loop=self.bot.loop, download=True)
                    if source.title == title:
                        player.pq.additem(source, track.index)
                        await Music.skip_(self, ctx)
                    else:
                        player.pq.additem(source, track.index)
                player.loop_queue = True
            else:
                database.sync_pq(ctx)
                keys = [k for k,v in player.pq.items() if v < index]
                for key in keys:
                    del player.pq[key]

                await Music.skip_(self, ctx)

        except AttributeError:
            return await ctx.send('The audio specified is not on the queue')

    @commands.command(name='shuffle', help='Randomizes all audios in the queue')
    async def shuffle_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('You are not connected to any voice channel', delete_after=10)

        voice_channel = ctx.voice_client

        player = self.get_player(ctx)
        database = self.get_database(ctx)

        database.shuffle(ctx)

        await ctx.message.add_reaction('🔀')

    @commands.after_invoke(is_empty)
    @commands.command(name='loop_queue', help="Loops through the queue")
    async def loop_queue_true(self, ctx):
            player = self.get_player(ctx)

            if player.loop_queue == False:
                player.loop_queue = True
                return await ctx.send('The queue will loop when it ends')
            else:
                return await ctx.send('The queue is already looping')

    async def loop_queue_(self, ctx):

            player = self.get_player(ctx)
            player.wait = True

            database = self.get_database(ctx)

            for track in db.session.query(db.Track).filter(db.Track.guild_id == database._guild.id):
                source = await YTDLSource.create_source(ctx, track.title, loop=self.bot.loop, download=True)
                player.pq.additem(source, track.index)

            player.wait = False

def setup(bot):
    bot.add_cog(Music(bot))
