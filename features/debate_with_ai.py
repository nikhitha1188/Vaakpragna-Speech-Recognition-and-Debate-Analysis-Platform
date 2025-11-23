from flask import Blueprint, request, jsonify, render_template
import random
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import time
import uuid
import logging
import threading
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

debate_bp = Blueprint('debate', __name__, template_folder='../templates', static_folder='../static')

genai.configure(api_key='AIzaSyBKLMeWZvyjoB0AXHY6MEIgCKT--vXe_LY')
try:
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    logger.error(f"Failed to initialize Gemini API: {str(e)}")
    model = None

debate_topics = [
    "AI in Education",
    "Climate Change Policies",
    "Universal Basic Income",
    "Social Media Regulation",
    "Space Exploration Funding",
    "Genetic Engineering Ethics",
    "Renewable Energy Adoption",
    "Privacy vs. Security",
    "Legalization of Recreational Marijuana",
    "Automation and Job Displacement"
]

try:
    tts_engine = pyttsx3.init()
    voices = tts_engine.getProperty('voices')
    if not voices:
        raise Exception("No voices available for pyttsx3")
    tts_engine.setProperty('voice', voices[0].id)
except Exception as e:
    logger.error(f"Failed to initialize pyttsx3: {str(e)}")
    tts_engine = None

# Thread lock for TTS engine access
tts_lock = threading.Lock()

debate_state = {
    'current_topic': None,
    'debate_style': 'Formal',
    'ai_difficulty': 'Intermediate',
    'time_per_turn': 30,
    'num_rounds': 3,
    'current_round': 1,
    'dialogues': [],
    'user_score': 0,
    'ai_score': 0,
    'last_user_speak_time': None
}

@debate_bp.route('/')
def index():
    return render_template('debate-with-ai.html')

@debate_bp.route('/roll_dice', methods=['POST'])
def roll_dice():
    topic = random.choice(debate_topics)
    return jsonify({'topic': topic})

@debate_bp.route('/accept_topic', methods=['POST'])
def accept_topic():
    data = request.json
    debate_state['current_topic'] = data.get('topic')
    num_rounds = data.get('num_rounds', '').strip()
    if not num_rounds or not num_rounds.isdigit() or int(num_rounds) < 1:
        return jsonify({'error': 'Please enter a valid number of rounds (at least 1).'}), 400
    debate_state['num_rounds'] = int(num_rounds)
    debate_state['current_round'] = 1
    return jsonify({'status': 'success', 'round': debate_state['current_round']})

@debate_bp.route('/set_debate_settings', methods=['POST'])
def set_debate_settings():
    data = request.json
    debate_state['debate_style'] = data['style']
    debate_state['ai_difficulty'] = data['difficulty']
    debate_state['time_per_turn'] = int(data['time_per_turn'])
    
    if tts_engine:
        try:
            with tts_lock:
                if debate_state['debate_style'] == 'Formal':
                    tts_engine.setProperty('rate', 150)
                elif debate_state['debate_style'] == 'Casual':
                    tts_engine.setProperty('rate', 170)
                else:
                    tts_engine.setProperty('rate', 160)
        except Exception as e:
            logger.error(f"Failed to set pyttsx3 properties: {str(e)}")
    
    return jsonify({'status': 'success'})

@debate_bp.route('/voice_input', methods=['POST'])
def voice_input():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        try:
            start_time = time.time()
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            text = recognizer.recognize_google(audio)
            end_time = time.time()
            debate_state['last_user_speak_time'] = end_time - start_time
            return jsonify({'text': text})
        except sr.UnknownValueError:
            return jsonify({'error': 'Could not understand audio'})
        except sr.RequestError:
            return jsonify({'error': 'Speech recognition service unavailable'})
        except sr.WaitTimeoutError:
            return jsonify({'error': 'Listening timed out, please try again'})
        except Exception as e:
            return jsonify({'error': f'Unexpected error: {str(e)}'})

@debate_bp.route('/speak_welcome', methods=['POST'])
def speak_welcome():
    try:
        data = request.json
        welcome_message = data.get('message')
        if not welcome_message:
            return jsonify({'error': 'No welcome message provided'}), 400

        if tts_engine:
            try:
                with tts_lock:
                    tts_engine.setProperty('rate', 150)
                    tts_engine.say(welcome_message)
                    tts_engine.runAndWait()
                return jsonify({'status': 'success'})
            except Exception as e:
                logger.error(f"Failed to speak welcome message: {str(e)}")
                return jsonify({'error': f'Failed to speak welcome message: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Text-to-speech engine not initialized'}), 500

    except Exception as e:
        logger.error(f"Error in speak_welcome: {str(e)}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

def speak_text(text):
    global tts_engine
    if tts_engine:
        try:
            with tts_lock:
                tts_engine.say(text)
                tts_engine.runAndWait()
        except Exception as e:
            logger.error(f"Failed to convert text to speech: {str(e)}")
            try:
                with tts_lock:
                    tts_engine.stop()  # Stop any ongoing speech
                    tts_engine = pyttsx3.init()  # Reinitialize
                    voices = tts_engine.getProperty('voices')
                    if voices:
                        tts_engine.setProperty('voice', voices[0].id)
                        tts_engine.setProperty('rate', 150)
                        tts_engine.say(text)
                        tts_engine.runAndWait()
                    else:
                        logger.error("No voices available after reinitialization")
            except Exception as reinit_e:
                logger.error(f"Failed to reinitialize pyttsx3: {str(reinit_e)}")

def get_word_definition(word):
    try:
        prompt = f"""Provide a simple, one-sentence definition for the word \"{word}\" that would be understandable by a high school student.\nReturn ONLY the definition with no additional text or formatting."""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error getting definition for {word}: {str(e)}")
        return None

@debate_bp.route('/generate_ai_response', methods=['POST'])
def generate_ai_response():
    try:
        data = request.json
        user_input = data['user_input']
        debate_state['dialogues'].append({'speaker': 'You', 'text': user_input, 'time': time.strftime('%H:%M')})

        if not model:
            raise Exception("Gemini API model not initialized")

        # Professional debate prompt with strict length requirements
        prompt = f"""Act as a professional debate opponent on the topic: {debate_state['current_topic']}.
        The debate style is {debate_state['debate_style']}.
        My last argument was: \"{user_input}\"
        
        Respond concisely in 2-3 lines maximum, following these rules:
        1. Acknowledge my point briefly
        2. Present a clear counter-argument
        3. Use professional but engaging language
        4. Maintain logical consistency
        5. Keep response under 40 words if possible
        6. Make sure to use the same language as the user.
        7. Make sure to use the same tone as the user.
        8. Stay close to the topic,dont get carried away.
        
        Example formats:
        - \"While I understand your point about X, the evidence suggests Y because Z.\"
        - \"That's an interesting perspective, but have you considered X? Studies show Y.\"
        - \"I respectfully disagree because X. The data indicates Y which contradicts your point.\"\n        """

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=50,  # Keep responses short
                temperature=0.7  # Balance creativity and focus
            )
        )
        response_text = response.text.strip()

        # Detect complex words
        complex_words = detect_complex_words(response_text)
        complex_word_data = []
        for word in complex_words:
            definition = get_word_definition(word)
            if definition:
                complex_word_data.append({
                    'word': word,
                    'definition': definition
                })

        # Ensure response is concise
        if len(response_text.split()) > 30:
            sentences = response_text.split('. ')
            response_text = '. '.join(sentences[:2]) + '.' if len(sentences) > 1 else sentences[0]

        debate_state['dialogues'].append({'speaker': 'AI Opponent', 'text': response_text, 'time': time.strftime('%H:%M')})

        # Check if round is complete (10 exchanges = 5 from each side)
        user_exchanges = len([d for d in debate_state['dialogues'] if d['speaker'] == 'You'])
        ai_exchanges = len([d for d in debate_state['dialogues'] if d['speaker'] == 'AI Opponent'])
        round_complete = (user_exchanges + ai_exchanges) >= 10
        end = False
        analysis = None
        
        if round_complete:
            analysis = analyze_debate()
            # Process the response to be more concise if 'Unintended Humor' is present
            if isinstance(analysis.get('strengths'), str) and "Unintended Humor" in analysis['strengths']:
                analysis['strengths'] = "1. Efficient communication\n2. Engaged audience emotionally"
                analysis['weaknesses'] = "1. Lacked substantive arguments\n2. Failed to address the topic\n3. No engagement with opponent"
                analysis['improvements'] = "1. Research the topic thoroughly\n2. Develop a clear stance\n3. Support arguments with evidence"
            debate_state['current_round'] += 1
            debate_state['dialogues'] = []
            if debate_state['current_round'] > debate_state['num_rounds']:
                end = True
            return jsonify({
                'response': response_text,
                'complex_words': complex_word_data,
                'round': debate_state['current_round'] - 1,
                'analysis': analysis,
                'end': end
            })

        return jsonify({'response': response_text, 'complex_words': complex_word_data, 'round': debate_state['current_round']})

    except Exception as e:
        logger.error(f"Error in generate_ai_response: {str(e)}")
        return jsonify({'error': f'Failed to generate AI response: {str(e)}'}), 500

def analyze_debate():
    user_dialogues = [d['text'] for d in debate_state['dialogues'] if d['speaker'] == 'You']
    ai_dialogues = [d['text'] for d in debate_state['dialogues'] if d['speaker'] == 'AI Opponent']

    try:
        prompt = f"""Act as a professional debate judge analyzing this {debate_state['debate_style']} debate on {debate_state['current_topic']}.

        User Arguments:
        {user_dialogues}

        AI Opponent Arguments:
        {ai_dialogues}

        Provide a detailed analysis with these EXACT section headers:
        [Strengths]
        [Weaknesses]
        [Improvements]
        [Score]
        [Winner]

        For each section, provide 2-3 concise bullet points (except Score which should be a number 0-100 and Winner which should be either "User" or "AI Opponent").

        Example format:
        [Strengths]
        - Clear logical structure
        - Good use of evidence
        [Weaknesses]
        - Lacked counter-arguments
        - Needed more examples
        [Improvements]
        - Research more statistics
        - Address opponent's points directly
        [Score]
        75
        [Winner]
        AI Opponent
        """

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=400,
                temperature=0.3
            )
        )
        analysis_text = response.text.strip()

        # Initialize with defaults that will show if parsing fails
        analysis = {
            'strengths': 'No strengths identified',
            'weaknesses': 'No weaknesses identified',
            'improvements': 'No suggestions provided',
            'score': 50,
            'winner': 'AI Opponent'
        }

        # More robust parsing that handles different formats
        sections = re.split(r'\[(.*?)\]', analysis_text)
        for i in range(1, len(sections), 2):
            section_name = sections[i].strip()
            content = sections[i+1].strip() if i+1 < len(sections) else ""
            
            if section_name.lower() == 'strengths':
                analysis['strengths'] = content or 'No strengths identified'
            elif section_name.lower() == 'weaknesses':
                analysis['weaknesses'] = content or 'No weaknesses identified'
            elif section_name.lower() == 'improvements':
                analysis['improvements'] = content or 'No suggestions provided'
            elif section_name.lower() == 'score':
                try:
                    analysis['score'] = min(100, max(0, int(re.search(r'\d+', content).group())))
                except:
                    analysis['score'] = 50
            elif section_name.lower() == 'winner':
                if 'user' in content.lower():
                    analysis['winner'] = 'You'
                else:
                    analysis['winner'] = 'AI Opponent'

        # Clean up each section
        for key in ['strengths', 'weaknesses', 'improvements']:
            analysis[key] = analysis[key].replace('- ', '• ').strip()
            if not analysis[key] or analysis[key] == 'No analysis available':
                analysis[key] = f'No {key} identified' if key != 'improvements' else 'No suggestions provided'

        return analysis

    except Exception as e:
        logger.error(f"Error in analyze_debate: {str(e)}")
        return {
            'strengths': 'Analysis failed - please try again',
            'weaknesses': 'Analysis failed - please try again',
            'improvements': 'Analysis failed - please try again',
            'score': 50,
            'winner': 'AI Opponent'
        }

def detect_complex_words(text):
    """
    Uses the Gemini API to detect complex or difficult words in the given text.
    Returns a list of complex words, or an empty list if none are found or on error.
    """
    try:
        if not model:
            return []
        prompt = f"""Analyze this text and identify any complex or difficult words that might be challenging for an average reader:\n\n\"{text}\"\n\nReturn ONLY a comma-separated list of the complex words you identify, with no additional explanation or formatting.\nIf no complex words are found, return an empty string."""
        response = model.generate_content(prompt)
        complex_words = response.text.strip().split(',') if response.text.strip() else []
        return [word.strip() for word in complex_words if word.strip()]
    except Exception as e:
        logger.error(f"Error detecting complex words: {str(e)}")
        return []