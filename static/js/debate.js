document.addEventListener('DOMContentLoaded', () => {
    const diceButton = document.getElementById('dice-button');
    const topicDisplay = document.getElementById('topic-display');
    const acceptTopicButton = document.getElementById('accept-topic');
    const startButton = document.getElementById('start-debate');
    const roundsInput = document.getElementById('rounds-input');
    const debateLog = document.querySelector('.debate-log');
    const sendButton = document.getElementById('send-button');
    const userInput = document.getElementById('debate-input');
    const micButton = document.getElementById('voice-button');
    const micIcon = document.getElementById('mic-icon');
    const micStatus = document.getElementById('mic-status');
    const turnIndicator = document.getElementById('turn-indicator');
    let currentTopic = null;
    let timeLeft = 30;
    let timerInterval = null;
    let isUserTurn = true;
    let exchangeCount = 0;
    let currentRound = 1; // Track the current round
    let totalRounds = 3;
    let recognition = null;
    let isListening = false;
    let timePerTurn = 30;
    let secondsLeft = 30;
    let difficulty = 'Intermediate';
    let debateStyle = 'Formal';
    let dialogues = []; // Store debate dialogues for Judgement Bot
    let wins = 0;
    let losses = 0;
    let totalPoints = 0;

    // Speech Recognition Setup
    try {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            userInput.value = transcript;
            micStatus.textContent = 'Microphone status: Success';
            micStatus.className = 'text-sm text-green-600 mt-2';
            micIcon.className = 'ri-mic-line text-green-600';
        };

        recognition.onerror = (event) => {
            micStatus.textContent = `Microphone status: Error - ${event.error}`;
            micStatus.className = 'text-sm text-red-600 mt-2';
            micIcon.className = 'ri-mic-off-line text-red-600';
            if (event.error === 'not-allowed') {
                alert('Microphone access was denied. Please enable microphone permissions in your browser settings.');
            }
        };

        recognition.onend = () => {
            if (micIcon.className.includes('text-blue-600')) {
                micIcon.className = 'ri-mic-line text-gray-600';
            }
            isListening = false;
        };
    } catch (e) {
        console.error('Speech recognition not supported', e);
        micButton.disabled = true;
        micStatus.textContent = 'Microphone status: Not supported';
        micStatus.className = 'text-sm text-red-600 mt-2';
        micIcon.className = 'ri-mic-off-line text-red-600';
    }

// Voice Button Handler
micButton.addEventListener('click', () => {
    if (!isUserTurn) {
        alert("Please wait for your turn to speak.");
        return;
    }

    // Stop any ongoing AI speech
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }

    // Rest of your existing microphone code...
    try {
        if (isListening) {
            // Stop recording
            recognition.stop();
            micStatus.textContent = 'Microphone status: Ready';
            micStatus.className = 'text-sm text-green-600 mt-2';
            micIcon.className = 'ri-mic-line text-green-600';
            isListening = false;
        } else {
            // Start recording
            micStatus.style.display = 'block';
            micStatus.textContent = 'Microphone status: Listening...';
            micIcon.className = 'ri-mic-line text-blue-600';
            recognition.start();
            isListening = true;
        }
    } catch (error) {
        micStatus.textContent = `Microphone status: Error - ${error.message}`;
        micStatus.className = 'text-sm text-red-600 mt-2';
        micIcon.className = 'ri-mic-off-line text-red-600';
        console.error('Speech recognition error:', error);
    }
});

    // Enhanced Send Button Handler
    function sendMessage() {
        if (!isUserTurn) {
            alert("Please wait for your turn to respond.");
            return;
        }

        const userText = userInput.value.trim();
        if (!userText) {
            alert("Please enter your argument before sending.");
            return;
        }

        // Disable input during processing
        userInput.disabled = true;
        sendButton.disabled = true;
        micButton.disabled = true;

        appendMessage('You', userText);
        dialogues.push({'speaker': 'You', 'text': userText, 'time': new Date().toLocaleTimeString()});
        exchangeCount++;
        clearInterval(timerInterval);
        document.querySelector('.timer').textContent = 'Turn Complete';
        if (turnIndicator) turnIndicator.style.display = 'none';

        // Move fetch here so it only runs when sendMessage is called
        fetch('/debate/generate_ai_response', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_input: userText })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }

            if (data.complex_words && data.complex_words.length > 0) {
                // Process the response to highlight complex words
                let processedResponse = data.response;
                data.complex_words.forEach(wordInfo => {
                    const regex = new RegExp(`\\b${wordInfo.word}\\b`, 'gi');
                    processedResponse = processedResponse.replace(regex, 
                        `<span class="complex-word underline decoration-wavy decoration-blue-500 cursor-help" title="${wordInfo.definition}">${wordInfo.word}</span>`);
                });
                appendMessage('AI Opponent', processedResponse);
            } else {
                appendMessage('AI Opponent', data.response);
            }
            dialogues.push({'speaker': 'AI Opponent', 'text': data.response, 'time': new Date().toLocaleTimeString()});
            exchangeCount++;

            // Speak the AI response
            if (data.response && window.speechSynthesis) {
                const utterance = new SpeechSynthesisUtterance(data.response);
                utterance.rate = 0.9;
                utterance.pitch = 1.0;
                
                // Only enable user input after AI finishes speaking
                userInput.disabled = true;
                sendButton.disabled = true;
                micButton.disabled = true;
                
                utterance.onend = function() {
                    if (data.analysis) {
                        // Round completed
                        showFeedback(data.analysis);
                        if (data.analysis.winner === 'You') {
                            wins++;
                            totalPoints += data.analysis.score;
                        } else {
                            losses++;
                            totalPoints += Math.floor(data.analysis.score / 2); // Give some points even if lost
                        }
                        // Update profile stats
                        updateProfileStats({
                            wins: wins,
                            losses: losses,
                            totalPoints: totalPoints,
                            strengths: data.analysis.strengths,
                            weaknesses: data.analysis.weaknesses,
                            score: data.analysis.score
                        });
                        if (data.end) {
                            // Debate completed
                            appendMessage('System', 'Debate has ended!');
                            return;
                        }
                    }
                    // Enable user input for next turn
                    isUserTurn = true;
                    userInput.disabled = false;
                    sendButton.disabled = false;
                    micButton.disabled = false;
                    startTimer();
                    showTurnIndicator();
                };
                window.speechSynthesis.speak(utterance);
            } else {
                // If speech synthesis not available, proceed immediately
                if (data.analysis) {
                    showFeedback(data.analysis);
                }
                isUserTurn = true;
                userInput.disabled = false;
                sendButton.disabled = false;
                micButton.disabled = false;
                startTimer();
                showTurnIndicator();
            }
        });
    }

    // Event Listeners
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }
    });

    sendButton.addEventListener('click', (e) => {
        e.preventDefault();
        sendMessage();
    });

    diceButton.addEventListener('click', () => {
        diceButton.disabled = true;
        const dice = document.createElement('div');
        dice.className = 'dice-animation';
        document.body.appendChild(dice);

        setTimeout(() => {
            fetch('/debate/roll_dice', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    currentTopic = data.topic;
                    topicDisplay.textContent = `Topic: ${currentTopic}`;
                    acceptTopicButton.style.display = 'block';
                    document.body.removeChild(dice);
                    diceButton.disabled = false;
                });
        }, 1000);
    });

    acceptTopicButton.addEventListener('click', () => {
        const numRounds = roundsInput.value.trim();
        if (!numRounds || isNaN(numRounds) || numRounds < 1) {
            alert('Please enter a valid number of rounds (at least 1).');
            return;
        }

        totalRounds = parseInt(numRounds);
        diceButton.disabled = true;
        acceptTopicButton.style.display = 'none';
        startButton.disabled = false;
        startButton.className = 'bg-primary hover:bg-blue-700 text-white px-5 py-2 rounded-full whitespace-nowrap transition-colors';
        fetch('/debate/accept_topic', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic: currentTopic, num_rounds: numRounds })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                diceButton.disabled = false;
                acceptTopicButton.style.display = 'block';
                startButton.disabled = true;
                startButton.className = 'bg-gray-400 text-white px-5 py-2 rounded-full whitespace-nowrap transition-colors';
            }
        })
        .catch(error => {
            alert('An error occurred while accepting the topic. Please try again.');
            console.error('Error:', error);
        });
    });

    startButton.addEventListener('click', () => {
        const numRounds = roundsInput.value.trim();
        if (!currentTopic || !numRounds || isNaN(numRounds) || numRounds < 1) {
            alert('Please accept a topic and enter a valid number of rounds.');
            return;
        }

        const startAnimation = document.createElement('div');
        startAnimation.className = 'start-animation';
        startAnimation.textContent = 'Start!';
        document.body.appendChild(startAnimation);
        setTimeout(() => {
            document.body.removeChild(startAnimation);
            roundsInput.disabled = true;
            startButton.style.display = 'none';
            document.querySelector('.round-indicator').textContent = `Round 1/${totalRounds}`;
            appendMessage('AI Opponent', `Welcome to the debate! We're discussing "${currentTopic}". You can type or use the microphone to share your argument. Let's get started!`);
            startTimer();
            exchangeCount = 0;
            showTurnIndicator();
        }, 1500);
    });

    document.querySelectorAll('.debate-settings input').forEach(input => {
        input.addEventListener('change', () => {
            const difficultyMap = { '1': 'Beginner', '2': 'Intermediate', '3': 'Expert' };
            const styleInputs = document.querySelectorAll('.debate-style-option');
            let selectedStyle = 'Formal';
            styleInputs.forEach(option => {
                if (option.querySelector('.radio-dot').classList.contains('bg-primary')) {
                    selectedStyle = option.querySelector('span').textContent;
                }
            });
            const settings = {
                style: selectedStyle,
                difficulty: difficultyMap[document.querySelector('input[name="ai-difficulty"]').value],
                time_per_turn: document.querySelector('input[name="time-per-turn"]').value
            };
            fetch('/debate/set_debate_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            document.querySelector('.difficulty-value').textContent = settings.difficulty;
            const minutes = Math.floor(settings.time_per_turn / 60);
            document.querySelector('.time-value').textContent = `${minutes} minute${minutes > 1 ? 's' : ''}`;
            document.querySelector('.debate-style-indicator').textContent = `• Style: ${settings.style}`;
        });
    });

    document.querySelectorAll('.debate-style-option').forEach(option => {
        option.addEventListener('click', () => {
            document.querySelectorAll('.debate-style-option').forEach(opt => {
                opt.classList.remove('border-primary', 'bg-blue-50');
                opt.querySelector('.radio-dot').classList.remove('bg-primary');
            });
            option.classList.add('border-primary', 'bg-blue-50');
            option.querySelector('.radio-dot').classList.add('bg-primary');
            debateStyle = option.querySelector('span').textContent; // Update debateStyle for Judgement Bot
            const settings = {
                style: debateStyle,
                difficulty: document.querySelector('.difficulty-value').textContent,
                time_per_turn: document.querySelector('input[name="time-per-turn"]').value
            };
            fetch('/debate/set_debate_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            document.querySelector('.debate-style-indicator').textContent = `• Style: ${settings.style}`;
        });
    });

    function startTimer() {
        timeLeft = document.querySelector('input[name="time-per-turn"]').value;
        const timerDisplay = document.querySelector('.timer');
        const minutesLeft = Math.floor(timeLeft / 60);
        const secondsLeft = timeLeft % 60;
        timerDisplay.textContent = `${isUserTurn ? 'Your Turn' : 'AI Turn'} • ${minutesLeft > 0 ? minutesLeft + 'm ' : ''}${secondsLeft}s left`;

        if (isUserTurn) {
            userInput.disabled = false;
            sendButton.disabled = false;
            micButton.disabled = false;
        }

        timerInterval = setInterval(() => {
            timeLeft--;
            const minutesLeft2 = Math.floor(timeLeft / 60);
            const secondsLeft2 = timeLeft % 60;
            timerDisplay.textContent = `${isUserTurn ? 'Your Turn' : 'AI Turn'} • ${minutesLeft2 > 0 ? minutesLeft2 + 'm ' : ''}${secondsLeft2}s left`;

            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                timerDisplay.textContent = "Time's Up!";

                if (isUserTurn) {
                    userInput.disabled = true;
                    sendButton.disabled = true;
                    micButton.disabled = true;
                    micStatus.textContent = 'Microphone status: Turn ended';
                    micStatus.className = 'text-sm text-gray-600 mt-2';
                    micIcon.className = 'ri-mic-off-line text-gray-600';

                    if (userInput.value.trim()) {
                        sendMessage();
                    } else {
                        // User didn't input anything, proceed to AI turn
                        appendMessage('You', 'No input provided.');
                        dialogues.push({'speaker': 'You', 'text': 'No input provided.', 'time': new Date().toLocaleTimeString()});
                        exchangeCount++;
                        fetch('/debate/generate_ai_response', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ user_input: 'No input provided.' })
                        })
                        .then(response => response.json())
                        .then(data => {
                            appendMessage('AI Opponent', data.response);
                            dialogues.push({'speaker': 'AI Opponent', 'text': data.response, 'time': new Date().toLocaleTimeString()});
                            exchangeCount++;
                            const speakingTime = (data.response.split(' ').length / 2.5) * 1000;

                            if (data.end) {
                                appendMessage('System', 'Debate has ended!');
                                if (typeof window.analyzeDebate === 'function') {
                                    window.analyzeDebate(dialogues, currentTopic, debateStyle, currentRound, totalRounds);
                                }
                            } else if (data.round > currentRound) {
                                currentRound = data.round;
                                document.querySelector('.round-indicator').textContent = `Round ${data.round}/${totalRounds}`;
                                exchangeCount = 0;
                                dialogues = [];
                            }

                            setTimeout(() => {
                                isUserTurn = true;
                                userInput.disabled = false;
                                sendButton.disabled = false;
                                micButton.disabled = false;
                                startTimer();
                                showTurnIndicator();
                            }, speakingTime + 1000);
                        })
                        .catch(error => {
                            console.error('Error:', error);
                            alert(`An error occurred: ${error.message}`);
                            userInput.disabled = false;
                            sendButton.disabled = false;
                            micButton.disabled = false;
                            startTimer();
                        });
                    }
                }
            }
        }, 1000);
    }

    function showTurnIndicator() {
        if (isUserTurn && turnIndicator) {
            turnIndicator.style.display = 'block';
            setTimeout(() => {
                turnIndicator.style.display = 'none';
            }, 3000);
        }
    }

    function appendMessage(speaker, text) {
        const entry = document.createElement('div');
        entry.className = speaker === 'You' ? 'flex gap-3 flex-row-reverse' : 'flex gap-3';
        entry.innerHTML = `
            <div class="w-10 h-10 flex items-center justify-center ${speaker === 'You' ? 'bg-blue-100' : speaker === 'System' ? 'bg-yellow-100' : 'bg-gray-200'} rounded-full flex-shrink-0">
                <i class="${speaker === 'You' ? 'ri-user-line text-primary' : speaker === 'System' ? 'ri-error-warning-line text-yellow-600' : 'ri-robot-line text-gray-700'}"></i>
            </div>
            <div class="max-w-[80%]">
                <div class="flex items-center gap-2 mb-1 ${speaker === 'You' ? 'justify-end' : ''}">
                    <span class="font-medium">${speaker}</span>
                    <span class="text-xs text-gray-500">${new Date().toLocaleTimeString()}</span>
                </div>
                <div class="${speaker === 'You' ? 'bg-blue-100 user-message' : speaker === 'System' ? 'bg-yellow-100 system-message' : 'bg-gray-200 ai-message'} p-3">
                    <p>${text}</p>
                </div>
            </div>
        `;
        debateLog.appendChild(entry);
        debateLog.scrollTop = debateLog.scrollHeight;
    }

    function showFeedback(analysis) {
        const popup = document.createElement('div');
        popup.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        popup.innerHTML = `
            <div class="bg-white p-6 rounded-lg max-w-lg w-full">
                <h3 class="text-xl font-bold mb-4">${analysis.winner === 'You' ? 'Congratulations, You Won!' : 'Great Effort!'}</h3>
                <p><strong>Score:</strong> ${analysis.score}/100</p>
                <p><strong>Strengths:</strong> ${analysis.strengths}</p>
                <p><strong>Weaknesses:</strong> ${analysis.weaknesses}</p>
                <p><strong>Improvements:</strong> ${analysis.improvements}</p>
                <p><strong>Winner:</strong> ${analysis.winner}</p>
                <button class="mt-4 bg-primary hover:bg-blue-700 text-white px-5 py-3 rounded-full">Close</button>
            </div>
        `;
        document.body.appendChild(popup);
        popup.querySelector('button').addEventListener('click', () => {
            document.body.removeChild(popup);
            if (currentRound >= totalRounds) {
                // Reset for new debate
                diceButton.disabled = false;
                roundsInput.disabled = false;
                startButton.style.display = 'block';
                topicDisplay.textContent = '';
                exchangeCount = 0;
                currentRound = 1;
                dialogues = [];
            }
        });

        if (analysis.winner === 'You') {
            const canvas = document.createElement('canvas');
            canvas.className = 'fixed inset-0 pointer-events-none z-40';
            document.body.appendChild(canvas);
            const ctx = canvas.getContext('2d');
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const confetti = [];
            for (let i = 0; i < 100; i++) {
                confetti.push({
                    x: Math.random() * canvas.width,
                    y: Math.random() * -canvas.height,
                    speed: Math.random() * 5 + 2,
                    color: `hsl(${Math.random() * 360}, 100%, 50%)`
                });
            }
            function animateConfetti() {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                confetti.forEach(c => {
                    c.y += c.speed;
                    if (c.y > canvas.height) c.y = -20;
                    ctx.fillStyle = c.color;
                    ctx.fillRect(c.x, c.y, 10, 10);
                });
                if (document.body.contains(canvas)) {
                    requestAnimationFrame(animateConfetti);
                }
            }
            animateConfetti();
            setTimeout(() => {
                if (document.body.contains(canvas)) {
                    document.body.removeChild(canvas);
                }
            }, 5000);
        } else {
            const encourage = document.createElement('div');
            encourage.className = 'fixed inset-0 flex items-center justify-center z-40';
            encourage.innerHTML = `<div class="text-4xl font-bold text-primary animate-bounce">Keep Debating!</div>`;
            document.body.appendChild(encourage);
            setTimeout(() => {
                if (document.body.contains(encourage)) {
                    document.body.removeChild(encourage);
                }
            }, 3000);
        }
    }

    function updateProfileStats(stats) {
        const statsData = {
            total_debates: 1,  // Count this debate
            wins: stats.winner === 'You' ? 1 : 0,
            losses: stats.winner === 'AI Opponent' ? 1 : 0,
            total_points: stats.score,
            strengths: stats.strengths,
            weaknesses: stats.weaknesses
        };

        fetch('/api/update_debate_stats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(statsData)
        })
        .then(response => response.json())
        .then(data => {
            console.log('Profile stats updated:', data);
            // Update the UI immediately if the user is on the profile page
            if (window.location.pathname === '/profile') {
                updateProfileUI(statsData);
            }
        })
        .catch(error => {
            console.error('Error updating profile stats:', error);
        });
    }

    // Add this function to update the profile UI
    function updateProfileUI(stats) {
        const totalDebates = stats.total_debates || 0;
        const wins = stats.wins || 0;
        const losses = stats.losses || 0;
        const totalPoints = stats.total_points || 0;
        
        document.getElementById("totalDebates").textContent = totalDebates;
        document.getElementById("winsCount").textContent = wins;
        document.getElementById("lossesCount").textContent = losses;
        
        const winRate = totalDebates > 0 ? Math.round((wins / totalDebates) * 100) : 0;
        document.getElementById("winRate").textContent = `${winRate}%`;
        document.getElementById("totalPoints").textContent = totalPoints;
        
        if (stats.strengths) {
            document.getElementById("strengthsList").innerHTML = 
                `<ul class="list-disc pl-5">${stats.strengths.split('\n').map(s => `<li>${s}</li>`).join('')}</ul>`;
        }
        if (stats.weaknesses) {
            document.getElementById("weaknessesList").innerHTML = 
                `<ul class="list-disc pl-5">${stats.weaknesses.split('\n').map(w => `<li>${w}</li>`).join('')}</ul>`;
        }
    }

    // Check for microphone permissions
    navigator.permissions.query({ name: 'microphone' }).then(result => {
        if (result.state === 'granted') {
            micButton.title = 'Microphone access granted';
        } else if (result.state === 'prompt') {
            micButton.title = 'Click to allow microphone access';
        } else if (result.state === 'denied') {
            micButton.title = 'Microphone access denied. Check browser settings.';
            micButton.disabled = true;
            micIcon.className = 'ri-mic-off-line text-gray-400';
        }
    });

    const style = document.createElement('style');
    style.innerHTML = `
        .dice-animation {
            width: 50px;
            height: 50px;
            background: url('/static/images/dice.png') center/cover;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1000;
            animation: roll 1s ease-in-out;
        }
        @keyframes roll {
            0% { transform: translate(-50%, -50%) rotate(0deg); }
            100% { transform: translate(-50%, -50%) rotate(360deg); }
        }
        .start-animation {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            font-size: 4rem;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            animation: fadeOut 1.5s ease-out;
        }
        .time-up-animation {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 2em;
            color: red;
            z-index: 1000;
            animation: fadeOut 1s ease-out;
        }
        @keyframes fadeOut {
            0% { opacity: 1; }
            100% { opacity: 0; }
        }
        .animate-bounce {
            animation: bounce 1s infinite;
        }
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }
        .animate-pulse {
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.1); opacity: 0.7; }
            100% { transform: scale(1); opacity: 1; }
        }
    `;
    document.head.appendChild(style);
});