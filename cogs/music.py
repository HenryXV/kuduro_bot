import discord
from discord.ext import commands

import asyncio
import itertools
import sys
import traceback
from cogs.music_player import MusicPlayer
from ytdlsource import YTDLSource
from async_timeout import timeout
from functools import partial
from youtube_dl import YoutubeDL

class Music(commands.Cog):

    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
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

    @commands.command(name='join', help='Conecta o bot no canal de voz que você está')
    async def join(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            await ctx.send('Você não está conectado a nenhum canal de voz', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()

    @commands.command(name='play', help='Toca o aúdio de vídeos do youtube no canal de voz que o usuário está', aliases=['p'])
    async def play_(self, ctx, *, search: str):

        await ctx.trigger_typing()

        await Music.join(self, ctx)

        player = self.get_player(ctx)

        # If download is True, source will be a discord.FFmpegPCMAudio with a VolumeTransformer.
        source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop, download=True)

        player.title.append(source.title)
        print(player.title)

        await player.songs.put(source)

    @commands.command(name='pula', help='Pula para a próxima música na fila')
    async def skip_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('Você não está conectado a nenhum canal de voz', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_playing():
            voice.stop()
            await ctx.send('A música foi pulada', delete_after=10)
        else:
            await ctx.send('Não há nenhum aúdio na fila', delete_after=10)

    @commands.command(name='pause', help='Pausa o aúdio sendo tocado no momento')
    async def pause(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('Você não está conectado a nenhum canal de voz', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_playing():
            voice.pause()
            await ctx.send('O aúdio foi pausado')
        elif voice.is_paused():
            await ctx.send('O aúdio já está pausado', delete_after=10)
        else:
            await ctx.send('Não há nenhum aúdio tocando', delete_after=10)

    @commands.command(name='resume', help='Resume o aúdio sendo tocado no momento')
    async def resume(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('Você não está conectado a nenhum canal de voz', delete_after=10)

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_paused():
            voice.resume()
            await ctx.send('O aúdio foi retomado', delete_after=10)
        elif voice.is_playing():
            await ctx.send('O aúdio não está pausado', delete_after=10)
        else:
            await ctx.send('Não há nenhum aúdio tocando', delete_after=10)

    @commands.command(name='fila', help='Mostra as músicas que estão na fila', aliases=['f', 'playlist'])
    async def queue_info_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('Você não está conectado a nenhum canal de voz', delete_after=10)

        player = self.get_player(ctx)
        if player.songs.empty():
            return await ctx.send('Não há nenhuma música na fila', delete_after=20)

        upcoming = list(itertools.islice(player.title, 1, 11))

        fmt = '\n'.join([f'{i+1} - {item}' for i, item in enumerate(upcoming)])

        embed = discord.Embed(title=f'Próximas {len(upcoming)} músicas', description=fmt)

        await ctx.send(embed=embed)

    @commands.command(name='tocando_agora', help='Mostra a música tocando no momento', aliases=['ta', 'atual', 'audioatual', 'tocando'])
    async def now_playing_(self, ctx):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('Você não está conectado a nenhum canal de voz', delete_after=10)

        voice_channel = ctx.voice_client

        player = self.get_player(ctx)
        if not player.current:
            return await ctx.send('Eu não estou tocando nada no momento')

        try:
            # Remove our previous now_playing message.
            await player.np.delete()
        except discord.HTTPException:
            pass

        player.np = await ctx.send('Tocando agora: {}'.format(voice_channel.source.title))

    @commands.command(name='volume', help='Muda o volume da música de valores entre 1 e 100', aliases=['vol'])
    async def change_volume_(self, ctx, *, vol: float):

        try:
            channel = ctx.message.author.voice.channel
        except:
            return await ctx.send('Você não está conectado a nenhum canal de voz', delete_after=10)

        voice_channel = ctx.voice_client

        if not 0 < vol < 101:
            return await ctx.send('Por favor, coloque um número entre 0 e 100')

        player = self.get_player(ctx)

        if voice_channel.source:
            voice_channel.source.volume = vol / 100

        player.volume = vol / 100

        await ctx.send(f'O volume foi alterado para **{vol}%**')

    @commands.command(name='stop', help='ATENÇÃO!! Para a música atual e destroí toda playlist e configurações')
    async def stop_(self, ctx):

        await self.cleanup(ctx.guild)

def setup(bot):
    bot.add_cog(Music(bot))
