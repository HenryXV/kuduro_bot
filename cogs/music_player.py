import discord
from discord.ext import commands

import asyncio
import itertools
import sys
import traceback
from pqdict import pqdict
from ytdlsource import YTDLSource
from async_timeout import timeout
from functools import partial
from youtube_dl import YoutubeDL

class MusicPlayer():

    __slots__ = ('bot', '_guild', '_channel', '_cog', 'pq', 'next_song', 'value', 'source', 'current', 'np', 'volume')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.pq = pqdict()
        self.next_song = asyncio.Event()

        self.value = -1
        self.source = None
        self.np = None  # Now playing message
        self.volume = .5
        self.current = None

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next_song.clear()

            try:
                if len(self.pq) == 0:
                    await asyncio.sleep(5)
                    source = self.pq.pop()
                else:
                    source = self.pq.pop()
            except KeyError:
                await self._channel.send('Não há nenhum aúdio na fila, então vou me desconectar. Use o comando !play para tocar mais músicas', delete_after=15)
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                # So we should regather to prevent stream expiration
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.bot.loop)
                except Exception as e:
                    await self._channel.send(f'There was an error processing your song.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next_song.set))
            self.np = await self._channel.send('Tocando agora: {a} - Pedido por: <@{b}>'.format(a=source.title, b=source.requester.id))

            for k,v in self.pq.items():
                if v > 1:
                    self.pq.updateitem(k, v-1)

            if self.value > 1:
                self.value = self.value - 1
            print(self.value)
            print(self.pq)

            await self.next_song.wait()

            source.cleanup()
            self.current = None

            try:
                # We are no longer playing this song...
                await self.np.delete()
            except discord.HTTPException:
                pass

    def check(self):
        return len(self.pq) > 0

    def destroy(self, guild):
        return self.bot.loop.create_task(self._cog.cleanup(guild))
