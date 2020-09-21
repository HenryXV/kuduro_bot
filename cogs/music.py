import discord
import youtube_dl
from discord.ext import commands

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='play', help="Toca o aúdio de vídeos do youtube no canal de voz que o usuário está")
    async def play(self, ctx, url):

        ydl_opts = {'format': 'bestaudio', 'noplaylist':'True'}
        FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
        channel = ctx.message.author.voice.channel
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if not channel:
            await ctx.send('Você não está conectado a nenhum canal de voz!')
        else:
            if voice and voice.is_connected():
                await voice.move_to(channel)
            else:
                voice = await channel.connect()

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        URL = info['formats'][0]['url']
        voice.play(discord.FFmpegPCMAudio(URL, **FFMPEG_OPTIONS))
        voice.is_playing()

        await ctx.send('Tocando: {}'.format(info['title']))

def setup(bot):
    bot.add_cog(Music(bot))
