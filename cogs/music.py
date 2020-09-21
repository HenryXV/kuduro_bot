import discord
import youtube_dl
from discord.ext import commands

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='play', help="Toca o aúdio de vídeos do youtube no canal de voz que o usuário está")
    async def play(self, ctx, url):
        ydl_opts = {
            'format': 'bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'song.%(ext)s',
        }

        channel = ctx.message.author.voice.channel
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if not channel:
            await ctx.send('Você não está conectado a nenhum canal de voz')
        else:
            if voice and voice.is_connected():
                await voice.move_to(channel)
            else:
                voice = await channel.connect()

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        if not voice.is_playing():
            voice.play(discord.FFmpegPCMAudio("song.mp3"))
            voice.is_playing()
            await ctx.send('Tocando: {}'.format(info['title']))
        else:
            await ctx.send('Um aúdio já está sendo executado')
            return

    @commands.command(name="stop", help="Interrompe o aúdio sendo executado no momento")
    async def stop(self, ctx):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_playing():
            voice.stop()
            await ctx.send('O aúdio foi interrompido')
        else:
            await ctx.send('Não há nenhum aúdio tocando')

    @commands.command(name="pause", help="Pausa o aúdio sendo tocado no momento")
    async def pause(self, ctx):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_playing():
            voice.pause()
            await ctx.send('O aúdio foi pausado')
        elif voice.is_paused():
            await ctx.send('O aúdio já está pausado')
        else:
            await ctx.send('Não há nenhum aúdio tocando')

    @commands.command(name="resume", help="Resume o aúdio sendo tocado no momento")
    async def resume(self, ctx):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice.is_paused():
            voice.resume()
            await ctx.send('O aúdio foi retomado')
        elif voice.is_playing():
            await ctx.send('O aúdio não está pausado')
        else:
            await ctx.send('Não há nenhum aúdio tocando')

def setup(bot):
    bot.add_cog(Music(bot))
