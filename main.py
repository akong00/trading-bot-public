from config import *
bot = __import__('bots.{}'.format(BOT_TYPE)).__dict__[BOT_TYPE]

bot.run_bot()