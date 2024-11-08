from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token
import bcrypt
from pymongo import MongoClient
import os

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "83114bdeeb269275f27c98dea61244b1e27d495581b516d6c76d4b3d2e1937d8"
jwt = JWTManager(app)

client = MongoClient("mongodb://localhost:27017/")  
db = client['temp_db']  
users_collection = db['Users'] 

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form.get("username")
    password = request.form.get("password")
    mobile = request.form.get("Mobile")
    name = request.form.get("Name")
    address = request.form.get("Address")

    if len(password) < 12:
        return jsonify({"message": "Password is too short"}), 400
    
    if users_collection.find_one({"username": username}):
        return jsonify({"message": "User already exists"}), 409
    
    if name == None or mobile == None or address == None:
        return jsonify({"message": "Please fill all the fields"}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = {"username": username, "password": hashed_password ,"Name": name, "Mobile": mobile, "Address": address}
    users_collection.insert_one(user)

    return jsonify({"message": "User created successfully"}), 201

@app.route('/signin', methods=['POST'])
def signin():
    # data = request.json
    username = request.form.get("username")
    password = request.form.get("password")

    user = users_collection.find_one({"username": username})
    # print(password.encode('utf-8'))
    # print(user)
    # print(user['password'].encode('utf-8'))
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        access_token = create_access_token(identity=username)
        return jsonify({"access_token": access_token}), 200
    else:
        return jsonify({"message": "Invalid username or password"}), 401
    
if __name__ == '__main__':
    app.run(host = "0.0.0.0",port = 4235,debug=False)