// Fix timestamp handling in playback function
function playTTS(id, channel, timestamp) {
    // Correctly format the audio URL using the timestamp straight from the database
    // The timestamp should now match the file format (YYYYMMDD-HHMMSS)
    const audioFile = `${channel}-${timestamp}.wav`;
    const audioPath = `/static/outputs/${channel}/${audioFile}`;
    
    console.log(`Playing audio: ${audioPath}`);
    
    // Create or get audio player
    let player = document.getElementById('audio-player');
    if (!player) {
        player = document.createElement('audio');
        player.id = 'audio-player';
        player.controls = true;
        document.body.appendChild(player);
    }
    
    // Set source and play
    player.src = audioPath;
    player.play().catch(e => {
        console.error(`Error playing audio: ${e}`);
        alert(`Could not play audio: ${e}`);
    });
} 