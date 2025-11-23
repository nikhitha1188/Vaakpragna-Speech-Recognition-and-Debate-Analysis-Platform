# Set environment variables before any imports to suppress TensorFlow warnings
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '3'

import logging
logging.getLogger('tensorflow').setLevel(logging.ERROR)
logging.getLogger('absl').setLevel(logging.ERROR)
logging.getLogger('mediapipe').setLevel(logging.ERROR)

from flask import Blueprint, render_template, request, jsonify, Response
import cv2, mediapipe as mp, dlib, re
import numpy as np
import google.generativeai as genai

video_analyzer_bp = Blueprint("video_analyzer", __name__)
genai.configure(api_key="AIzaSyAlpyIaKMRn7cVdJLAa5HU0xETAK9E3-08")
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'shape_predictor_68_face_landmarks.dat')

camera_active = False
latest_live_feedback = {"judgment": "", "eye_contact": "", "body_language": "", "tone_pace": "", "tips": ""}

@video_analyzer_bp.route("/video-analyzer")
def video_page():
    return render_template("video-analyzer.html")

@video_analyzer_bp.route("/start_live")
def start_live():
    global camera_active
    camera_active = True
    return Response(gen_live(), mimetype='multipart/x-mixed-replace; boundary=frame')

@video_analyzer_bp.route("/stop_live")
def stop_live():
    global camera_active
    camera_active = False
    return jsonify({"message": "Live feed stopped"})

@video_analyzer_bp.route("/live_feedback")
def live_feedback():
    print(f"Serving feedback: {latest_live_feedback}")
    return jsonify(latest_live_feedback)

@video_analyzer_bp.route("/analyze_voice", methods=["POST"])
def analyze_voice():
    data = request.get_json()
    transcript = data.get("transcript", "")
    speech_rate = data.get("speech_rate", 0)
    pitch_variation = data.get("pitch_variation", 0)

    if not transcript:
        return jsonify({"error": "No transcript provided"}), 400

    voice_info = f"Speech rate: {speech_rate} words/min, Pitch variation: {pitch_variation}"
    prompt = build_voice_prompt(voice_info)
    result = call_gemini(prompt)
    print(f"Voice analysis result: {result}")
    if "error" in result:
        return jsonify(result), 500
    latest_live_feedback["tone_pace"] = result.get("tone_pace", "Not available")
    return jsonify(latest_live_feedback)

def gen_live():
    global camera_active, latest_live_feedback
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(MODEL_PATH)
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5, model_complexity=1)

    frame_count = 0
    face_count = 0
    pose_count = 0

    while camera_active and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector(gray)
        if faces:
            face_count += 1
            shape = predictor(gray, faces[0])
            for i in range(36, 48):
                cv2.circle(frame, (shape.part(i).x, shape.part(i).y), 2, (0, 255, 0), -1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        if results.pose_landmarks:
            pose_count += 1
            mp.solutions.drawing_utils.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        if frame_count % 15 == 0:
            eye_summary = f"Eye contact: {face_count}/{frame_count} frames"
            pose_summary = f"Pose: {pose_count}/{frame_count} frames"
            print(f"Live metrics: {eye_summary}, {pose_summary}")
            prompt = build_student_prompt(eye_summary, pose_summary, "Live session")
            feedback = call_gemini(prompt)
            print(f"Video feedback: {feedback}")
            latest_live_feedback.update({
                "judgment": feedback.get("judgment", "Not available"),
                "eye_contact": feedback.get("eye_contact", "Not available"),
                "body_language": feedback.get("body_language", "Not available"),
                "tips": feedback.get("tips", "Not available")
            })

            transcript = "Sample live speech for analysis."
            speech_rate = np.random.randint(120, 180)
            pitch_variation = np.random.randint(50, 100)
            voice_info = f"Speech rate: {speech_rate} words/min, Pitch variation: {pitch_variation}"
            voice_prompt = build_voice_prompt(voice_info)
            voice_result = call_gemini(voice_prompt)
            print(f"Voice feedback: {voice_result}")
            latest_live_feedback["tone_pace"] = voice_result.get("tone_pace", "Not available")

            print(f"Updated latest_live_feedback: {latest_live_feedback}")
            face_count = 0
            pose_count = 0
            frame_count = 0

        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

    cap.release()
    cv2.destroyAllWindows()

def build_student_prompt(eye_info, pose_info, topic_summary):
    return f"""
You are a professional public speaking coach providing concise, actionable feedback.
Analyze the following and respond with feedback in the format below (1 sentence each):
1. Overall Judgment: [Your judgment here]
2. Eye Contact Feedback: [Your feedback here]
3. Body Language Feedback: [Your feedback here]
4. Improvement Tips: [Your tips here]
Use a positive, encouraging tone.

## Eye Tracking:
{eye_info}

## Body Language:
{pose_info}

## Topic:
{topic_summary}
"""

def build_voice_prompt(voice_info):
    return f"""
You are a professional public speaking coach.

Given the voice metrics below, identify the speaker's **tone** (e.g., formal, casual, nervous, enthusiastic, monotone, robotic, dynamic, persuasive) and provide clear, encouraging feedback on how the tone and pace affect delivery. Suggest specific improvements if needed.

Respond exactly in this format:
1. Detected Tone: [one phrase only]
2. Tone and Pace Feedback: [one brief sentence giving advice or praise]

Voice Metrics:
{voice_info}
"""

def call_gemini(prompt):
    try:
        response = gemini_model.generate_content(prompt)
        full_text = response.text.strip()
        print(f"Raw Gemini response: {full_text}")

        if "Voice Metrics" in prompt:
            tone_detected = extract_section(full_text, "1. Detected Tone:")
            tone_feedback = extract_section(full_text, "2. Tone and Pace Feedback:")
            return {
                "tone_pace": f"{tone_feedback} (Tone detected: {tone_detected})" if tone_feedback and tone_detected else "Not available"
            }

        return {
            "judgment": extract_section(full_text, "1. Overall Judgment:"),
            "eye_contact": extract_section(full_text, "2. Eye Contact Feedback:"),
            "body_language": extract_section(full_text, "3. Body Language Feedback:"),
            "tips": extract_section(full_text, "4. Improvement Tips:")
        }
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        if "Voice Metrics" in prompt:
            return {"tone_pace": "Error in analysis"}
        return {
            "judgment": "Error in analysis",
            "eye_contact": "Error in analysis",
            "body_language": "Error in analysis",
            "tips": "Error in analysis"
        }

def extract_section(text, marker):
    pattern = rf"{re.escape(marker)}\s*(.*?)(?=\n\d+\.|\Z|-|\n\n)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip().lstrip("*\u2022- ").strip()
    if marker in text:
        parts = text.split(marker, 1)
        if len(parts) > 1:
            next_section = parts[1].split('\n', 1)[0].strip()
            return next_section.lstrip("*\u2022- ").strip()
    return "Not available"

