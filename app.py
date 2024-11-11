from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from flask_jwt_extended import JWTManager, create_access_token
from flask_cors import CORS
import bcrypt
import nba_api
from nba_api.live.nba.endpoints import scoreboard


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "83114bdeeb269275f27c98dea61244b1e27d495581b516d6c76d4b3d2e1937d8"
jwt = JWTManager(app)
# Enable CORS for cross-origin requests
CORS(app)

# MongoDB setup
client = MongoClient("mongodb+srv://court-metrics:k2vCw0PaWW2v7k7N@cluster0.tqzmo.mongodb.net/")
db = client['courtmetrics_db']
users_collection = db['Users']

@app.route('/')
def home():
    
    games = scoreboard.ScoreBoard()
    games_dict = games.get_dict()

    
    live_scores = []
    completed_match_summary = None

    for game in games_dict['scoreboard']['games']:
        home_team = game['homeTeam']['teamName']
        away_team = game['awayTeam']['teamName']
        home_score = game['homeTeam']['score']
        away_score = game['awayTeam']['score']

        
        if game['gameStatusText'] == 'Final':
            completed_match_summary = {
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'summary': f"In an intense showdown, {home_team} faced off against {away_team}. The final score was {home_team} {home_score} - {away_team} {away_score}. It was a thrilling match with key plays from both teams."
            }

        
        live_scores.append({
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score
        })

    
    return render_template('index.html', live_scores=live_scores, completed_match_summary=completed_match_summary)

# Define wallet_balance as a global variable
wallet_balance = 1000  # Initial dummy balance

@app.route('/available_bids', methods=['GET', 'POST'])
def available_bids():
    global wallet_balance  # Access the global wallet balance

    if request.method == 'POST':
        # Handle adding funds to the wallet
        amount_to_add = int(request.form.get('amount'))
        wallet_balance += amount_to_add

    # Fetch today's scoreboard data using nba_api
    games = scoreboard.ScoreBoard()
    games_dict = games.get_dict()

    ongoing_matches = []
    
    if games_dict['scoreboard']['games']:
        for game in games_dict['scoreboard']['games']:
            home_team = game['homeTeam']['teamName']
            away_team = game['awayTeam']['teamName']
            home_score = game['homeTeam']['score']
            away_score = game['awayTeam']['score']

            # Add match details to the list of ongoing matches
            ongoing_matches.append({
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'betting_amount': max(100 - (home_score + away_score), 0)  # Example: betting amount decreases as scores increase
            })

    return render_template('available_bids.html', matches=ongoing_matches, wallet_balance=wallet_balance)

@app.route('/place_bid', methods=['POST'])
def place_bid():
    match_id = request.form.get('match_id')
    bet_amount = int(request.form.get('bet_amount'))
    
    global wallet_balance
    
    if bet_amount <= wallet_balance:
        wallet_balance -= bet_amount  # Deduct the bet amount from the wallet balance
        return jsonify({'success': True, 'message': f'Bid placed successfully! Remaining balance: ${wallet_balance}'})
    
    return jsonify({'success': False, 'message': 'Insufficient funds!'})



@app.route('/live_scores')
def live_scores():
    # Fetch today's scoreboard data using nba_api
    games = scoreboard.ScoreBoard()
    games_dict = games.get_dict()

    # Prepare a list of matches with team names and scores
    live_scores = []
    for game in games_dict['scoreboard']['games']:
        home_team = game['homeTeam']['teamName']
        away_team = game['awayTeam']['teamName']
        home_score = game['homeTeam']['score']
        away_score = game['awayTeam']['score']
        
        # Append each match's data as a dictionary
        live_scores.append({
            'home_team': home_team,
            'away_team': away_team,
            'home_score': home_score,
            'away_score': away_score
        })

    # Return the live scores as JSON
    return jsonify(live_scores)


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
            return jsonify({"access_token": access_token, "name": user["Name"]}), 200
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
