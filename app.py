import os
import torch
import torch.nn as nn
from flask import Flask, request, jsonify, render_template, send_from_directory, session, flash, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
from transformers import ViTForImageClassification, ViTImageProcessor
import mysql.connector
import datetime
import numpy as np
from functools import wraps
import json

# ============================================
# CONFIGURATION
# ============================================
app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
CORS(app)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}

# Create folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('models', exist_ok=True)

# ============================================
# DATABASE CONFIGURATION (MySQL uniquement)
# ============================================
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'pfe_medical',
    'port': 3306
}

def get_db_connection():
    """Get MySQL database connection"""
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

# ============================================
# INITIALISATION DES TABLES
# ============================================

def init_users_table():
    """Initialize users table in MySQL"""
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot connect to MySQL. Please make sure MySQL is running.")
        return
    
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            specialty VARCHAR(100),
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Users table initialized")

def init_consultations_table():
    """Initialize consultations table in MySQL"""
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot connect to MySQL. Please make sure MySQL is running.")
        return
    
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consultations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            consultation_id VARCHAR(50),
            patient_id VARCHAR(50),
            patient_name VARCHAR(100) NOT NULL,
            patient_age INT,
            patient_gender CHAR(1),
            smoking_status ENUM('never', 'former', 'current'),
            smoking_years INT,
            packs_per_day DECIMAL(3,1),
            pack_years DECIMAL(5,1),
            passive_smoking BOOLEAN,
            clinical_suspicion ENUM('low', 'moderate', 'high', 'very_high'),
            urgency_level ENUM('low', 'medium', 'high', 'critical'),
            initial_suspicion TEXT,
            clinical_notes TEXT,
            symptoms JSON,
            image_path VARCHAR(500),
            vit_results JSON,
            staging JSON,
            final_diagnosis JSON,
            additional_tests JSON,
            additional_tests_results JSON,
            status VARCHAR(50) DEFAULT 'consultation_completed',
            direct_validation BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_patient_name (patient_name),
            INDEX idx_patient_id (patient_id),
            INDEX idx_status (status),
            INDEX idx_created_at (created_at)
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Consultations table initialized")

# Initialize tables
init_users_table()
init_consultations_table()

# ============================================
# AUTHENTIFICATION - ROUTES
# ============================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        specialty = request.form.get('specialty')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash('Erreur de connexion à la base de données', 'danger')
            return render_template('register.html')
        
        cursor = conn.cursor()
        
        # Vérifier si l'utilisateur existe déjà
        cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
        existing = cursor.fetchone()
        
        if existing:
            flash('Nom d\'utilisateur ou email déjà utilisé', 'danger')
            cursor.close()
            conn.close()
            return render_template('register.html')
        
        # Hasher le mot de passe
        hashed = generate_password_hash(password)
        
        # Insérer l'utilisateur
        cursor.execute('''
            INSERT INTO users (username, email, full_name, specialty, password_hash)
            VALUES (%s, %s, %s, %s, %s)
        ''', (username, email, full_name, specialty, hashed))
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Inscription réussie ! Veuillez vous connecter.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash('Erreur de connexion à la base de données', 'danger')
            return render_template('login.html')
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['doctor_name'] = user['full_name']
            flash(f'Bienvenue Dr. {user["full_name"]} !', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('index'))

# ============================================
# AUTHENTICATION MIDDLEWARE
# ============================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter pour accéder à cette page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# AI PARAMETERS
# ============================================
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
IMG_SIZE = 224
CLASS_NAMES = ['adenocarcinoma', 'large.cell.carcinoma', 'normal', 'squamous.cell.carcinoma']
NUM_CLASSES = 4

# ============================================
# LOAD VIT MODEL
# ============================================
print("="*50)
print("Loading Vision Transformer model...")
print("="*50)

model = None
feature_extractor = None

try:
    print("📁 Loading base ViT model from HuggingFace...")
    model = ViTForImageClassification.from_pretrained('google/vit-base-patch16-224-in21k')
    model.classifier = nn.Linear(model.config.hidden_size, NUM_CLASSES)
    
    model_path = 'models/full_model.pth'
    if os.path.exists(model_path):
        print(f"📥 Loading weights from: {model_path}")
        checkpoint = torch.load(model_path, map_location=DEVICE, weights_only=False)
        
        if isinstance(checkpoint, ViTForImageClassification):
            model = checkpoint
            print("✅ Loaded complete ViT model directly!")
        elif isinstance(checkpoint, dict) and 'model' in checkpoint:
            model = checkpoint['model']
            print("✅ Loaded model from dictionary key 'model'!")
        elif isinstance(checkpoint, dict):
            model.load_state_dict(checkpoint, strict=False)
            print("✅ Loaded state_dict!")
        else:
            print("⚠️ Using base model with random weights")
    else:
        print(f"⚠️ Model file not found at: {model_path}")
    
    feature_extractor = ViTImageProcessor.from_pretrained('google/vit-base-patch16-224-in21k')
    print("✅ Feature extractor loaded!")
    
except Exception as e:
    print(f"❌ Error loading model: {e}")

if model:
    model.to(DEVICE)
    model.eval()
print(f"💾 Device: {DEVICE}")

# ============================================
# TRANSFORMATIONS
# ============================================
from torchvision import transforms
mean = [0.485, 0.456, 0.406]
std = [0.229, 0.224, 0.225]
inference_transform = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean, std)
])

# ============================================
# FONCTION DE PRÉDICTION
# ============================================
def predict_image(image_path):
    """Retourne (classe_predite, confidence, probas_dict)"""
    if model is None:
        return 'normal', 0.5, {cls: 0.25 for cls in CLASS_NAMES}
    
    try:
        image = Image.open(image_path).convert('RGB')
        
        if feature_extractor:
            inputs = feature_extractor(images=image, return_tensors="pt")
            input_tensor = inputs['pixel_values'].to(DEVICE)
        else:
            input_tensor = inference_transform(image).unsqueeze(0).to(DEVICE)
        
        with torch.no_grad():
            outputs = model(pixel_values=input_tensor)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=1).cpu().numpy()[0]
        
        pred_idx = np.argmax(probabilities)
        confidence = float(probabilities[pred_idx])
        predicted_class = CLASS_NAMES[pred_idx]
        probas = {CLASS_NAMES[i]: float(probabilities[i]) for i in range(NUM_CLASSES)}
        
        return predicted_class, confidence, probas
    
    except Exception as e:
        print(f"Prediction error: {e}")
        return 'normal', 0.5, {cls: 0.25 for cls in CLASS_NAMES}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============================================
# ROUTES PROTÉGÉES
# ============================================

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/first-consultation')
@login_required
def first_consultation():
    return render_template('first_consultation.html')

@app.route('/upload')
@login_required
def upload_page():
    return render_template('upload.html')

@app.route('/predict')
@login_required
def predict_page():
    return render_template('predict.html')

@app.route('/tumor-staging')
@login_required
def tumor_staging():
    return render_template('tumor_staging.html')

@app.route('/additional-tests')
@login_required
def additional_tests():
    return render_template('additional_tests.html')

@app.route('/validate')
@login_required
def validate_page():
    return render_template('validate.html')

@app.route('/history')
@login_required
def history_page():
    return render_template('history.html')

@app.route('/report')
@login_required
def report():
    return render_template('report.html')

# ============================================
# API ROUTES - MySQL uniquement
# ============================================

@app.route('/api/save_consultation', methods=['POST'])
@login_required
def save_consultation():
    """Save consultation to MySQL"""
    data = request.json
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO consultations (
                consultation_id, patient_id, patient_name, patient_age, patient_gender,
                smoking_status, smoking_years, packs_per_day, pack_years, passive_smoking,
                clinical_suspicion, urgency_level, initial_suspicion, clinical_notes,
                symptoms, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('consultation_id'),
            data.get('patient_id'),
            data.get('patient_name'),
            data.get('patient_age'),
            data.get('patient_gender'),
            data.get('smoking_status'),
            data.get('smoking_years'),
            data.get('packs_per_day'),
            data.get('pack_years'),
            data.get('passive_smoking'),
            data.get('clinical_suspicion'),
            data.get('urgency_level'),
            data.get('initial_suspicion'),
            data.get('clinical_notes'),
            json.dumps(data.get('symptoms', {})),
            'consultation_completed'
        ))
        
        consultation_db_id = cursor.lastrowid
        conn.commit()
        return jsonify({'success': True, 'id': consultation_db_id})
    
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/get_consultations', methods=['GET'])
@login_required
def get_consultations():
    """Get all consultations from MySQL"""
    conn = get_db_connection()
    if not conn:
        return jsonify([]), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM consultations ORDER BY created_at DESC")
        rows = cursor.fetchall()
        
        for row in rows:
            if row.get('symptoms'):
                row['symptoms'] = json.loads(row['symptoms']) if row['symptoms'] else {}
            if row.get('vit_results'):
                row['vit_results'] = json.loads(row['vit_results']) if row['vit_results'] else None
            if row.get('staging'):
                row['staging'] = json.loads(row['staging']) if row['staging'] else None
            if row.get('final_diagnosis'):
                row['final_diagnosis'] = json.loads(row['final_diagnosis']) if row['final_diagnosis'] else None
            if row.get('additional_tests'):
                row['additional_tests'] = json.loads(row['additional_tests']) if row['additional_tests'] else None
            if row.get('additional_tests_results'):
                row['additional_tests_results'] = json.loads(row['additional_tests_results']) if row['additional_tests_results'] else None
        
        return jsonify(rows)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/get_consultation/<int:consultation_id>', methods=['GET'])
@login_required
def get_consultation(consultation_id):
    """Get single consultation from MySQL"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM consultations WHERE id = %s", (consultation_id,))
        row = cursor.fetchone()
        
        if row:
            if row.get('symptoms'):
                row['symptoms'] = json.loads(row['symptoms']) if row['symptoms'] else {}
            if row.get('vit_results'):
                row['vit_results'] = json.loads(row['vit_results']) if row['vit_results'] else None
            if row.get('staging'):
                row['staging'] = json.loads(row['staging']) if row['staging'] else None
            if row.get('final_diagnosis'):
                row['final_diagnosis'] = json.loads(row['final_diagnosis']) if row['final_diagnosis'] else None
        
        return jsonify(row) if row else jsonify({'error': 'Not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/upload_image', methods=['POST'])
@login_required
def upload_image():
    """Upload CT scan image and update MySQL"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image'}), 400
    
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file'}), 400
    
    filename = secure_filename(file.filename)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_filename = f"{timestamp}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(filepath)
    
    consultation_id = request.form.get('consultation_id')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE consultations 
            SET image_path = %s, status = 'ct_uploaded' 
            WHERE id = %s
        """, (saved_filename, consultation_id))
        conn.commit()
        
        return jsonify({
            'success': True,
            'image_url': f'/static/uploads/{saved_filename}',
            'consultation_id': consultation_id
        })
    
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/predict/<int:consultation_id>', methods=['GET'])
@login_required
def run_prediction(consultation_id):
    """Run AI prediction and save to MySQL"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT image_path FROM consultations WHERE id = %s", (consultation_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({'error': 'Consultation not found'}), 404
        
        image_path = row[0]
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], image_path)
        predicted_class, confidence, probas = predict_image(full_path)
        
        cursor.execute("""
            UPDATE consultations 
            SET vit_results = %s, status = 'predicted' 
            WHERE id = %s
        """, (json.dumps({'predictedClass': predicted_class, 'confidence': confidence, 'probabilities': probas}), consultation_id))
        conn.commit()
        
        return jsonify({
            'consultation_id': consultation_id,
            'predicted_class': predicted_class,
            'confidence': confidence,
            'probabilities': probas
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/update_staging', methods=['POST'])
@login_required
def update_staging():
    """Update staging information in MySQL"""
    data = request.json
    consultation_id = data.get('consultation_id')
    staging_data = data.get('staging')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE consultations 
            SET staging = %s, status = 'staging_completed' 
            WHERE id = %s
        """, (json.dumps(staging_data), consultation_id))
        conn.commit()
        return jsonify({'success': True})
    
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/update_additional_tests', methods=['POST'])
@login_required
def update_additional_tests():
    """Update additional tests in MySQL"""
    data = request.json
    consultation_id = data.get('consultation_id')
    additional_tests = data.get('additional_tests')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE consultations 
            SET additional_tests = %s, status = 'additional_tests_needed' 
            WHERE id = %s
        """, (json.dumps(additional_tests), consultation_id))
        conn.commit()
        return jsonify({'success': True})
    
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/update_test_results', methods=['POST'])
@login_required
def update_test_results():
    """Update test results in MySQL"""
    data = request.json
    consultation_id = data.get('consultation_id')
    test_results = data.get('test_results')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE consultations 
            SET additional_tests_results = %s 
            WHERE id = %s
        """, (json.dumps(test_results), consultation_id))
        conn.commit()
        return jsonify({'success': True})
    
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/update_final_diagnosis', methods=['POST'])
@login_required
def update_final_diagnosis():
    """Update final diagnosis in MySQL"""
    data = request.json
    consultation_id = data.get('consultation_id')
    final_diagnosis = data.get('final_diagnosis')
    direct_validation = data.get('direct_validation', False)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE consultations 
            SET final_diagnosis = %s, status = 'valide', direct_validation = %s 
            WHERE id = %s
        """, (json.dumps(final_diagnosis), direct_validation, consultation_id))
        conn.commit()
        return jsonify({'success': True})
    
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/delete_consultation/<int:consultation_id>', methods=['DELETE'])
@login_required
def delete_consultation(consultation_id):
    """Delete consultation from MySQL"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT image_path FROM consultations WHERE id = %s", (consultation_id,))
        row = cursor.fetchone()
        
        if row and row[0]:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], row[0])
            if os.path.exists(image_path):
                os.remove(image_path)
        
        cursor.execute("DELETE FROM consultations WHERE id = %s", (consultation_id,))
        conn.commit()
        return jsonify({'success': True})
    
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/model-info', methods=['GET'])
@login_required
def model_info():
    """Get model information"""
    model_path = 'models/full_model.pth'
    return jsonify({
        'loaded': model is not None,
        'device': str(DEVICE),
        'classes': CLASS_NAMES,
        'model_path': model_path,
        'model_exists': os.path.exists(model_path),
        'model_source': 'HuggingFace + custom weights'
    })

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============================================
# MAIN
# ============================================
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 PNEUMOANALYST - Application Médicale")
    print("="*50)
    print(f"🤖 Model: {'✅ Loaded' if model else '❌ Not Loaded'}")
    print(f"💾 Device: {DEVICE}")
    print(f"🗄️ Database: MySQL (pfe_medical)")
    print(f"📁 Upload folder: {app.config['UPLOAD_FOLDER']}")
    print("\n🌐 Open in browser: http://localhost:5000")
    print("="*50 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')