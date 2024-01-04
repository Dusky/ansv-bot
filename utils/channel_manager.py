import json

class ChannelManager:
    def __init__(self, channels):
        try:
            with open('markov_enabled.json', 'r') as f:
                self.markov_enabled = json.load(f)
        except FileNotFoundError:
            self.markov_enabled = {channel: True for channel in channels}

    def toggle_markov(self, channel):
        if channel in self.markov_enabled:
            self.markov_enabled[channel] = not self.markov_enabled[channel]
            status = "enabled" if self.markov_enabled[channel] else "disabled"
            
            # Save the updated markov_enabled dictionary to the JSON file
            with open('markov_enabled.json', 'w') as f:
                json.dump(self.markov_enabled, f)
            return f"Brain has been {status} for channel {channel}."
        else:
            return f"Channel {channel} not found."

    def is_markov_enabled(self, channel):
        return self.markov_enabled.get(channel, False)