// bot.js
const tmi = require('tmi.js');
const { spawn } = require('child_process');

const client = new tmi.Client({
    options: { debug: true },
    connection: {
        secure: true,
        reconnect: true
    },
    identity: {
        username: 'anormalskipviewer',
        password: 'oauth:syo8d41n5fh6dxq7v6grt1uacii754'
    },
    channels: [ 'firestarman' ]
});


client.connect();

client.on('message', (channel, tags, message, self) => {
    if(self) return;

    if(message.toLowerCase() === '!markov') {
        const python = spawn('python', ['markov.py']);
        let dataToSend;

        python.stdout.on('data', (data) => {
            dataToSend = data.toString();
        });

        python.on('close', (code) => {
            client.say(channel, `@${tags.username}, ${dataToSend}`);
        });
    }
});