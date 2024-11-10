from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from flask_jwt_extended import JWTManager, create_access_token
from flask_cors import CORS
import bcrypt


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "83114bdeeb269275f27c98dea61244b1e27d495581b516d6c76d4b3d2e1937d8"
jwt = JWTManager(app)
# Enable CORS for cross-origin requests
CORS(app)

# MongoDB setup
connection_string = "mongodb+srv://court-metrics:k2vCw0PaWW2v7k7N@cluster0.tqzmo.mongodb.net/"
client = MongoClient(connection_string)
db = client['courtmetrics_db']
users_collection = db['Users']

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        # Find the user in the database
        user = users_collection.find_one({"username": username})

        # Verify user and password
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            # Generate access token
            access_token = create_access_token(identity=username)
            return jsonify({"access_token": access_token}), 200
        else:
            return jsonify({"message": "Invalid username or password"}), 401

    # Render the signin form for GET request
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        mobile = request.form.get("mobile")
        name = request.form.get("name")
        address = request.form.get("address")

        # Validate password length
        if len(password) < 12:
            return jsonify({"message": "Password is too short"}), 400

        # Check if the user already exists
        if users_collection.find_one({"username": username}):
            return jsonify({"message": "User already exists"}), 409

        # Ensure required fields are not empty
        if not all([username, password, mobile, name, address]):
            return jsonify({"message": "Please fill all the fields"}), 400

        # Hash the password and save user data
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = {"username": username, "password": hashed_password, "Name": name, "Mobile": mobile, "Address": address}

        # Insert user into database
        users_collection.insert_one(user)
        return jsonify({"message": "User created successfully"}), 201

    # Render the signup form for GET request
    return render_template('signup.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=4235, debug=True)
