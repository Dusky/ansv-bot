from transformers import AutoProcessor, BarkModel, set_seed
import torch
import accelerate
import scipy.io.wavfile
import random
import time
import os
import argparse
import warnings
from datetime import datetime
import re


# Set up argument parser
parser = argparse.ArgumentParser(description="Run the text-to-speech model.")
parser.add_argument('-debug', action='store_true', help='Enable debug mode to display all warnings.')
parser.add_argument('-text', type=str, required=True, help='Input text to convert to speech')
parser.add_argument('-voice', type=str, default='v2/en_speaker_5', help='Specify the voice preset (0-9) or a random choice with "R"')
parser.add_argument('-o', '--output', type=str, help='Specify the output directory for the .wav file')
args = parser.parse_args()
# Configure warning filters
if not args.debug:
    # Hide all PyTorch and BetterTransformer warnings unless in debug mode
    warnings.filterwarnings("ignore", category=UserWarning)
    #adjust the category or module depending

input_text = args.text

# Determine voice preset with validation
valid_voices = [str(i) for i in range(10)] + ['R', 'r']
if args.voice not in valid_voices:
    print(f"Invalid voice preset '{args.voice}'. Defaulting to 'v2/en_speaker_5'.")
    voice_preset = 'v2/en_speaker_5'
elif args.voice.isdigit():
    voice_preset = f"v2/en_speaker_{args.voice}"
elif args.voice in ['R', 'r']:
    voice_preset = f"v2/en_speaker_{random.randint(0, 9)}"

# Verbose Output Control - Set to False to reduce output, True for detailed output
verbose = True

def print_verbose(message):
    """Prints message only if verbose mode is enabled."""
    if verbose:
        print(message)

# Directories for resources and output
base_directory = "wordlists"  # Change this to your word lists directory, filename defined later
save_directory = "outputs"  # Directory where the .wav files will be saved

# Function to validate and return a random word from a file
def get_valid_word(file_path):
    """Fetches a random valid word from the specified file for use in filenames."""
    valid_word = None
    try:
        with open(file_path, 'r') as file:
            words = file.read().splitlines()
        while not valid_word:
            word = random.choice(words)
            if re.match("^[a-zA-Z0-9_-]*$", word) and len(word) < 255:
                valid_word = word
    except Exception as e:
        print_verbose(f"Error reading from {file_path}: {e}")
    return valid_word

# Ensure the output directory exists
save_directory = args.output if args.output else "outputs"  # Use the provided directory or default to "outputs"

try:
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)
except Exception as e:
    print_verbose(f"Error creating directory {save_directory}: {e}")
    exit()

# Start the timer
start_time = time.time()

try:
    # Setting up the device for PyTorch
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Initializing processor and model with the given model name
    processor = AutoProcessor.from_pretrained("suno/bark-small")
    model = BarkModel.from_pretrained("suno/bark-small").to(device)
    model = model.to_bettertransformer()  # Enhancing performance with BetterTransformer

    # Enable CPU offloading if necessary (for saving memory)
    model.enable_cpu_offload()

   # Manually set voice preset
   # voice_preset = "v2/en_speaker_5"

    # Processing input text through the model to generate audio
    inputs = processor(input_text, voice_preset=voice_preset).to(device)
    audio_array = model.generate(**inputs)
    audio_array = audio_array.cpu().numpy().squeeze()  # Moving the generated array to CPU and formatting

    # Getting sample rate from the model's configuration
    sample_rate = model.generation_config.sample_rate

    # Calculating audio length in seconds
    audio_length = len(audio_array) / sample_rate

    # Generating a filename from two random valid words from the word lists
    word1 = get_valid_word(os.path.join(base_directory, 'Wordlist_A.txt'))
    word2 = get_valid_word(os.path.join(base_directory, 'Wordlist_B.txt'))
    if word1 is None or word2 is None:
        raise ValueError("Invalid filename generated from word lists.")
    filename = f"{word1}-{word2}.wav"

    # Full path for the file to be saved
    full_path = os.path.join(save_directory, filename)

    # Saving the audio file in the specified format and path
    scipy.io.wavfile.write(full_path, rate=sample_rate, data=audio_array)
except Exception as e:
    print_verbose(f"An error occurred during processing: {e}")
    exit()

# End the timer
end_time = time.time()

# Calculating and printing the execution details
duration = end_time - start_time
completion_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print_verbose(f"- Execution Time: {duration:.2f} seconds")
print_verbose(f"- Completion Time: {completion_time}")
print_verbose(f"- File Name: {full_path}")
print_verbose(f"- Audio Length: {audio_length:.2f} seconds")
print_verbose(f"- Voice: {voice_preset}")

# Clearing PyTorch CUDA cache after heavy operations to release memory
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    print_verbose("Cleared CUDA cache.")
