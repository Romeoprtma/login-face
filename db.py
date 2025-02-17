import os
import mysql.connector
from urllib.parse import urlparse

def get_db_connection():
    # """Membuat koneksi ke database MySQL menggunakan DATABASE_URL dari environment."""
    # DATABASE_URL = os.environ.get("DATABASE_URL")

    try:
        # # Parsing URL database
        # db_url = urlparse(DATABASE_URL)
        # db_port = db_url.port if db_url.port else 3306  # Default MySQL port

        DB_CONFIG = {
            "host": "localhost",
            "user": "root",
            "password": "",
            "database": "absensi",  # Hapus "/" di awal nama database
            "port": "3306"  # Pastikan port dalam bentuk integer
        }

        if not DB_CONFIG:
            print("❌ DATABASE_URL tidak ditemukan! Pastikan environment variable sudah diatur.")
            return None

        # Membuat koneksi ke database
        conn = mysql.connector.connect(**DB_CONFIG)
        print("✅ Koneksi ke database berhasil!")
        return conn  # Kembalikan koneksi

    except mysql.connector.Error as err:
        print(f"❌ Koneksi gagal: {err}")
        return None  # Kembalikan None jika gagal

# TESTING
if __name__ == "__main__":
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SHOW DATABASES;") 
        for db in cursor.fetchall():
            print(db)
        cursor.close()
        connection.close()  # Tutup koneksi setelah selesai
