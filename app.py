from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from flask_cors import CORS
import bcrypt
import nba_api
import requests
from datetime import datetime
from nba_api.live.nba.endpoints import scoreboard
from bson.objectid import ObjectId  # Import ObjectId to handle MongoDB IDs


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "83114bdeeb269275f27c98dea61244b1e27d495581b516d6c76d4b3d2e1937d8"
jwt = JWTManager(app)
# Enable CORS for cross-origin requests
CORS(app)
wallet = 1000
placed_bids = []
# MongoDB setup
connection_string = "mongodb+srv://court-metrics:k2vCw0PaWW2v7k7N@cluster0.tqzmo.mongodb.net/"
client = MongoClient(connection_string)
db = client['courtmetrics_db']
matches_collection = db["upcoming_matches"]
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

@app.route('/available_bids', methods=['GET'])
@jwt_required(optional=True)  # Optional so that users can still view matches if not logged in
def available_bids():
    current_user = get_jwt_identity()  # Get current logged-in user (if any)
    wallet_balance = None

    if current_user:
        # Fetch user's wallet balance from MongoDB
        user_data = users_collection.find_one({"username": current_user})
        if user_data:
            wallet_balance = user_data.get("wallet_balance", 1000)  # Default to 1000 if no balance found

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
                'match_id': f"{home_team}_vs_{away_team}",
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'betting_amount': max(100 - (home_score + away_score), 0)  # Example: betting amount decreases as scores increase
            })

    return render_template('available_bids.html', matches=ongoing_matches, wallet_balance=wallet_balance, current_user=current_user)

@app.route('/place_bid', methods=['POST'])
@jwt_required() 
def place_bid():
    global wallet_balance
    current_user = get_jwt_identity()  
    match_id = request.form.get('match_id')
    selected_team = request.form.get('selected_team')  # Either "home" or "away"
    bet_amount = int(request.form.get('bet_amount'))
    user= users_collection.find_one({"username": current_user})
    if bet_amount > wallet_balance:
        return jsonify({'success': False, 'message': 'Insufficient funds!'})

    # Deduct bet amount from wallet immediately
    wallet_balance -= bet_amount
    users_collection.update_one(
        {'username': current_user},
        {'$set': {'wallet_balance': wallet_balance}}
    )

    # Store this bid in memory (or database) to be resolved later when the match ends
    placed_bids.append({
        'match_id': match_id,
        'selected_team': selected_team,
        'bet_amount': bet_amount,
        'status': 'pending'
    })

    return jsonify({'success': True, 'message': f'Bid placed successfully! Remaining balance: ${wallet_balance}'})

@app.route('/check_results')
def check_results():
    global wallet_balance

    # Fetch today's scoreboard data using nba_api to get final scores
    games = scoreboard.ScoreBoard()
    games_dict = games.get_dict()

    results_messages = []

    for game in games_dict['scoreboard']['games']:
        if game['gameStatusText'] == "Final":
            home_team_name = game['homeTeam']['teamName']
            away_team_name = game['awayTeam']['teamName']
            home_score = game['homeTeam']['score']
            away_score = game['awayTeam']['score']

            # Check if there are any pending bids for this match
            for bid in placed_bids:
                if bid['match_id'] == f"{home_team_name}_vs_{away_team_name}" and bid['status'] == "pending":
                    if bid['selected_team'] == "home":
                        if home_score > away_score:  # Home team wins
                            wallet_balance += bid['bet_amount'] * 2  # Double reward
                            results_messages.append(f"Your team {home_team_name} won! You earned ${bid['bet_amount'] * 2}.")
                        elif home_score == away_score:  # Draw
                            wallet_balance += bid['bet_amount']  # Refund original bet amount
                            results_messages.append(f"The match between {home_team_name} and {away_team_name} was a draw. Your bet has been refunded.")
                        else:
                            results_messages.append(f"Your team {home_team_name} lost.")
                    elif bid['selected_team'] == "away":
                        if away_score > home_score:  # Away team wins
                            wallet_balance += bid['bet_amount'] * 2  # Double reward
                            results_messages.append(f"Your team {away_team_name} won! You earned ${bid['bet_amount'] * 2}.")
                        elif away_score == home_score:  # Draw
                            wallet_balance += bid['bet_amount']  # Refund original bet amount
                            results_messages.append(f"The match between {home_team_name} and {away_team_name} was a draw. Your bet has been refunded.")
                        else:
                            results_messages.append(f"Your team {away_team_name} lost.")

                    # Mark this bid as resolved
                    bid['status'] = "resolved"

    return jsonify({'success': True, 'results_messages': results_messages, 'wallet_balance': wallet_balance})



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

@app.route('/get_wallet_balance', methods=['GET'])
@jwt_required()  # Ensure only logged-in users can access this route
def get_wallet_balance():
    current_user = get_jwt_identity()  # Get current user's username from JWT
    
    # Fetch user's wallet balance from MongoDB
    user_data = users_collection.find_one({"username": current_user})
    if user_data:
        return jsonify({'wallet_balance': user_data.get("wallet_balance", 1000)})  # Default balance of 1000
    else:
        return jsonify({'message': 'User not found'}), 404

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        # Find the user in the database
        user = users_collection.find_one({"username": username, "Role": "user"})

        # Verify user and password
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            # Generate access token
            access_token = create_access_token(identity=username)
            return jsonify({"access_token": access_token, "name": user["Name"]}), 200
        else:
            return jsonify({"message": "Invalid username or password"}), 401

    # Render the signin form for GET request
    return render_template('login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        admin = users_collection.find_one({"username": username, "Role": "admin"})

        if admin and bcrypt.checkpw(password.encode('utf-8'), admin['password'].encode('utf-8')):
            access_token = create_access_token(identity=username)
            return jsonify({"access_token": access_token, "name": admin["Name"]}), 200
        else:
            return jsonify({"message": "Invalid admin credentials"}), 401

    return render_template('admin_login.html')


@app.route('/admin_home')
def admin_home():
    users = list(users_collection.find({"Role": "user"}))
    return render_template('admin_home.html', users=users)

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
        user = {"username": username, "password": hashed_password, "Name": name, "Mobile": mobile, "Address": address, "Role": "user"}

        # Insert user into database
        users_collection.insert_one(user)
        return jsonify({"message": "User created successfully"}), 201

    # Render the signup form for GET request
    return render_template('signup.html')
@app.route('/schedules')
def schedules():
    return render_template('schedules.html')


@app.route('/get_upcoming_matches', methods=['GET'])
def get_upcoming_matches():

    month = request.args.get('month', '')
    team = request.args.get('team', '')
    
    if month == '' and team == '':
        
        response = requests.get("http://127.0.0.1:4235/get_matches")
        response.raise_for_status()  # Raise an error for bad status codes
        matches = response.json()  # Parse JSON response
        return jsonify(matches) 
    if month == '' and team != '':
        try:
            response = requests.get("http://127.0.0.1:4235/get_matches", params={"team":team})
            response.raise_for_status()  # Raise an error for bad status codes
            matches = response.json()  # Parse JSON response
            return jsonify(matches)  # Send data to frontend
        except requests.RequestException as e:
            print(f"Error fetching matches: {e}") 
            return jsonify([])  # Return an empty list on error
    else:
        try:
            response = requests.get("http://127.0.0.1:4235/get_matches", params={"month": month,"team":team})
            response.raise_for_status()  # Raise an error for bad status codes
            matches = response.json()  # Parse JSON response
            return jsonify(matches)  # Send data to frontend
        except requests.RequestException as e:
            print(f"Error fetching matches: {e}") 
            return jsonify([])  # Return an empty list on error
@app.route('/add_funds', methods=['POST'])
@jwt_required()
def add_funds():
    current_user = get_jwt_identity()
    amount_to_add = request.form.get('amount')
    if not amount_to_add or not amount_to_add.isdigit():
        return jsonify({'success': False, 'message': 'Invalid amount'}), 400
    amount_to_add = int(amount_to_add)
    user_data = users_collection.find_one({"username": current_user})
    if not user_data:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    new_balance = user_data.get("wallet_balance", 1000) + int(amount_to_add)
    users_collection.update_one({"username": current_user}, {"$set": {"wallet_balance": new_balance}})
    return jsonify({'success': True, 'message': f'Funds added successfully! New balance: ${new_balance}', 'wallet_balance': new_balance}), 200


@app.route("/get_matches", methods=["GET"])
def get_matches():
    month = request.args.get("month")
    team = request.args.get("team")
    print(team)
    print(month)

    # if month != None:
    #     print("month is not none")
    if month != None and team == None:
        month_abbreviation = month[:3].capitalize()
        
        matches = list(
            matches_collection.find({
                "Date": {"$regex": f"{month_abbreviation}", "$options": "i"}
            })
        )

    elif team!=None and month == None:
        team = team.capitalize()
        matches = list(matches_collection.find({"$or": [
            {"Visitor/Neutral": {"$regex": team, "$options": "i"}},
            {"Home/Neutral": {"$regex": team, "$options": "i"}}
        ]}))

    elif month != None and team !=None:
        month_abbreviation = month[:3].capitalize()
        team = team.capitalize()
        matches = list(matches_collection.find({"$and": [
            {"Date": {"$regex": f"{month_abbreviation}", "$options": "i"}},
            {"$or": [
                {"Visitor/Neutral": {"$regex": team, "$options": "i"}},
                {"Home/Neutral": {"$regex": team, "$options": "i"}}
            ]}
        ]}))
        
    else:
        current_month = datetime.now().strftime("%B")
        # matches = list(matches_collection.find().limit(10))
        month_abbreviation = current_month[:3].capitalize()
        
        matches = list(
            matches_collection.find({
                "Date": {"$regex": f"{month_abbreviation}", "$options": "i"}
            }))
        current_day = datetime.now().day
        
        for match in matches:
            found_date = int(match['Date'].split(',')[1].strip().split(' ')[1])
            if found_date < current_day:
                matches.remove(match)
        matches = matches[:10]

    if len(matches) == 0:
        return jsonify({"error": "No matches found,check for the month"})

    for match in matches:
        match["_id"] = str(match["_id"])
    print(matches)
    return jsonify(matches)





@app.route('/delete_user/<user_id>', methods=['DELETE'])
def delete_user(user_id):

    # Attempt to delete the user by user_id
    result = users_collection.delete_one({"_id": ObjectId(user_id)})
    
    if result.deleted_count == 1:
        return jsonify({"success": True, "message": "User deleted successfully."})
    else:
        return jsonify({"success": False, "message": "User not found."}), 404

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=4235, debug=True)
