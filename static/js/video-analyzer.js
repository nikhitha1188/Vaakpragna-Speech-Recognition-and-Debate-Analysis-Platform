// Video Analyzer JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const startLiveBtn = document.getElementById('startLive');
    const stopLiveBtn = document.getElementById('stopLive');
    const videoFeed = document.getElementById('videoFeed');
    const recordingStatus = document.getElementById('recordingStatus');
    const judgmentEl = document.getElementById('judgment');
    const eyeContactEl = document.getElementById('eyeContact');
    const bodyLanguageEl = document.getElementById('bodyLanguage');
    const tonePaceEl = document.getElementById('tonePace');
    const tipsEl = document.getElementById('tips');

    let feedbackInterval;
    let isLive = false;

    // Start live analysis
    startLiveBtn.addEventListener('click', async function() {
        try {
            // Start video feed
            videoFeed.src = '/start_live';
            startLiveBtn.disabled = true;
            stopLiveBtn.disabled = false;
            recordingStatus.textContent = 'Recording...';
            recordingStatus.classList.add('text-red-500');
            isLive = true;

            // Start polling for feedback
            feedbackInterval = setInterval(updateFeedback, 2000);
        } catch (error) {
            console.error('Error starting live analysis:', error);
            recordingStatus.textContent = 'Error starting recording';
            recordingStatus.classList.add('text-red-500');
        }
    });

    // Stop live analysis
    stopLiveBtn.addEventListener('click', async function() {
        try {
            // Stop video feed
            await fetch('/stop_live');
            videoFeed.src = '';
            startLiveBtn.disabled = false;
            stopLiveBtn.disabled = true;
            recordingStatus.textContent = 'Not Recording';
            recordingStatus.classList.remove('text-red-500');
            isLive = false;

            // Stop polling for feedback
            clearInterval(feedbackInterval);

            // Reset feedback display
            resetFeedback();
        } catch (error) {
            console.error('Error stopping live analysis:', error);
        }
    });

    // Handle keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' || e.key === 'Enter') {
            if (!stopLiveBtn.disabled) {
                stopLiveBtn.click();
            }
        }
    });

    // Update feedback from server
    async function updateFeedback() {
        if (!isLive) return;
        
        try {
            const response = await fetch('/live_feedback');
            const feedback = await response.json();

            // Update UI with feedback
            judgmentEl.textContent = feedback.judgment || 'Not available';
            eyeContactEl.textContent = feedback.eye_contact || 'Not available';
            bodyLanguageEl.textContent = feedback.body_language || 'Not available';
            tonePaceEl.textContent = feedback.tone_pace || 'Not available';
            tipsEl.textContent = feedback.tips || 'Not available';

            // Add animation to show feedback is updating
            const feedbackElements = [judgmentEl, eyeContactEl, bodyLanguageEl, tonePaceEl, tipsEl];
            feedbackElements.forEach(el => {
                el.classList.add('animate-pulse');
                setTimeout(() => el.classList.remove('animate-pulse'), 1000);
            });
        } catch (error) {
            console.error('Error updating feedback:', error);
        }
    }

    // Reset feedback display
    function resetFeedback() {
        const feedbackElements = [judgmentEl, eyeContactEl, bodyLanguageEl, tonePaceEl, tipsEl];
        feedbackElements.forEach(el => {
            el.textContent = 'Waiting for analysis...';
            el.classList.remove('animate-pulse');
        });
    }

    // Updated PDF Download report functionality (with overall analysis)
    document.getElementById('downloadReport').addEventListener('click', async function() {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        
        const today = new Date();
        const dateStr = today.toLocaleDateString() + ' ' + today.toLocaleTimeString();
        
        // Fetch the latest live feedback from backend
        let feedback = {};
        try {
            const res = await fetch('/live_feedback');
            feedback = await res.json();
        } catch (e) {
            // fallback to DOM if fetch fails
            feedback = {
                judgment: document.getElementById('judgment').innerText,
                eye_contact: document.getElementById('eyeContact').innerText,
                body_language: document.getElementById('bodyLanguage').innerText,
                tone_pace: document.getElementById('tonePace').innerText,
                tips: document.getElementById('tips').innerText
            };
        }
        const judgment = feedback.judgment || 'Not available';
        const eyeContact = feedback.eye_contact || 'Not available';
        const bodyLanguage = feedback.body_language || 'Not available';
        const tonePace = feedback.tone_pace || 'Not available';
        const tips = feedback.tips || 'Not available';
        
        // Generate overall analysis
        const overallAnalysis = generateOverallAnalysis(judgment, eyeContact, bodyLanguage, tonePace, tips);
        
        // Set colors
        const titleColor = '#4F46E5';
        const headingColor = '#10B981';
        const textColor = '#333333';
        
        // Add header
        doc.setFontSize(20);
        doc.setTextColor(titleColor);
        doc.text('Vaakpragna - Comprehensive Speech Analysis', 105, 20, { align: 'center' });
        
        doc.setFontSize(10);
        doc.setTextColor(100);
        doc.text(`Generated on: ${dateStr}`, 105, 30, { align: 'center' });
        doc.line(20, 35, 190, 35);
        
        // Add Overall Analysis section
        doc.setFontSize(16);
        doc.setTextColor(titleColor);
        doc.text('Comprehensive Performance Summary', 20, 45);
        
        doc.setFontSize(12);
        doc.setTextColor(textColor);
        doc.text(overallAnalysis, 20, 55, { maxWidth: 170 });
        
        // Add Final Live Feedback Outcomes section
        let yPosition = doc.splitTextToSize(overallAnalysis, 170).length * 6 + 60;
        doc.setFontSize(15);
        doc.setTextColor('#4F46E5');
        doc.text('Final Live Feedback Outcomes', 20, yPosition);
        yPosition += 8;
        
        const addSection = (title, content) => {
            doc.setFontSize(14);
            doc.setTextColor(headingColor);
            doc.text(title, 20, yPosition);
            yPosition += 7;
            doc.setFontSize(12);
            doc.setTextColor(textColor);
            const lines = doc.splitTextToSize(content, 170);
            // If near bottom, add new page
            if (yPosition + lines.length * 6 > 270) {
                doc.addPage();
                yPosition = 20;
            }
            doc.text(lines, 20, yPosition);
            yPosition += lines.length * 6 + 6;
        };
        
        addSection('Detailed Judgment', judgment);
        addSection('Eye Contact Analysis', eyeContact);
        addSection('Body Language Evaluation', bodyLanguage);
        addSection('Tone & Pace Assessment', tonePace);
        addSection('Actionable Improvement Tips', tips);
        
        // Add footer
        doc.setFontSize(10);
        doc.setTextColor(100);
        doc.text('© Vaakpragna - AI-Powered Speech Analysis', 105, 285, { align: 'center' });
        
        doc.save(`Vaakpragna_Speech_Analysis_${today.toISOString().slice(0,10)}.pdf`);
    });
});

// Generate a holistic overall analysis based on all feedback sections
function generateOverallAnalysis(judgment, eyeContact, bodyLanguage, tonePace, tips) {
    return `
This comprehensive analysis combines all evaluation metrics to provide a holistic view of your speaking performance.

Key Strengths:
- ${judgment.includes('good') || judgment.includes('excellent') ? judgment.split('.')[0] : 'Your delivery shows potential in several areas'}
- ${eyeContact.includes('good') || eyeContact.includes('excellent') ? eyeContact.split('.')[0] : 'With practice, your eye contact can become more effective'}
- ${bodyLanguage.includes('good') || bodyLanguage.includes('excellent') ? bodyLanguage.split('.')[0] : 'Your body language has room for improvement'}

Areas for Development:
- ${tonePace.includes('improve') ? tonePace.split('.')[0] : 'Your tone and pace are generally appropriate'}
- ${tips.includes('try') ? tips.split('.')[0] : 'Consider implementing the suggested improvements'}

Recommendations:
1. Focus on ${tips.split('.')[0].toLowerCase() || 'the key areas mentioned above'}
2. Practice ${eyeContact.toLowerCase().includes('maintain') ? 'maintaining consistent eye contact' : 'your eye contact technique'}
3. Work on ${bodyLanguage.toLowerCase().includes('posture') ? 'your posture and gestures' : 'your body language awareness'}

Final Assessment:
${judgment || 'Your overall performance shows potential with room for growth in specific areas.'}
`;
} 