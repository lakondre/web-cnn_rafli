import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import mysql.connector
import json
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from sqlalchemy.orm import sessionmaker
from flask_migrate import Migrate
from sqlalchemy import Sequence
from functools import wraps
from datetime import date
from flask import Flask, request, render_template, jsonify, redirect, url_for, session
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask import flash
import os
from keras.models import load_model
from keras_preprocessing.image import load_img, img_to_array
from keras_applications.mobilenet_v2 import preprocess_input, decode_predictions, MobileNetV2
import tensorflow as tf
from skimage import transform, io
import numpy as np
from PIL import Image
from datetime import datetime
from keras.preprocessing import image
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
# Load model for prediction
modelnasnet = load_model("Rafli-pest-95.28.h5")

UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'tiff', 'webp', 'jfif'}
app.config['SECRET_KEY'] = 'andreas12'
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql://root:@localhost/db_mata"
db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

display_id_seq = Sequence('display_id_seq')
migrate = Migrate(app, db)

cnx = mysql.connector.connect(user='root', password='', host='localhost', database='db_mata')
cursor = cnx.cursor()

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'db_mata'

class User(db.Model):
    id_user = db.Column(db.Integer, primary_key=True)
    nm_user = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(200), nullable=False)
    nohp = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(20), nullable=False)
    level = db.Column(db.String(10), nullable=False)


class Riwayat(db.Model):
    id_riwayat = db.Column(db.Integer, primary_key=True)
    id_pasien = db.Column(db.Integer, db.ForeignKey('tb_pasien.id_pasien'), nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    nohp = db.Column(db.String(20), nullable=False)
    tlahir = db.Column(db.String(10), nullable=False)
    tscreen = db.Column(db.String(10), nullable=False)
    diagnosa = db.Column(db.String(50), nullable=False)
    alamat = db.Column(db.String(255), nullable=False)



class Pasien(db.Model):
    id_pasien = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    alamat = db.Column(db.String(200), nullable=False)
    nohp = db.Column(db.String(20), nullable=False)
    tlahir = db.Column(db.Date, nullable=False)

    __tablename__ = 'tb_pasien'



@app.route("/api/pasien/<int:id_pasien>")
def get_pasien_data(id_pasien):
    pasien = Pasien.query.get(id_pasien)
    if pasien:
        return jsonify({"nohp": pasien.nohp, "tlahir": pasien.tlahir.isoformat()})
    return jsonify({"error": "Patient not found"}), 404

def levels_required(*levels):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session or session['level'] not in levels:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/admin')
@levels_required('Admin')
def admin():
    doctors = User.query.filter_by(level='Dokter').count()
    operators = User.query.filter_by(level='Operator').count()
    patients = Pasien.query.count()
    riwayat_count = Riwayat.query.count()
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    return render_template('/admin/index.html',  username=username, level=level, doctors=doctors, operators=operators, patients=patients, riwayat_count=riwayat_count, doctor_name=doctor_name, level_user=level_user)

@app.route('/operator')
@levels_required('Operator')
def operator():
    doctors = User.query.filter_by(level='Dokter').count()
    operators = User.query.filter_by(level='Operator').count()
    patients = Pasien.query.count()
    username = session['username']
    user = User.query.filter_by(username=username).first()
    riwayat_count = Riwayat.query.count()
    doctor_name = user.nm_user
    level_user='Operator'
    return render_template('/operator/index.html', username=session['username'], level=session['level'], doctors=doctors, operators=operators, patients=patients, riwayat_count=riwayat_count, doctor_name=doctor_name, level_user=level_user)

@app.route('/dokter')
@levels_required('Dokter')
def dokter():
    riwayat_count = Riwayat.query.count()
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level_user='Dokter'
    return render_template('/dokter/index.html', username=username, level=session['level'], riwayat_count=riwayat_count, doctor_name=doctor_name, level_user=level_user)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['username'] = user.username
            session['level'] = user.level
            if user.level == 'Admin':
                return redirect(url_for('admin'))
            elif user.level == 'Operator':
                return redirect(url_for('operator'))
            elif user.level == 'Dokter':
                return redirect(url_for('dokter'))
            else:
                return 'Invalid level', 401
        else:
            return '''
                <script>
                alert("Username atau Password salah!");
                window.location.href = "/";
            </script>
            '''
    return render_template('/index.html')


@app.route("/classification", methods=['GET', 'POST'])
def classification():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    return render_template("/admin/classifications.html", doctor_name=doctor_name, level_user=level_user)

@app.route("/classification1", methods=['GET', 'POST'])
def classification1():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Operstor'
    return render_template("/operator/classifications.html", doctor_name=doctor_name, level_user=level_user)

@app.route("/riwayat", methods=['GET', 'POST'])
@levels_required('Admin')
def riwayat():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    try :
        cursor.execute("SELECT * FROM riwayat")
        riwayats = cursor.fetchall()
        output = []
        for riwayat in riwayats:
            output.append({
                'id_riwayat': riwayat[0],
                'id_pasien': riwayat[1],
                'nama': riwayat[2],
                'nohp': riwayat[3],
                'tlahir': riwayat[4],
                'tscreen': riwayat[5],
                'diagnosa': riwayat[6],
                'alamat': riwayat[7]
            })  # Check if data is being processed correctly
        return render_template("/admin/riwayat.html", riwayats=output, doctor_name=doctor_name, level=level, level_user=level_user)
    except mysql.connector.Error as err:
        print("Error:", err)  # Check for database errors
        return "Error fetching data"

@app.route("/riwayat2", methods=['GET', 'POST'])
def riwayat2():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Dokter'
    try :
        cursor.execute("SELECT * FROM riwayat")
        riwayats = cursor.fetchall()
        output = []
        for riwayat in riwayats:
            output.append({
                'id_riwayat': riwayat[0],
                'id_pasien': riwayat[1],
                'nama': riwayat[2],
                'nohp': riwayat[3],
                'tlahir': riwayat[4],
                'tscreen': riwayat[5],
                'diagnosa': riwayat[6],
                'alamat': riwayat[7]
            })  # Check if data is being processed correctly
        return render_template("/dokter/riwayat.html", riwayats=output, doctor_name=doctor_name, level=level, level_user=level_user)
    except mysql.connector.Error as err:
        print("Error:", err)  # Check for database errors
        return "Error fetching data"

@app.route("/riwayat1", methods=['GET', 'POST'])
def riwayat1():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Operator'
    try :
        cursor.execute("SELECT * FROM riwayat")
        riwayats = cursor.fetchall()
        output = []
        for riwayat in riwayats:
            output.append({
                'id_riwayat': riwayat[0],
                'id_pasien': riwayat[1],
                'nama': riwayat[2],
                'nohp': riwayat[3],
                'tlahir': riwayat[4],
                'tscreen': riwayat[5],
                'diagnosa': riwayat[6],
                'alamat': riwayat[7]
            })  # Check if data is being processed correctly
        return render_template("/operator/riwayat.html", riwayats=output, doctor_name=doctor_name, level=level, level_user=level_user)
    except mysql.connector.Error as err:
        print("Error:", err)  # Check for database errors
        return "Error fetching data"
    
@app.route("/pengguna", methods=['GET', 'POST'])
@levels_required('Admin')
def pengguna():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    try :
        cursor.execute("SELECT * FROM user")
        users = cursor.fetchall()
        output = []
        for user in users:
            output.append({
                'id_user': user[0],
                'nm_user': user[1],
                'username': user[2],
                'nohp': user[3],
                'level': user[5]
            })  # Check if data is being processed correctly
        return render_template("/admin/pengguna.html", users=output, doctor_name=doctor_name, level=level, level_user=level_user)
    except mysql.connector.Error as err:
        print("Error:", err)  # Check for database errors
        return "Error fetching data"

@app.route("/pasien", methods=['GET', 'POST'])
@levels_required('Admin')
def pasien():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    try:
        cursor.execute("SELECT * FROM tb_pasien")
        pasiens = cursor.fetchall()
        output = []
        for pasien in pasiens:
            output.append({
                'id_pasien':pasien[0],
                'nama': pasien[1],
                'alamat': pasien[2],
                'nohp': pasien[3],
                'tlahir': pasien[4]
            })
        return render_template("/admin/pasien.html", pasiens=output,  doctor_name=doctor_name, level=level, level_user=level_user)
    except mysql.connector.Error as err:
        return "error fetching data"


@app.route("/pasien1", methods=['GET', 'POST'])
def pasien1():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Operator'
    try:
        cursor.execute("SELECT * FROM tb_pasien")
        pasiens = cursor.fetchall()
        output = []
        for pasien in pasiens:
            output.append({
                'id_pasien':pasien[0],
                'nama': pasien[1],
                'alamat': pasien[2],
                'nohp': pasien[3],
                'tlahir': pasien[4]
            })
        return render_template("/operator/pasien.html", pasiens=output,  doctor_name=doctor_name, level=level, level_user=level_user)
    except mysql.connector.Error as err:
        return "error fetching data"

@app.route("/tambahpasien", methods=["GET", "POST"])
def tambahpasien():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    if request.method == 'POST':
        nama = request.form.get('nama')
        alamat = request.form.get('alamat')
        nohp = request.form.get('nohp')
        tlahir = request.form.get('tlahir')

        pasien = Pasien(nama=nama, alamat=alamat, nohp=nohp, tlahir=tlahir)
        db.session.add(pasien)
        db.session.commit()

        return '''
        <script>
            alert("Data berhasil disimpan!");
            window.location.href = "/pasien";
        </script>
        '''
    pasien = Pasien.query.all()
    return render_template("/admin/tambahpasien.html", pasien=pasien, doctor_name=doctor_name, level=level, level_user=level_user)

@app.route("/tambahpasien1", methods=["GET", "POST"])
def tambahpasien1():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    if request.method == 'POST':
        nama = request.form.get('nama')
        alamat = request.form.get('alamat')
        nohp = request.form.get('nohp')
        tlahir = request.form.get('tlahir')

        pasien = Pasien(nama=nama, alamat=alamat, nohp=nohp, tlahir=tlahir)
        db.session.add(pasien)
        db.session.commit()

        return '''
        <script>
            alert("Data berhasil disimpan!");
            window.location.href = "/pasien";
        </script>
        '''
    pasien = Pasien.query.all()
    return render_template("/operator/tambahpasien.html", pasien=pasien, doctor_name=doctor_name, level=level, level_user=level_user)

@app.route('/hapusriwayat/<int:id_riwayat>', methods=['DELETE'])
def hapusriwayat(id_riwayat):
    riwayat = Riwayat.query.get(id_riwayat)
    db.session.delete(riwayat)
    db.session.commit()
    return jsonify({'success': True, 'message': 'data pengguna deleted successfully'})

@app.route('/hapusriwayat2/<int:id_riwayat>', methods=['DELETE'])
def hapusriwayat2(id_riwayat):
    riwayat = Riwayat.query.get(id_riwayat)
    db.session.delete(riwayat)
    db.session.commit()
    return jsonify({'success': True, 'message': 'data pengguna deleted successfully'})


@app.route('/hapusriwayat1/<int:id_riwayat>', methods=['DELETE'])
def hapusriwayat1(id_riwayat):
    riwayat = Riwayat.query.get(id_riwayat)
    if riwayat is None:
        return jsonify({'success': False, 'message': 'Riwayat not found'}), 404
    db.session.delete(riwayat)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Riwayat deleted successfully'}), 200


@app.route('/hapuspasien/<int:id_pasien>', methods=['DELETE'])
def hapuspasien(id_pasien):
    pasien = Pasien.query.get(id_pasien)
    db.session.delete(pasien)
    db.session.commit()
    return jsonify({'success': True, 'message': 'data pasien deleted successfully'})

@app.route('/hapuspasien1/<int:id_pasien>', methods=['DELETE'])
def hapuspasien1(id_pasien):
    pasien = Pasien.query.get(id_pasien)
    if pasien is None:
        return jsonify({'success': False, 'essage': 'Pasien not found'})
    db.session.delete(pasien)
    db.session.commit()
    return jsonify({'success': True, 'essage': 'Pasien deleted successfully'})

@app.route('/editpasien/<int:id_pasien>', methods=['GET', 'POST'])
@levels_required('Admin')
def editpasien(id_pasien):
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    try:
        cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
        cur = cnx.cursor()
        if request.method == 'POST':
            # Get the updated values from the form
            nama = request.form['nama']
            alamat = request.form['alamat']
            nohp = request.form['nohp']
            tlahir = request.form['tlahir']

            # Update the user data in the database
            cur.execute("UPDATE tb_pasien SET nama = %s, alamat = %s, nohp = %s, tlahir = %s WHERE id_pasien = %s", (nama, alamat, nohp, tlahir, id_pasien))
            cnx.commit()

            # Close the cursor and connection
            cur.close()
            cnx.close()

            # Redirect to a success page or display a success message
            return '''
                <script>
                alert("Data berhasil disimpan!");
                window.location.href = "/pasien";
            </script>
            '''

        else :
            cur.execute("SELECT * FROM tb_pasien WHERE id_pasien = %s", (id_pasien,))
            pasien_tuple = cur.fetchone()
            user_dict = {
                'id_pasien': pasien_tuple[0],
                'nama': pasien_tuple[1],
                'alamat': pasien_tuple[2],
                'nohp' : pasien_tuple[3],
                'tlahir' : pasien_tuple[4],
                }

        cur.close()
        cnx.close()

        # Return the user data
        return render_template('/admin/edit_pasien.html', pasien=user_dict, doctor_name=doctor_name, level=level, level_user=level_user)


    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return "Error fetching user data", 500

@app.route('/editpasien1/<int:id_pasien>', methods=['GET', 'POST'])
def editpasien1(id_pasien):
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user=level
    try:
        cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
        cur = cnx.cursor()
        if request.method == 'POST':
            # Get the updated values from the form
            nama = request.form['nama']
            alamat = request.form['alamat']
            nohp = request.form['nohp']
            tlahir = request.form['tlahir']

            # Update the user data in the database
            cur.execute("UPDATE tb_pasien SET nama = %s, alamat = %s, nohp = %s, tlahir = %s WHERE id_pasien = %s", (nama, alamat, nohp, tlahir, id_pasien))
            cnx.commit()

            # Close the cursor and connection
            cur.close()
            cnx.close()

            # Redirect to a success page or display a success message
            return '''
                <script>
                alert("Data berhasil disimpan!");
                window.location.href = "/pasien1";
            </script>
            '''

        else :
            cur.execute("SELECT * FROM tb_pasien WHERE id_pasien = %s", (id_pasien,))
            pasien_tuple = cur.fetchone()
            user_dict = {
                'id_pasien': pasien_tuple[0],
                'nama': pasien_tuple[1],
                'alamat': pasien_tuple[2],
                'nohp' : pasien_tuple[3],
                'tlahir' : pasien_tuple[4],
                }

        cur.close()
        cnx.close()

        # Return the user data
        return render_template('/operator/edit_pasien.html', pasien=user_dict, doctor_name=doctor_name, level=level, level_user=level_user)


    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return "Error fetching user data", 500


@app.route('/save_riwayat', methods=['POST'])
def save_riwayat():
    id_pasien = request.form['id_pasien']
    nama_pasien = request.form['nama_pasien']
    nohp = request.form['nohp']
    tlahir = request.form['tlahir']
    tscreen = request.form['tscreen']
    diagnosis = request.form['diagnosis']
    alamat = request.form['alamat']

    cursor.execute("INSERT INTO riwayat (id_pasien, nama, nohp, tlahir, tscreen, diagnosa, alamat) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                   (id_pasien, nama_pasien, nohp, tlahir, tscreen, diagnosis, alamat))
    cnx.commit()

    return '''
        <script>
            alert("Data berhasil disimpan!");
            window.location.href = "/classification";
        </script>
    '''

@app.route('/save_riwayat2', methods=['POST'])
def save_riwayat2():
    id_pasien = request.form['id_pasien']
    nama_pasien = request.form['nama_pasien']
    nohp = request.form['nohp']
    tlahir = request.form['tlahir']
    tscreen = request.form['tscreen']
    diagnosis = request.form['diagnosis']
    alamat = request.form['alamat']

    cursor.execute("INSERT INTO riwayat (id_pasien, nama, nohp, tlahir, tscreen, diagnosa, alamat) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                   (id_pasien, nama_pasien, nohp, tlahir, tscreen, diagnosis, alamat))
    cnx.commit()

    return '''
        <script>
            alert("Data berhasil disimpan!");
            window.location.href = "/classification2";
        </script>
    '''

@app.route('/save_riwayat1', methods=['POST'])
def save_riwayat1():
    id_pasien = request.form['id_pasien']
    nama_pasien = request.form['nama_pasien']
    nohp = request.form['nohp']
    tlahir = request.form['tlahir']
    tscreen = request.form['tscreen']
    diagnosis = request.form['diagnosis']
    alamat = request.form['alamat']

    cursor.execute("INSERT INTO riwayat (id_pasien, nama, nohp, tlahir, tscreen, diagnosa, alamat) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                   (id_pasien, nama_pasien, nohp, tlahir, tscreen, diagnosis, alamat))
    cnx.commit()

    return '''
        <script>
            alert("Data berhasil disimpan!");
            window.location.href = "/classification1";
        </script>
    '''

@app.route("/tambahpengguna", methods=["GET", "POST"])
@levels_required('Admin')
def tambahpengguna():
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    if request.method == "POST":
        nama = request.form["nama"]
        username = request.form["username"]
        nohp = request.form["nohp"]
        user_password = request.form["password"]
        level = request.form["level"]

        cursor.execute("INSERT INTO user ( nm_user, username, nohp, password, level) VALUES (%s, %s, %s, %s, %s)",
                   (nama, username, nohp, user_password, level))
        cnx.commit()

        return '''
        <script>
            alert("Data berhasil disimpan!");
            window.location.href = "/pengguna";
        </script>
        '''

    users = User.query.all()
    return render_template("/admin/tambahpengguna.html", user=users, doctor_name=doctor_name, level=level, level_user=level_user)



@app.route('/edit_user/<int:id_user>', methods=['GET', 'POST'])
@levels_required('Admin')
def edit_user(id_user):
    username = session['username']
    user = User.query.filter_by(username=username).first()
    doctor_name = user.nm_user
    level=session['level']
    level_user='Administrator'
    try:
        cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
        cur = cnx.cursor()
        if request.method == 'POST':
            # Get the updated values from the form
            nm_user = request.form['nama']
            username = request.form['username']
            nohp = request.form['nohp']
            password = request.form['password']
            level = request.form['level']

            # Update the user data in the database
            cur.execute("UPDATE user SET nm_user = %s, username = %s, nohp = %s, password = %s, level = %s WHERE id_user = %s", (nm_user, username, nohp, password, level, id_user))
            cnx.commit()

            # Close the cursor and connection
            cur.close()
            cnx.close()

            # Flash a success message and redirect back to the pengguna page
 
            return '''
                <script>
                alert("Data berhasil dirubah!");
                window.location.href = "/pengguna";
                </script>
                '''

        else :
            cur.execute("SELECT * FROM user WHERE id_user = %s", (id_user,))
            user_tuple = cur.fetchone()
            user_dict = {
                'id_user': user_tuple[0],
                'nm_user': user_tuple[1],
                'username': user_tuple[2],
                'nohp' : user_tuple[3],
                'password' : user_tuple[4],
                'level' : user_tuple[5],
                }

        cur.close()
        cnx.close()

        # Return the user data
        return render_template('/admin/edit_user.html', user=user_dict, doctor_name=doctor_name, level=level, level_user=level_user)

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return "Error fetching user data", 500
    

    
@app.route('/hapuspengguna/<int:id_user>', methods=['DELETE'])
@levels_required('Admin')
def hapuspengguna(id_user):
    user = User.query.get(id_user)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'data pengguna deleted successfully'})

@app.route("/edit_riwayat/<int:id_riwayat>", methods=['GET', 'POST'])
@levels_required('Admin')
def edit_riwayat(id_riwayat):
    try:
        cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
        cur = cnx.cursor()
        if request.method == 'POST':
            # Get the updated values from the form
            id_pasien = request.form['id_pasien']
            nama = request.form['nama']
            nohp = request.form['nohp']
            tlahir = request.form['tlahir']
            tscreen = request.form['tscreen']
            diagnosa = request.form['diagnosa']
            alamat = request.form['alamat']

            # Update the user data in the database
            cur.execute("UPDATE riwayat SET id_pasien = %s, nama = %s, nohp = %s, tlahir = %s, tscreen = %s, diagnosa = %s, alamat = %s WHERE id_riwayat = %s", (id_pasien, nama, nohp, tlahir, tscreen, diagnosa, alamat, id_riwayat))
            cnx.commit()

            # Close the cursor and connection
            cur.close()
            cnx.close()

            # Redirect to a success page or display a success message
            return redirect(url_for('riwayat'))

        else :
            cur.execute("SELECT * FROM riwayat WHERE id_riwayat = %s", (id_riwayat,))
            riwayat_tuple = cur.fetchone()
            riwayat_dict = {
                'id_riwayat': riwayat_tuple[0],
                'id_pasien': riwayat_tuple[1],
                'nama': riwayat_tuple[2],
                'nohp': riwayat_tuple[3],
                'tlahir': riwayat_tuple[4],
                'tscreen': riwayat_tuple[5],
                'diagnosa': riwayat_tuple[6],
                'alamat': riwayat_tuple[7]
                }

        cur.close()
        cnx.close()

        # Return the user data
        return render_template('/admin/edit_riwayat.html', riwayat=riwayat_dict)

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return "Error fetching user data", 500

@app.route("/edit_riwayat2/<int:id_riwayat>", methods=['GET', 'POST'])
def edit_riwayat2(id_riwayat):
    try:
        cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
        cur = cnx.cursor()
        if request.method == 'POST':
            # Get the updated values from the form
            id_pasien = request.form['id_pasien']
            nama = request.form['nama']
            nohp = request.form['nohp']
            tlahir = request.form['tlahir']
            tscreen = request.form['tscreen']
            diagnosa = request.form['diagnosa']
            alamat = request.form['alamat']

            # Update the user data in the database
            cur.execute("UPDATE riwayat SET id_pasien = %s, nama = %s, nohp = %s, tlahir = %s, tscreen = %s, diagnosa = %s, alamat = %s WHERE id_riwayat = %s", (id_pasien, nama, nohp, tlahir, tscreen, diagnosa, alamat, id_riwayat))
            cnx.commit()

            # Close the cursor and connection
            cur.close()
            cnx.close()

            # Redirect to a success page or display a success message
            return redirect(url_for('riwayat2'))

        else :
            cur.execute("SELECT * FROM riwayat WHERE id_riwayat = %s", (id_riwayat,))
            riwayat_tuple = cur.fetchone()
            riwayat_dict = {
                'id_riwayat': riwayat_tuple[0],
                'id_pasien': riwayat_tuple[1],
                'nama': riwayat_tuple[2],
                'nohp': riwayat_tuple[3],
                'tlahir': riwayat_tuple[4],
                'tscreen': riwayat_tuple[5],
                'diagnosa': riwayat_tuple[6],
                'alamat': riwayat_tuple[7]
                }

        cur.close()
        cnx.close()

        # Return the user data
        return render_template('/dokter/edit_riwayat.html', riwayat=riwayat_dict)

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return "Error fetching user data", 500

@app.route("/cetakriwayat/<int:id_riwayat>", methods=['GET', 'POST'])
def cetak_riwayat(id_riwayat):
    current_date = date.today().strftime("%d-%m-%Y")
    cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
    cur = cnx.cursor()
    cur.execute("SELECT * FROM riwayat WHERE id_riwayat = %s", (id_riwayat,))
    riwayat_tuple = cur.fetchone()
    riwayat_dict = {
            'id_riwayat': riwayat_tuple[0],
            'id_pasien': riwayat_tuple[1],
            'nama': riwayat_tuple[2],
            'nohp': riwayat_tuple[3],
            'tlahir': riwayat_tuple[4],
            'tscreen': riwayat_tuple[5],
            'diagnosa': riwayat_tuple[6],
            'alamat' : riwayat_tuple[7]
            }
    # Fetch all results before closing the cursor and connection
    cur.fetchall()  # Add this line to fetch all results
    cur.close()
    cnx.close()
    return render_template('/admin/print_riwayat.html', riwayat=riwayat_dict, current_date=current_date)    

@app.route("/cetakriwayat2/<int:id_riwayat>", methods=['GET', 'POST'])
def cetak_riwayat2(id_riwayat):
    current_date = date.today().strftime("%d-%m-%Y")
    cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
    cur = cnx.cursor()
    cur.execute("SELECT * FROM riwayat WHERE id_riwayat = %s", (id_riwayat,))
    riwayat_tuple = cur.fetchone()
    riwayat_dict = {
            'id_riwayat': riwayat_tuple[0],
            'id_pasien': riwayat_tuple[1],
            'nama': riwayat_tuple[2],
            'nohp': riwayat_tuple[3],
            'tlahir': riwayat_tuple[4],
            'tscreen': riwayat_tuple[5],
            'diagnosa': riwayat_tuple[6],
            'alamat' : riwayat_tuple[7]
            }
    # Fetch all results before closing the cursor and connection
    cur.fetchall()  # Add this line to fetch all results
    cur.close()
    cnx.close()
    return render_template('/dokter/print_riwayat.html', riwayat=riwayat_dict, current_date=current_date)    

@app.route("/edit_riwayatop/<int:id_riwayat>", methods=['GET', 'POST'])
def edit_riwayatop(id_riwayat):
    try:
        cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
        cur = cnx.cursor()
        if request.method == 'POST':
            # Get the updated values from the form
            id_pasien = request.form['id_pasien']
            nama = request.form['nama']
            nohp = request.form['nohp']
            tlahir = request.form['tlahir']
            tscreen = request.form['tscreen']
            diagnosa = request.form['diagnosa']
            alamat = request.form['alamat']

            # Update the user data in the database
            cur.execute("UPDATE riwayat SET id_pasien = %s, nama = %s, nohp = %s, tlahir = %s, tscreen = %s, diagnosa = %s, alamat = %s WHERE id_riwayat = %s", (id_pasien, nama, nohp, tlahir, tscreen, diagnosa, alamat, id_riwayat))
            cnx.commit()

            # Close the cursor and connection
            cur.close()
            cnx.close()

            # Redirect to a success page or display a success message
            return '''
        <script>
            alert("Data berhasil disimpan!");
            window.location.href = "/riwayat";
        </script>
        '''

        else :
            cur.execute("SELECT * FROM riwayat WHERE id_riwayat = %s", (id_riwayat,))
            riwayat_tuple = cur.fetchone()
            riwayat_dict = {
                'id_riwayat': riwayat_tuple[0],
                'id_pasien': riwayat_tuple[1],
                'nama': riwayat_tuple[2],
                'nohp': riwayat_tuple[3],
                'tlahir': riwayat_tuple[4],
                'tscreen': riwayat_tuple[5],
                'diagnosa': riwayat_tuple[6],
                'alamat': riwayat_tuple[7]
                }

        cur.close()
        cnx.close()

        # Return the user data
        return render_template('/operator/edit_riwayat.html', riwayat=riwayat_dict)

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return "Error fetching user data", 500
    
@app.route("/cetakriwayat1/<int:id_riwayat>", methods=['GET', 'POST'])
def cetak_riwayat1(id_riwayat):
    current_date = date.today().strftime("%d-%m-%Y")
    cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
    cur = cnx.cursor()
    cur.execute("SELECT * FROM riwayat WHERE id_riwayat = %s", (id_riwayat,))
    riwayat_tuple = cur.fetchone()
    riwayat_dict = {
            'id_riwayat': riwayat_tuple[0],
            'id_pasien': riwayat_tuple[1],
            'nama': riwayat_tuple[2],
            'nohp': riwayat_tuple[3],
            'tlahir': riwayat_tuple[4],
            'tscreen': riwayat_tuple[5],
            'diagnosa': riwayat_tuple[6],
            'alamat' : riwayat_tuple[7]
            }
    # Fetch all results before closing the cursor and connection
    cur.fetchall()  # Add this line to fetch all results
    cur.close()
    cnx.close()
    return render_template('/operator/print_riwayat.html', riwayat=riwayat_dict, current_date=current_date)    

@app.route("/edit_riwayat1/<int:id_riwayat>", methods=['GET', 'POST'])
def edit_riwayat1(id_riwayat):
    try:
        cnx = mysql.connector.connect(
            user='root',
            password='',
            host='localhost',
            database='db_mata'
        )
        cur = cnx.cursor()
        if request.method == 'POST':
            # Get the updated values from the form
            id_pasien = request.form['id_pasien']
            nama = request.form['nama']
            nohp = request.form['nohp']
            tlahir = request.form['tlahir']
            tscreen = request.form['tscreen']
            diagnosa = request.form['diagnosa']
            alamat = request.form['alamat']

            # Update the user data in the database
            cur.execute("UPDATE riwayat SET id_pasien = %s, nama = %s, nohp = %s, tlahir = %s, tscreen = %s, diagnosa = %s, alamat = %s WHERE id_riwayat = %s", (id_pasien, nama, nohp, tlahir, tscreen, diagnosa, alamat, id_riwayat))
            cnx.commit()

            # Close the cursor and connection
            cur.close()
            cnx.close()

            # Redirect to a success page or display a success message
            return redirect(url_for('riwayat'))

        else :
            cur.execute("SELECT * FROM riwayat WHERE id_riwayat = %s", (id_riwayat,))
            riwayat_tuple = cur.fetchone()
            riwayat_dict = {
                'id_riwayat': riwayat_tuple[0],
                'id_pasien': riwayat_tuple[1],
                'nama': riwayat_tuple[2],
                'nohp': riwayat_tuple[3],
                'tlahir': riwayat_tuple[4],
                'tscreen': riwayat_tuple[5],
                'diagnosa': riwayat_tuple[6],
                'alamat': riwayat_tuple[7]
                }

        cur.close()
        cnx.close()

        # Return the user data
        return render_template('/operator/edit_riwayat.html', riwayat=riwayat_dict)

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return "Error fetching user data", 500

@app.route('/submit', methods=['POST'])
def predict():
    current_date = date.today()
    if 'file' not in request.files:
        resp = jsonify({'message': 'No image in the request'})
        resp.status_code = 400
        return resp
    files = request.files.getlist('file')
    filename = "temp_image.png"
    errors = {}
    success = False
    for file in files:
        if file and allowed_file(file.filename):
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
            nama_pasien = request.form['nama_pasien']
            cursor.execute("SELECT * FROM tb_pasien WHERE nama =%s", (nama_pasien,))
            pasien_data = cursor.fetchone()
            
            if pasien_data:
                id_pasien = pasien_data[0]
                nama_pasien = pasien_data[1]
                alamat = pasien_data[2]
                nohp = pasien_data[3]
                tlahir = pasien_data[4]
                success = True
            else:
                return 'Nama Pasien tidak ditemukan'

    if not success:
        resp = jsonify(errors)
        resp.status_code = 400
        return resp
    img_url = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Convert image to RGB
    img = Image.open(img_url).convert('RGB')
    now = datetime.now()
    predict_image_path = 'static/uploads/' + now.strftime("%d%m%y-%H%M%S") + ".png"
    image_predict = predict_image_path
    img.convert('RGB').save(image_predict, format="png")
    img.close()

    # Prepare image for prediction
    img = image.load_img(predict_image_path, target_size=(128, 128, 3))
    x = image.img_to_array(img)
    x = x / 127.5 - 1
    x = np.expand_dims(x, axis=0)
    images = np.vstack([x])

    # Predict
    prediction_array_nasnet = modelnasnet.predict(images)

    # Prepare API response
    class_names = ['Katarak', 'Normal']

    return render_template("/admin/classifications.html", 
                           img_path=predict_image_path, 
                           predictionnasnet=class_names[np.argmax(prediction_array_nasnet)],
                           confidencenasnet='{:.2f}%'.format(100 * np.max(prediction_array_nasnet)),
                           nama_pasien=nama_pasien, id_pasien=id_pasien, alamat=alamat, nohp=nohp, tlahir=tlahir, current_date=current_date)


@app.route('/submit1', methods=['POST'])
def predict1():
    current_date = date.today()
    if 'file' not in request.files:
        resp = jsonify({'message': 'No image in the request'})
        resp.status_code = 400
        return resp
    files = request.files.getlist('file')
    filename = "temp_image.png"
    errors = {}
    success = False
    for file in files:
        if file and allowed_file(file.filename):
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
            nama_pasien = request.form['nama_pasien']
            cursor.execute("SELECT * FROM tb_pasien WHERE nama =%s", (nama_pasien,))
            pasien_data = cursor.fetchone()
            
            if pasien_data:
                id_pasien = pasien_data[0]
                nama_pasien = pasien_data[1]
                alamat = pasien_data[2]
                nohp = pasien_data[3]
                tlahir = pasien_data[4]
                success = True
            else:
                return 'Nama Pasien tidak ditemukan'

    if not success:
        resp = jsonify(errors)
        resp.status_code = 400
        return resp
    img_url = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Convert image to RGB
    img = Image.open(img_url).convert('RGB')
    now = datetime.now()
    predict_image_path = 'static/uploads/' + now.strftime("%d%m%y-%H%M%S") + ".png"
    image_predict = predict_image_path
    img.convert('RGB').save(image_predict, format="png")
    img.close()

    # Prepare image for prediction
    img = image.load_img(predict_image_path, target_size=(128, 128, 3))
    x = image.img_to_array(img)
    x = x / 127.5 - 1
    x = np.expand_dims(x, axis=0)
    images = np.vstack([x])

    # Predict
    prediction_array_nasnet = modelnasnet.predict(images)

    # Prepare API response
    class_names = ['Katarak', 'Normal']

    return render_template("/operator/classifications.html", 
                           img_path=predict_image_path, 
                           predictionnasnet=class_names[np.argmax(prediction_array_nasnet)],
                           confidencenasnet='{:.2f}%'.format(100 * np.max(prediction_array_nasnet)),
                           nama_pasien=nama_pasien, id_pasien=id_pasien, alamat=alamat, nohp=nohp, tlahir=tlahir, current_date=current_date)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)
