# Input and output in the future to be done through JSON Files, organized through ID in Database
from flask import Flask, render_template, request, jsonify
import faiss
import numpy as np
import sqlite3
from sentence_transformers import SentenceTransformer
from dataclasses import dataclass
from typing import List, Optional, Dict
import json
import os
from pymongo import MongoClient


client = MongoClient("mongodb+srv://LerichDev:A1aLe1fVrJ7sM4ir@orbital-cluster.rlnny.mongodb.net/?retryWrites=true&w=majority&appName=orbital-cluster")  
db = client["algo_test_db"]
collection = db["mentors"]



app = Flask(__name__)
sample_mentors = list()

# Define weights for each aspect of the matching (less weight as it's more flexible out of 100)
POSITION_WEIGHTS = {
    1: {  # First result - Career and responsibilities focused
        'career_goal': 0.45,
        'responsibilities': 0.30,
        'obstacle': 0.15,
        'mentoring_goal': 0.05,
        'teaching_style': 0.05
    },
    2: {  # Second result - Transitioning towards balance
        'career_goal': 0.35,
        'responsibilities': 0.25,
        'obstacle': 0.25,
        'mentoring_goal': 0.10,
        'teaching_style': 0.05
    },
    3: {  # Third result - Balanced weights
        'career_goal': 0.30,
        'responsibilities': 0.20,
        'obstacle': 0.30,
        'mentoring_goal': 0.15,
        'teaching_style': 0.05
    },
    4: {  # Fourth result - Transitioning to obstacle/mentoring focus
        'career_goal': 0.25,
        'responsibilities': 0.10,
        'obstacle': 0.35,
        'mentoring_goal': 0.25,
        'teaching_style': 0.05
    },
    5: {  # Fifth result - Obstacle and mentoring focused
        'career_goal': 0.15,
        'responsibilities': 0.05,
        'obstacle': 0.45,
        'mentoring_goal': 0.30,
        'teaching_style': 0.05
    }
}

@dataclass
class Mentor:
    id: int
    name: str
    position: str
    responsibilities: str
    obstacle: str
    help_offer: str
    teaching_style: str
    vector: Optional[Dict[str, np.ndarray]] = None

@dataclass
class Mentee:
    career_goal: str
    responsibilities: str
    obstacle: str
    mentoring_goal: str
    teaching_style: str

class MentorMatchingSystem:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.db_path = 'mentors.db'
        self.create_database()
        self.faiss_indices = {}
        
    def create_database(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            # Drop existing table if it exists
            c.execute('DROP TABLE IF EXISTS mentors')
            
            c.execute('''CREATE TABLE mentors (
                id INTEGER PRIMARY KEY,
                name TEXT,
                position TEXT,
                responsibilities TEXT,
                obstacle TEXT,
                help_offer TEXT,
                teaching_style TEXT,
                career_vector BLOB,
                responsibilities_vector BLOB,
                obstacle_vector BLOB,
                mentoring_vector BLOB,
                teaching_vector BLOB
            )''')
            conn.commit()
    
    def vectorize_text(self, text: str) -> np.ndarray:
        return self.model.encode([text])[0].astype('float32')
    
    def preload_sample_mentors(self):
        sample_mentors = list(collection.find({}, {"_id": 0}))

        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()

            for mentor in sample_mentors:
                profile = mentor.get("profile", {})
                questionnaire = profile.get("questionnaireAns", {})

                name = mentor.get("name", "Unnamed Mentor")
                position = questionnaire.get("1", "")
                responsibilities = questionnaire.get("2", "")
                obstacle = questionnaire.get("3", "")
                help_offer = questionnaire.get("4", "")
                teaching_style = questionnaire.get("5", "")

                try:
                    career_vector = self.vectorize_text(f"{position} {help_offer}").tobytes()
                    responsibilities_vector = self.vectorize_text(responsibilities).tobytes()
                    obstacle_vector = self.vectorize_text(obstacle).tobytes()
                    mentoring_vector = self.vectorize_text(help_offer).tobytes()
                    teaching_vector = self.vectorize_text(teaching_style).tobytes()

                    c.execute("""
                        INSERT INTO mentors 
                        (name, position, responsibilities, obstacle, help_offer, teaching_style,
                        career_vector, responsibilities_vector, obstacle_vector, mentoring_vector, teaching_vector) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name,
                        position,
                        responsibilities,
                        obstacle,
                        help_offer,
                        teaching_style,
                        career_vector,
                        responsibilities_vector,
                        obstacle_vector,
                        mentoring_vector,
                        teaching_vector
                    ))
                except Exception as e:
                    print(f"Skipping mentor {name} due to error: {e}")
            conn.commit()

    
    def build_faiss_indices(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            aspects = ['career', 'responsibilities', 'obstacle', 'mentoring', 'teaching']
            self.faiss_indices = {}
            
            for aspect in aspects:
                c.execute(f"SELECT {aspect}_vector FROM mentors")
                vectors = [np.frombuffer(row[0], dtype=np.float32) for row in c.fetchall()]
                
                if vectors:
                    vector_matrix = np.vstack(vectors)
                    index = faiss.IndexFlatL2(vector_matrix.shape[1])
                    index.add(vector_matrix)
                    self.faiss_indices[aspect] = index
    
    def calculate_similarity_scores(self, distances: Dict[str, np.ndarray]) -> List[float]:
        scores = []
        
        # Calculate score for each weighting scheme
        for position in range(1, 6):
            weighted_score = []
            weights = POSITION_WEIGHTS[position]
            
            for aspect, distance in distances.items():
                # Convert distance to similarity
                similarity = 1 / (1 + distance)
                weight = weights.get(aspect.replace('_vector', ''), 0.2)
                weighted_score.append(similarity * weight)
                
            scores.append(sum(weighted_score))
    
        return scores
    
    def match_mentee(self, mentee: Mentee, top_k: int = 5) -> List[dict]:
        if not self.faiss_indices:
            self.build_faiss_indices()
            
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM mentors")
            total_mentors = c.fetchone()[0]
        
        # Vectorize mentee inputs
        mentee_vectors = {
            'career': self.vectorize_text(mentee.career_goal),
            'responsibilities': self.vectorize_text(mentee.responsibilities),
            'obstacle': self.vectorize_text(mentee.obstacle),
            'mentoring': self.vectorize_text(mentee.mentoring_goal),
            'teaching': self.vectorize_text(mentee.teaching_style)
        }
        
        # Store all possible matches with their various scores
        mentor_matches = []
        
        # Get distances for each mentor
        for aspect, vector in mentee_vectors.items():
            if aspect in self.faiss_indices:
                distances, indices = self.faiss_indices[aspect].search(vector.reshape(1, -1), total_mentors)
                
                # Store distances for each mentor
                for idx, distance in zip(indices[0], distances[0]):
                    mentor_found = False
                    for mentor in mentor_matches:
                        if mentor['idx'] == idx:
                            mentor['distances'][aspect] = distance
                            mentor_found = True
                            break
                    
                    if not mentor_found:
                        mentor_matches.append({
                            'idx': idx,
                            'distances': {aspect: distance}
                        })
        
       # Calculate all scoring schemes for each mentor
        final_matches = []
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            for mentor in mentor_matches:
                if len(mentor['distances']) == 5:  # Ensure we have all aspects
                    scores = self.calculate_similarity_scores(mentor['distances'])

                    c.execute("""
                        SELECT name, position, responsibilities, obstacle, help_offer, teaching_style 
                        FROM mentors WHERE rowid=?
                    """, (int(mentor['idx']) + 1,))  # Add +1 since FAISS index is 0-based but SQLite rowid starts at 1

                    mentor_data = c.fetchone()
                    if mentor_data:
                        final_matches.append({
                            "name": mentor_data[0],
                            "position": mentor_data[1],
                            "responsibilities": mentor_data[2],
                            "obstacle": mentor_data[3],
                            "help_offer": mentor_data[4],
                            "teaching_style": mentor_data[5],
                            "scores": scores
                        })


        
        # Sort and select top matches based on each position's scoring
        top_matches = []
        for position in range(5):
            # Sort by the score for this position
            position_matches = sorted(
                [m for m in final_matches if m not in top_matches],
                key=lambda x: x['scores'][position],
                reverse=True
            )
            
            if position_matches:
                match = position_matches[0]
                match['match_score'] = float(match['scores'][position])
                del match['scores']  # Remove the scores array before returning
                top_matches.append(match)
        
        return top_matches

# Initialization
mentor_system = None

# @app.route('/')
# def home():
#     return render_template('index.html')

@app.route('/match', methods=['POST'])
def match_mentee():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON data"}), 400
        mentee = Mentee(
            career_goal=data['career_goal'],
            responsibilities=data['career_goal'],  
            obstacle=data['obstacle'],
            mentoring_goal=data['mentoring_goal'],
            teaching_style=data['teaching_style']
        )
      
        matches = mentor_system.match_mentee(mentee)
        return jsonify({"success": True, "matches": matches})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
    
@app.route('/upload-answers', methods=['POST'])
def upload_answers():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON data"}), 400

        mentee = Mentee(
            career_goal=data.get('career_goal', ''),
            responsibilities=data.get('career_goal', ''),  
            obstacle=data.get('obstacle', ''),
            mentoring_goal=data.get('mentoring_goal', ''),
            teaching_style=data.get('teaching_style', '')
        )

        matches = mentor_system.match_mentee(mentee)

        # Save results to a JSON file
        output_file = "top_5_matches.json"
        with open(output_file, 'w') as f:
            json.dump(matches, f, indent=4)

        return jsonify({"success": True, "message": "Matches saved", "file": output_file, "matches": matches})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# Initialization
if os.path.exists('mentors.db'):
    os.remove('mentors.db')

mentor_system = MentorMatchingSystem()
mentor_system.preload_sample_mentors()

if __name__ == '__main__':
    app.run(debug=True)
