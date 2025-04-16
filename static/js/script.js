const questions = [
    {
        id: "career_goal",
        text: "What is the future job or area you have for yourself? What type of responsibilities would you have?",
        type: "textarea"
    },
    {
        id: "obstacle",
        text: "What is the main obstacle you are facing in your professional development currently?",
        type: "textarea"
    },
    {
        id: "mentoring_goal",
        text: "What do you hope to accomplish with a mentor in the next 6 months?",
        type: "textarea"
    },
    {
        id: "teaching_style",
        text: "What type of teaching do you respond best to?",
        type: "select",
        options: ["Visual", "Traditional", "Mixed"]
    }
];

const matchDescriptions = {
    1: "Career & Responsibilities Focused (Career: 45%, Responsibilities: 30%)",
    2: "Transitioning to Balance (Career: 35%, Responsibilities: 25%, Obstacle: 25%)",
    3: "Balanced Weights (Career: 30%, Responsibilities: 20%, Obstacle: 30%)",
    4: "Transitioning to Obstacle Focus (Obstacle: 35%, Mentoring: 25%)",
    5: "Obstacle & Mentoring Focused (Obstacle: 45%, Mentoring: 30%)"
};

class MentorMatchingUI {
    constructor() {
        this.currentQuestionIndex = 0;
        this.answers = {};
        
        this.questionContainer = document.getElementById("question-container");
        this.resultsContainer = document.getElementById("results-container");
        this.mentorList = document.getElementById("mentor-list");
        
        this.initializeUI();
    }
    
    initializeUI() {
        this.renderQuestion();
        document.getElementById("next-btn").addEventListener("click", () => this.handleNext());
    }
    
    renderQuestion() {
        const question = questions[this.currentQuestionIndex];
        const questionText = document.getElementById("question-text");
        const inputContainer = document.getElementById("input-container");
        
        questionText.textContent = question.text;
        inputContainer.innerHTML = '';
        
        if (question.type === "textarea") {
            const textarea = document.createElement("textarea");
            textarea.id = "current-input";
            textarea.placeholder = "Type your response...";
            textarea.value = this.answers[question.id] || '';
            inputContainer.appendChild(textarea);
        } else if (question.type === "select") {
            const select = document.createElement("select");
            select.id = "current-input";
            question.options.forEach(option => {
                const optionElement = document.createElement("option");
                optionElement.value = option;
                optionElement.textContent = option;
                select.appendChild(optionElement);
            });
            select.value = this.answers[question.id] || question.options[0];
            inputContainer.appendChild(select);
        }
    }
    
    handleNext() {
        const currentQuestion = questions[this.currentQuestionIndex];
        const input = document.getElementById("current-input");
        
        if (!input.value.trim()) {
            alert("Please provide an answer before continuing.");
            return;
        }
        
        this.answers[currentQuestion.id] = input.value.trim();
        
        if (this.currentQuestionIndex < questions.length - 1) {
            this.currentQuestionIndex++;
            this.renderQuestion();
        } else {
            this.submitAnswers();
        }
    }
    
    async submitAnswers() {
        try {
            const response = await fetch("/match", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    career_goal: this.answers.career_goal,
                    responsibilities: this.answers.career_goal, 
                    obstacle: this.answers.obstacle,
                    mentoring_goal: this.answers.mentoring_goal,
                    teaching_style: this.answers.teaching_style
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.displayResults(data.matches);
            } else {
                throw new Error(data.error || "Failed to find matches");
            }
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    }
    
    displayResults(matches) {
        this.questionContainer.style.display = "none";
        this.resultsContainer.style.display = "block";
        this.mentorList.innerHTML = "";
        
        matches.forEach((mentor, index) => {
            const matchPosition = index + 1;
            const matchScore = Math.round(mentor.match_score * 100);
            
            const li = document.createElement("li");
            li.className = "mentor-card";
            li.innerHTML = `
                <div class="match-position">Match ${matchPosition}</div>
                <div class="match-description">${matchDescriptions[matchPosition]}</div>
                <h3>${mentor.name}</h3>
                <p><strong>Position:</strong> ${mentor.position}</p>
                <p><strong>Responsibilities:</strong> ${mentor.responsibilities}</p>
                <p><strong>Can help with:</strong> ${mentor.help_offer}</p>
                <p><strong>Teaching style:</strong> ${mentor.teaching_style}</p>
                <p><strong>Match score:</strong> ${matchScore}%</p>
            `;
            this.mentorList.appendChild(li);
        });
    }
}

// Initialize the UI after loading 
document.addEventListener('DOMContentLoaded', () => {
    new MentorMatchingUI();
});