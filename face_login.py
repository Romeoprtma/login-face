from flask import Flask, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
import cv2
import face_recognition
import pickle
import base64
import numpy as np
from pytz import timezone
import pytz
from datetime import datetime
import bcrypt
from db import get_db_connection

app = Flask(__name__)
app.secret_key = "supersecretkey"

CORS(app, supports_credentials=True)

login_manager = LoginManager()
login_manager.init_app(app)

jakarta_tz = timezone("Asia/Jakarta")

class User(UserMixin):
    def __init__(self, id, username, nis, role):
        self.id = id
        self.username = username
        self.nis = nis
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nis, role FROM users WHERE user_id = %s", (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user_data:
        return User(*user_data)  # Auto-unpack data
    return None

def authenticate_user(image_base64, identifier, password):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Cari user berdasarkan NIS atau username
        cursor.execute("SELECT user_id, username, nis, role, face_encoding, password FROM users WHERE nis = %s OR username = %s", (identifier, identifier))
        user = cursor.fetchone()

        if not user:
            return {"status": "error", "message": "Pengguna tidak ditemukan"}

        user_id, username, nis, role, encoding, hashed_password = user

        # Verifikasi password menggunakan bcrypt
        if not bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
            return {"status": "error", "message": "Password salah"}

        # Decode gambar untuk face recognition
        img_data = base64.b64decode(image_base64)
        np_img = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Cek apakah encoding wajah tersedia
        if not encoding:
            return {"status": "error", "message": "Data wajah tidak tersedia, silakan daftar"}

        known_encodings = [pickle.loads(encoding)]

        # Proses face recognition
        face_encodings = face_recognition.face_encodings(frame)
        if not face_encodings:
            return {"status": "error", "message": "Wajah tidak terdeteksi"}

        # Bandingkan wajah yang dikenali dengan yang ada di database
        matches = face_recognition.compare_faces(known_encodings, face_encodings[0], tolerance=0.4)
        face_distances = face_recognition.face_distance(known_encodings, face_encodings[0])
        best_match_index = np.argmin(face_distances) if face_distances.size > 0 else None

        if best_match_index is not None and matches[best_match_index]:
            login_time = datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')

            # Simpan log login
            cursor.execute("INSERT INTO login_logs (user_id, login_time) VALUES (%s, %s)", (user_id, login_time))
            conn.commit()

            return {
                "status": "success",
                "message": "Login berhasil",
                "user_id": user_id,
                "name": username,
                "nis": nis,
                "role": role,  # Role otomatis terdeteksi
                "login_time": login_time
            }
        
        return {"status": "register", "message": "Wajah tidak dikenali, silakan daftar"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    image_base64 = data.get("image_base64")
    identifier = data.get("identifier")
    password = data.get("password")
    
    if not image_base64 or not identifier or not password:
        return jsonify({"status": "error", "message": "Data tidak lengkap"})
    
    # Tidak perlu decode password karena tidak di-hash
    result = authenticate_user(image_base64, identifier, password)
    return jsonify(result)

@app.route('/register_face', methods=['POST'])
def register_face():
    data = request.json
    image_base64_list = data.get("image_base64")  # Mengharapkan list dari 5 gambar
    identifier = data.get("identifier")
    role = data.get("role")
    
    if not image_base64_list or len(image_base64_list) != 5 or not identifier or not role:
        return jsonify({"status": "error", "message": "Data tidak lengkap atau jumlah gambar tidak mencukupi"})
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Cari user berdasarkan nis (siswa) atau username (admin/guru)
        if role == "siswa":
            cursor.execute("SELECT user_id, face_encoding FROM users WHERE nis = %s AND role = 'siswa'", (identifier,))
        else:
            cursor.execute("SELECT user_id, face_encoding FROM users WHERE username = %s AND role = %s", (identifier, role))
        
        user_data = cursor.fetchone()
        
        if not user_data:
            return jsonify({"status": "error", "message": "User tidak ditemukan"})
        
        user_id, existing_encoding = user_data
        
        # Cek apakah wajah sudah diregistrasi
        if existing_encoding is not None:
            return jsonify({"status": "error", "message": "Wajah sudah terdaftar, tidak bisa registrasi ulang"})
        
        # Proses encoding wajah
        encodings = []
        for image_base64 in image_base64_list:
            img_data = base64.b64decode(image_base64)
            np_img = np.frombuffer(img_data, np.uint8)
            frame = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            face_encodings = face_recognition.face_encodings(frame)
            if not face_encodings:
                return jsonify({"status": "error", "message": "Wajah tidak terdeteksi dalam salah satu gambar"})
            
            encodings.append(pickle.dumps(face_encodings[0]))
        
        # Simpan 5 encoding wajah ke database
        cursor.execute("""
            UPDATE users 
            SET face_encoding = %s, 
                face_encoding2 = %s, 
                face_encoding3 = %s, 
                face_encoding4 = %s, 
                face_encoding5 = %s 
            WHERE user_id = %s
        """, (encodings[0], encodings[1], encodings[2], encodings[3], encodings[4], user_id))
        conn.commit()
        
        return jsonify({"status": "success", "message": "Wajah berhasil diregistrasi"})
    
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
    
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
