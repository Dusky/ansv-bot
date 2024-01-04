import markovify
import configparser
from twitchio.ext import commands
YELLOW = "\x1b[33m" #xterm colors. dunno why tbh
RESET = "\x1b[0m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
PURPLE = "\x1b[35m"

async def ansv_command(self, ctx, setting, new_value=None):
    if ctx.author.name not in self.trusted_users:
        self.my_logger.log_warning(f"Unauthorized attempt to use ansv command by {ctx.author.name}")
        return

    if setting == "speak":
        # Check if Markov chain is enabled for this channel
        if not self.channel_manager.is_markov_enabled(ctx.channel.name):
            #await ctx.send("Markov chain outputs are disabled for this channel.")
            return

        user_color_index = self.color_manager.get_user_color(ctx.author.name)
        colored_username = f"\x1b[38;5;{user_color_index}m{ctx.author.name}\x1b[0m"
        
        channel_color_index = self.color_manager.get_channel_color(ctx.channel.name)
        colored_channel_name = f"\x1b[38;5;{channel_color_index}m{ctx.channel.name}\x1b[0m"

        #self.my_logger.log_info(f"{GREEN}{colored_username} used !ansv speak in {colored_channel_name}, generating a message for them!{RESET}")
        response = self.model.make_sentence()
        try:
            await ctx.send(response)
            self.my_logger.log_message(ctx.channel.name, self.nick, response)
        except Exception as e:
            self.my_logger.log_error(f"{RED}Failed to send message due to: {e}{RESET}")

    if setting == "start":
        if not self.channel_manager.is_markov_enabled(ctx.channel.name):
            message = self.channel_manager.toggle_markov(ctx.channel.name)
            await ctx.send(message)
        else:
            await ctx.send("Markov chain is already enabled.")

    elif setting == "stop":
        if self.channel_manager.is_markov_enabled(ctx.channel.name):
            message = self.channel_manager.toggle_markov(ctx.channel.name)
            await ctx.send(message)
        else:
            await ctx.send("Markov chain is already disabled.")
        
    elif setting in ["time", "lines"]:
        config = configparser.ConfigParser()
        config.read("settings.conf")
        config.set("settings", setting + "_between_messages", new_value)
        with open("settings.conf", "w") as f:
            config.write(f)
        self.reload_settings()
        await ctx.send(f"Set {setting}_between_messages to {new_value}")
        self.my_logger.info(f"{ctx.author.name} set {setting}_between_messages to {new_value}")

    elif setting == "trust":
        self.trusted_users.append(new_value)
        config = configparser.ConfigParser()
        config.read("settings.conf")
        config.set("settings", "trusted_users", ",".join(self.trusted_users))
        with open("settings.conf", "w") as f:
            config.write(f)

    elif setting == "reload":
        print("Reload Brain Received")  # Debug print
        self.text = self.load_text()

        # Check if text is empty
        if not self.text:
            await ctx.send("No text data available.")
            return
        self.text_model = markovify.Text(self.text)

        await ctx.send("Brain reloaded.")

    elif setting == "join":
        if ctx.author.name != self.owner:
            self.my_logger.print_message(f"Unauthorized attempt to use join command by {ctx.author.name}")
            return
        if new_value not in self.channels:  # check if channel is not already present
            self.channels.append(new_value)
            config = configparser.ConfigParser()
            config.read("settings.conf")
            config.set("settings", "channels", ",".join(self.channels))
            with open("settings.conf", "w") as f:
                config.write(f)
            self.reload_settings()
            await ctx.send(f"Added {new_value} to channels.")
        else:
            await ctx.send(f"{new_value} is already in channels.")
        colored_channels = [f"\x1b[38;5;{self.color_manager.get_channel_color(channel)}m#{channel}\x1b[0m" for channel in self.channels]
        self.my_logger.print_message(f"{YELLOW}Current channels: {', '.join(colored_channels)}{RESET}")  # print to console

    elif setting == "part":
        if ctx.author.name != self.owner:
            self.my_logger.log_warning(f"Unauthorized attempt to use part command by {ctx.author.name}")
            return
        if new_value in self.channels:  # check if channel is already present
            self.channels.remove(new_value)
            config = configparser.ConfigParser()
            config.read("settings.conf")
            config.set("settings", "channels", ",".join(self.channels))
            with open("settings.conf", "w") as f:
                config.write(f)
            self.reload_settings()
            await ctx.send(f"Removed {new_value} from channels.")
        else:
            await ctx.send(f"{new_value} is not in channels.")
        colored_channels = [f"\x1b[38;5;{self.color_manager.get_channel_color(channel)}m#{channel}\x1b[0m" for channel in self.channels]
        self.my_logger.print_message(f"{YELLOW}Current channels: {', '.join(colored_channels)}{RESET}")  # print to console
    
    # Build the model
    self.text_model = markovify.Text(self.text)