from flask import Flask, request, jsonify, render_template,session
from pymongo import MongoClient
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from flask_cors import CORS
import bcrypt
import nba_api
import requests
from datetime import datetime, time, timedelta
from nba_api.live.nba.endpoints import scoreboard
from bson.objectid import ObjectId  # Import ObjectId to handle MongoDB IDs
from nba_api.live.nba.endpoints import boxscore
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import joblib
import os


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "83114bdeeb269275f27c98dea61244b1e27d495581b516d6c76d4b3d2e1937d8"
jwt = JWTManager(app)
# Enable CORS for cross-origin requests
CORS(app)
wallet = 100
placed_bids = []
# MongoDB setup
connection_string = "mongodb+srv://court-metrics:k2vCw0PaWW2v7k7N@cluster0.tqzmo.mongodb.net/"
client = MongoClient(connection_string)
db = client['courtmetrics_db']
matches_collection = db["upcoming_matches"]
users_collection = db['Users']
teams_collection = db["Team_stats"]
perGame_collection = db["Player_stats_perGame"]
perMinute_collection = db["Player_stats_perMinute"]
total_collection = db["Player_stats_totals"]
payment_history_collection = db["payment_history"]
suspicious_bets_collection = db["suspicious_bets"]

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
wallet_balance = 100  # Initial dummy balance

@app.route('/place_bid', methods=['POST'])
@jwt_required()
def place_bid():
    global wallet_balance
    current_user = get_jwt_identity()
    print(current_user)
    match_id = request.form.get('match_id')
    selected_team = request.form.get('selected_team')
    bet_amount = int(request.form.get('bet_amount'))

    # Fetch user data from the database
    user_data = users_collection.find_one({"email": current_user})
    wallet_balance = user_data.get("wallet_balance", 100)

    # Check if the user has already placed a bet for the match
    existing_bet = next((bid for bid in placed_bids if bid['match_id'] == match_id and bid['user'] == current_user), None)
    if existing_bet:
        return jsonify({'success': False, 'message': 'You have already placed a bet for this match!'})

    if bet_amount > wallet_balance:
        return jsonify({'success': False, 'message': 'Insufficient funds!'})

    # Deduct bet amount from wallet immediately
    new_balance = wallet_balance - bet_amount
    users_collection.update_one(
        {'email': current_user},
        {'$set': {'wallet_balance': new_balance}}
    )

    # Store this bid in memory (or database) to be resolved later when the match ends
    placed_bids.append({
        'match_id': match_id,
        'selected_team': selected_team,
        'bet_amount': bet_amount,
        'status': 'pending',
        'user': current_user  # Store the user for later reference
    })

    # Record the transaction in payment history
    payment_record = {
        "email": current_user,
        "amount": -bet_amount,
        "date": datetime.now(),
        "balance_after_transaction": new_balance,
        "transaction_type": "bid",
        "match_id": match_id,
        "selected_team": selected_team
    }
    payment_history_collection.insert_one(payment_record)

    return jsonify({'success': True, 'message': f'Bid placed successfully! Remaining balance: ${new_balance}'})


wallet_balance = 100
@app.route('/add_funds_dummy', methods=['POST'])
@jwt_required()
def add_funds_dummy():
    current_user = get_jwt_identity()
    data = request.json
    method = data.get('method')
    amount_to_add = data.get('amount')

    if not method or not amount_to_add or not isinstance(amount_to_add, int) or amount_to_add <= 0:
        return jsonify({'success': False, 'message': 'Invalid input'}), 400

    # Fetch the user's wallet balance from MongoDB
    user_data = users_collection.find_one({"email": current_user})
    if not user_data:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    current_balance = user_data.get("wallet_balance", 0)

    if current_balance + amount_to_add > 5000:
        return jsonify({'success': False, 'message': 'Maximum wallet balance of $5000 reached.'}), 400

    # Simulate adding funds
    new_balance = user_data.get("wallet_balance", 1000) + amount_to_add
    users_collection.update_one({"email": current_user}, {"$set": {"wallet_balance": new_balance}})

    # Record the dummy transaction in the payment history
    payment_record = {
        "email": current_user,
        "amount": amount_to_add,
        "date": datetime.now(),
        "balance_after_transaction": new_balance,
        "transaction_type": f"add_funds_{method}"  # e.g., add_funds_credit_card
    }
    payment_history_collection.insert_one(payment_record)

    return jsonify({
        'success': True,
        'message': f"Funds added successfully via {method}! New balance: ${new_balance}",
        'wallet_balance': new_balance
    }), 200



@app.route('/get_user_bids', methods=['GET'])
@jwt_required()
def get_user_bids():
    current_user = get_jwt_identity()
    user_bids = [bid for bid in placed_bids if bid['user'] == current_user]
    user_data = users_collection.find_one({"email": current_user})
    wallet_balance = user_data.get("wallet_balance", 1000)
    return jsonify({'user_bids': user_bids, 'wallet_balance': wallet_balance})



def predict(home_team,away_team):
    # print('predicting')
    # home_team = request.args.get('home_team')
    # away_team = request.args.get('away_team')

    team_mapping = {"Celtics": "Boston Celtics",
                    "Nets": "Brooklyn Nets",
                    "Knicks": "New York Knicks",
                    "76ers": "Philadelphia 76ers",
                    "Raptors": "Toronto Raptors",
                    "Bulls": "Chicago Bulls",
                    "Cavaliers": "Cleveland Cavaliers",
                    "Pistons": "Detroit Pistons",
                    "Pacers": "Indiana Pacers",
                    "Bucks": "Milwaukee Bucks",
                    "Hawks": "Atlanta Hawks",
                    "Hornets": "Charlotte Hornets",
                    "Heat": "Miami Heat",
                    "Magic": "Orlando Magic",
                    "Wizards": "Washington Wizards",
                    "Nuggets": "Denver Nuggets",
                    "Timberwolves": "Minnesota Timberwolves",
                    "Thunder": "Oklahoma City Thunder",
                    "Trail Blazers": "Portland Trail Blazers",
                    "Jazz": "Utah Jazz",
                    "Warriors": "Golden State Warriors",
                    "Clippers": "Los Angeles Clippers",
                    "Lakers": "Los Angeles Lakers",
                    "Suns": "Phoenix Suns",
                    "Kings": "Sacramento Kings",
                    "Mavericks": "Dallas Mavericks",
                    "Rockets": "Houston Rockets",
                    "Grizzlies": "Memphis Grizzlies",
                    "Pelicans": "New Orleans Pelicans",
                    "Spurs": "San Antonio Spurs"}

    model = joblib.load('random_forest_model.joblib')
    label_encoder_visitor = joblib.load('label_encoder_visitor.joblib')
    label_encoder_home = joblib.load('label_encoder_home.joblib')
    label_encoder_won = joblib.load('label_encoder_won.joblib')
    print('---------------------------')
    print(away_team)
    future_match = pd.DataFrame({
        "Visitor/Neutral_encoded": label_encoder_visitor.transform([team_mapping[away_team]]),
        "Home/Neutral_encoded": label_encoder_home.transform([team_mapping[home_team]])
    })

    future_pred = model.predict(future_match)
    predicted_winner = label_encoder_won.inverse_transform(future_pred)
    future_pred_proba = model.predict_proba(future_match)

    prob_visitor = future_pred_proba[0][model.classes_ == label_encoder_won.transform([team_mapping[away_team]])[0]][0]
    prob_home = future_pred_proba[0][model.classes_ == label_encoder_won.transform([team_mapping[home_team]])[0]][0]

    return predicted_winner[0], prob_visitor* 100, prob_home* 100


@app.route('/available_bids', methods=['GET'])
@jwt_required(optional=True)
def available_bids():
    current_user = get_jwt_identity()
    wallet_balance = None

    if current_user:
        user_data = users_collection.find_one({"email": current_user})
        if user_data:
            wallet_balance = user_data.get("wallet_balance", 1000)

    current_time = datetime.now().time()
    if current_time >= time(1, 0):
        update_previous_day_matches(current_user)

    games = scoreboard.ScoreBoard()
    games_dict = games.get_dict()

    ongoing_matches = []

    if games_dict['scoreboard']['games']:
        for game in games_dict['scoreboard']['games']:
            home_team = game['homeTeam']['teamName']
            away_team = game['awayTeam']['teamName']
            print('==========================================')
            print(home_team)
            print(away_team)
            home_score = game['homeTeam']['score']
            away_score = game['awayTeam']['score']

            # Fetch prediction for the match
            predicted_winner, prob_home, prob_visitor = predict(home_team, away_team)

            ongoing_matches.append({
                'match_id': f"{home_team}_vs_{away_team}",
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'betting_amount': max(115 - (home_score + away_score), 0),
                'predicted_winner': predicted_winner,
                'prob_home': prob_home,
                'prob_visitor': prob_visitor
            })

    return render_template(
        'available_bids.html',
        matches=ongoing_matches,
        wallet_balance=wallet_balance,
        current_user=current_user
    )


def update_previous_day_matches(current_user):
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    yesterday_matches = matches_collection.find({"Date": yesterday})

    for match in yesterday_matches:
        game_id = match['GameID']
        final_score = get_final_score(game_id)

        if final_score:
            home_score, away_score = final_score
            matches_collection.update_one(
                {"_id": match['_id']},
                {"$set": {"HomeScore": home_score, "AwayScore": away_score, "Status": "Completed"}}
            )

            process_bets(match['_id'], home_score, away_score, current_user)

def process_bets(match_id, home_score, away_score, current_user):
    bets = payment_history_collection.find({"match_id": match_id, "email": current_user, "transaction_type": "bid"})

    for bet in bets:
        bet_amount = abs(bet['amount'])
        selected_team = bet['selected_team']

        if (selected_team == 'home' and home_score > away_score) or (selected_team == 'away' and away_score > home_score):
            reward = bet_amount * 2
            update_user_balance(current_user, reward)
            record_transaction(current_user, reward, "bet_win", match_id)
        elif home_score == away_score:
            update_user_balance(current_user, bet_amount)
            record_transaction(current_user, bet_amount, "bet_refund", match_id)

def update_user_balance(username, amount):
    users_collection.update_one(
        {"email": username},
        {"$inc": {"wallet_balance": amount}}
    )

def record_transaction(username, amount, transaction_type, match_id):
    payment_record = {
        "email": username,
        "amount": amount,
        "date": datetime.now(),
        "balance_after_transaction": users_collection.find_one({"email": username})['wallet_balance'],
        "transaction_type": transaction_type,
        "match_id": match_id
    }
    payment_history_collection.insert_one(payment_record)

def get_final_score(game_id):
    try:
        # Fetch the boxscore data for the given game_id
        box_score = boxscore.BoxScore(game_id=game_id)
        game_data = box_score.get_dict()

        # Extract the scores
        home_score = game_data['game']['homeTeam']['score']
        away_score = game_data['game']['awayTeam']['score']

        # Check if the game is finished
        if game_data['game']['gameStatus'] == 3:  # 3 indicates a completed game
            return (home_score, away_score)
        else:
            return None  # Game not finished yet
    except Exception as e:
        print(f"Error fetching score for game {game_id}: {str(e)}")
        return None



otp_storage = {}
def send_otp_email(user_email, otp):
    sender_email = "testsenderse2024@gmail.com"  
    sender_password = "sdew udqr hmho reps" 
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    subject = "OTP to reset your password"
    body = f"OTP to reset password for your CourtMetrics account is: {otp}"

    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = user_email
    message['Subject'] = subject
    message.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, user_email, message.as_string())
        server.quit()
    except Exception as e:
        print(f"Error sending OTP: {e}")


@app.route('/send-otp', methods=['GET'])
def send_otp():
    user_email = request.args.get('email') 

    if not user_email:
        return jsonify({"error": "Email is required"}), 400

    otp = random.randint(100000, 999999)
    expiration_time = datetime.now() + timedelta(minutes=5)  

    otp_storage[user_email] = {"otp": otp, "expires_at": expiration_time}

    
    send_otp_email(user_email, otp)
    return jsonify({"message": f"OTP sent to {user_email}"}), 200


@app.route('/verify-otp', methods=['GET'])
def verify_otp():
    user_email = request.args.get('email')
    user_otp = request.args.get('otp')

    if not user_email or not user_otp:
        return jsonify({"error": "Email and OTP are required"}), 400

    stored_data = otp_storage.get(user_email)

    if not stored_data:
        return jsonify({"error": "OTP not found for this email"}), 404

    correct_otp = stored_data["otp"]
    expiration_time = stored_data["expires_at"]

    if datetime.now() > expiration_time:
        return jsonify({"error": "OTP has expired"}), 400

    if int(user_otp) == correct_otp:
        del otp_storage[user_email] 
        return jsonify({"message": "OTP verified successfully!"}), 200
    else:
        return jsonify({"error": "Invalid OTP"}), 400
    

@app.route('/forgot_password', methods=['GET'])
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.json
    email = data.get('email')
    new_password = data.get('newPassword')

    if not email or not new_password or len(new_password) < 12:
        return jsonify({"message": "Invalid input or password too short"}), 400

    # Find user in the database
    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Hash the new password
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Update password in the database
    users_collection.update_one({"email": email}, {"$set": {"password": hashed_password}})
    return jsonify({"message": "Password reset successful"}), 200


@app.route('/check_results')
def check_results():
    global wallet_balance
    games = scoreboard.ScoreBoard().get_dict()

    results_messages = []
    
    for game in games['scoreboard']['games']:
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
                            # Add this line after updating wallet_balance in check_results function
                            users_collection.update_one( {'email': current_user}, {'$set': {'wallet_balance': wallet_balance}})
                        elif home_score == away_score:  # Draw
                            wallet_balance += bid['bet_amount']  # Refund original bet amount
                            results_messages.append(f"The match between {home_team_name} and {away_team_name} was a draw. Your bet has been refunded.")
                            users_collection.update_one( {'email': current_user}, {'$set': {'wallet_balance': wallet_balance}})
                        else:

                            results_messages.append(f"Your team {home_team_name} lost.")
                            users_collection.update_one( {'email': current_user}, {'$set': {'wallet_balance': wallet_balance}})
                    elif bid['selected_team'] == "away":
                        if away_score > home_score:  # Away team wins
                            wallet_balance += bid['bet_amount'] * 2  # Double reward
                            results_messages.append(f"Your team {away_team_name} won! You earned ${bid['bet_amount'] * 2}.")
                            users_collection.update_one( {'email': current_user}, {'$set': {'wallet_balance': wallet_balance}})
                        elif away_score == home_score:  # Draw
                            wallet_balance += bid['bet_amount']  # Refund original bet amount
                            results_messages.append(f"The match between {home_team_name} and {away_team_name} was a draw. Your bet has been refunded.")
                            users_collection.update_one( {'email': current_user}, {'$set': {'wallet_balance': wallet_balance}})
                        else:
                            results_messages.append(f"Your team {away_team_name} lost.")
                            users_collection.update_one( {'email': current_user}, {'$set': {'wallet_balance': wallet_balance}})

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
    user_data = users_collection.find_one({"email": current_user})
    if user_data:
        return jsonify({'wallet_balance': user_data.get("wallet_balance", 1000)})  # Default balance of 1000
    else:
        return jsonify({'message': 'User not found'}), 404

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")

        # Find the user in the database
        user = users_collection.find_one({"email": email, "Role": "user"})

        # Verify user and password
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            # Generate access token
            access_token = create_access_token(identity=email)
            # session['access_token'] = access_token
            return jsonify({"access_token": access_token, "username": user["username"]}), 200
        else:
            return jsonify({"message": "Invalid username or password"}), 401

    # Render the signin form for GET request
    return render_template('login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        admin = users_collection.find_one({"email": email, "Role": "admin"})

        if admin and bcrypt.checkpw(password.encode('utf-8'), admin['password'].encode('utf-8')):
            access_token = create_access_token(identity=email)
            return jsonify({"admin_access_token": access_token, "username": admin["username"]}), 200
        else:
            return jsonify({"message": "Invalid admin credentials"}), 401

    return render_template('admin_login.html')


@app.route('/admin_home')
def admin_home():
    # Get all users
    users = list(users_collection.find({"Role": "user"}))
    
    # Get all betting transactions
    bets = list(payment_history_collection.find({"transaction_type": "bid"}))
    
    # Get suspicious bets
    suspicious_bets = list(suspicious_bets_collection.find())
    
    # Format suspicious bets data
    formatted_suspicious = []
    for bet in suspicious_bets:
        try:
            # Convert string date to datetime if it's a string
            if isinstance(bet['date_reported'], str):
                bet['date_reported'] = datetime.strptime(bet['date_reported'], '%Y-%m-%d %H:%M:%S')
        except (ValueError, KeyError):
            bet['date_reported'] = datetime.now()
            
        formatted_bet = {
            'bet_id': str(bet['_id']),
            'email': bet.get('email', 'Unknown'),
            'match_id': bet.get('match_id', 'Unknown Match'),
            'selected_team': bet.get('selected_team', 'Unknown'),
            'amount': bet.get('amount', 0),
            'reason': bet.get('reason', ''),
            'date_reported': bet['date_reported'].strftime('%Y-%m-%d %H:%M:%S'),
            'status': bet.get('status', 'Under Review')
        }
        formatted_suspicious.append(formatted_bet)

    # Format betting data
    formatted_bets = []
    for bet in bets:
        formatted_bet = {
            'id': str(bet['_id']),
            'email': bet.get('email', 'Unknown'),
            'match_id': bet.get('match_id', 'Unknown Match'),
            'selected_team': bet.get('selected_team', 'Unknown'),
            'amount': abs(bet.get('amount', 0)),
            'status': 'Running',
            'admin_pl': -bet.get('amount', 0)
        }
        formatted_bets.append(formatted_bet)

    return render_template(
        'admin_home.html',
        users=users,
        bets=formatted_bets,
        suspicious_bets=formatted_suspicious
    )

@app.route('/report_bet', methods=['POST'])
def report_bet():
    bet_id = request.form.get('bet_id')
    reason = request.form.get('reason')
    
    if not bet_id or not reason:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
    
    try:
        # Find the bet in payment history
        bet = payment_history_collection.find_one({"_id": ObjectId(bet_id)})
        if not bet:
            return jsonify({"success": False, "message": "Bet not found"}), 404

        # Create suspicious bet record
        suspicious_bet = {
            "bet_id": str(bet["_id"]),
            "email": bet.get("email", "Unknown"),
            "match_id": bet.get("match_id", "Unknown Match"),
            "selected_team": bet.get("selected_team", "Unknown"),
            "amount": abs(bet.get("amount", 0)),
            "reason": reason,
            "date_reported": datetime.now(),
            "status": "Under Review"
        }
        
        # Insert into suspicious_bets collection
        suspicious_bets_collection.insert_one(suspicious_bet)
        
        # Remove from payment history
        payment_history_collection.delete_one({"_id": ObjectId(bet_id)})
        
        return jsonify({"success": True, "message": "Bet reported successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/delete_suspicious_bet/<bet_id>', methods=['DELETE'])
def delete_suspicious_bet(bet_id):
    try:
        result = suspicious_bets_collection.delete_one({"_id": ObjectId(bet_id)})
        if result.deleted_count == 1:
            return jsonify({"success": True, "message": "Suspicious bet deleted successfully."})
        return jsonify({"success": False, "message": "Bet not found."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/delete_bet/<bet_id>', methods=['DELETE'])
def delete_bet(bet_id):
    try:
        result = payment_history_collection.delete_one({"_id": ObjectId(bet_id)})
        if result.deleted_count == 1:
            return jsonify({"success": True, "message": "Bet deleted successfully."})
        return jsonify({"success": False, "message": "Bet not found."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/betting_history')
def betting_history():
    # Get all betting transactions
    bets = list(payment_history_collection.find({"transaction_type": "bid"}))
    
    # Calculate financial metrics
    total_bets = len(bets)
    total_bet_amount = sum(abs(bet.get('amount', 0)) for bet in bets)
    net_profit = sum(-bet.get('amount', 0) for bet in bets)
    
    # Format betting data
    formatted_bets = []
    for bet in bets:
        formatted_bet = {
            'id': str(bet['_id']),
            'email': bet.get('email', 'Unknown'),
            'match_id': bet.get('match_id', 'Unknown Match'),
            'selected_team': bet.get('selected_team', 'Unknown'),
            'amount': abs(bet.get('amount', 0)),
            'status': 'Running',
            'admin_pl': -bet.get('amount', 0)
        }
        formatted_bets.append(formatted_bet)

    return render_template(
        'admin_betting.html',
        bets=formatted_bets,
        total_bets=total_bets,
        total_bet_amount=total_bet_amount,
        net_profit=net_profit
    )

@app.route('/suspicious_bids')
def suspicious_bids():
    suspicious_bets = list(suspicious_bets_collection.find())
    formatted_suspicious = []
    for bet in suspicious_bets:
        formatted_bet = {
            'bet_id': str(bet['_id']),
            'email': bet.get('email', 'Unknown'),
            'match_id': bet.get('match_id', 'Unknown Match'),
            'selected_team': bet.get('selected_team', 'Unknown'),
            'amount': bet.get('amount', 0),
            'reason': bet.get('reason', ''),
            'date_reported': bet['date_reported'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(bet['date_reported'], datetime) else bet['date_reported'],
            'status': bet.get('status', 'Under Review')
        }
        formatted_suspicious.append(formatted_bet)
    
    return render_template('suspicious_bids.html', suspicious_bets=formatted_suspicious)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        mobile = request.form.get("mobile")
        username = request.form.get("username")
        address = request.form.get("address")

        # Validate password length
        if len(password) < 12:
            return jsonify({"message": "Password is too short"}), 400
        
        if "@gmail.com" not in email:
            return jsonify({"message": "Please use a Gmail account"}), 400

        # Check if the user already exists
        if users_collection.find_one({"email": email}):
            return jsonify({"message": "User already exists, Please Log In"}), 409

        # Ensure required fields are not empty
        if not all([email, password, mobile, username, address]):
            return jsonify({"message": "Please fill all the fields"}), 400

        # Hash the password and save user data
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = {"email": email, "password": hashed_password, "username": username, "Mobile": mobile, "Address": address, "Role": "user"}

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
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))  # Get items per page from request
    month = request.args.get('month', '')
    team = request.args.get('team', '')

    try:
        params = {"month": month, "team": team}
        response = requests.get("http://127.0.0.1:4235/get_matches", params=params)
        response.raise_for_status()
        matches = response.json()

        today = datetime.today().date()
        upcoming_matches = [
            match for match in matches 
            if 'Date' in match and datetime.strptime(match['Date'], '%a, %b %d, %Y').date() >= today
        ]

        total_matches = len(upcoming_matches)
        total_pages = (total_matches + per_page - 1) // per_page
        paginated_matches = upcoming_matches[(page - 1) * per_page: page * per_page]

        return jsonify({
            "matches": paginated_matches,
            "current_page": page,
            "total_pages": total_pages
        })
    except requests.RequestException as e:
        print(f"Error fetching matches: {e}")
        return jsonify({"matches": [], "current_page": 1, "total_pages": 1})
        


@app.route('/payment_history', methods=['GET'])
@jwt_required(optional=True)
def payment_history():
    return render_template('payment_history.html')

@app.route('/api/payment_history', methods=['GET'])
@jwt_required(optional=True)
def api_payment_history():
    current_user = get_jwt_identity()
    page = int(request.args.get('page', 1))
    per_page = 10  
    # Filtering options
    transaction_type = request.args.get('transaction_type', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    
    # Build query
    query = {"email": current_user}
    
    if transaction_type:
        query['transaction_type'] = transaction_type
    
    if start_date_str and end_date_str:
        query['date'] = {
            "$gte": datetime.strptime(start_date_str, "%Y-%m-%d"),
            "$lte": datetime.strptime(end_date_str, "%Y-%m-%d")
        }
    
    total_records = payment_history_collection.count_documents(query)
    total_pages = (total_records + per_page - 1) // per_page
    
    history = list(payment_history_collection.find(query)
                   .sort("date", -1)
                   .skip((page-1) * per_page)
                   .limit(per_page))
    
    for record in history:
        record['_id'] = str(record['_id'])
        record['date'] = record['date'].isoformat()
    
    # Return JSON response
    return jsonify({
        'transactions': history,
        'current_page': page,
        'total_pages': total_pages
    })
 
    

@app.route('/add_funds', methods=['POST'])
@jwt_required()
def add_funds():
    current_user = get_jwt_identity()
    amount_to_add = request.form.get('amount')
    
    if not amount_to_add or not amount_to_add.isdigit():
        return jsonify({'success': False, 'message': 'Invalid amount'}), 400
    
    amount_to_add = int(amount_to_add)
    user_data = users_collection.find_one({"email": current_user})
    
    if not user_data:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    # Update the user's wallet balance
    new_balance = user_data.get("wallet_balance", 1000) + amount_to_add
    users_collection.update_one({"email": current_user}, {"$set": {"wallet_balance": new_balance}})
    
    # Record the transaction in the payment history
    payment_record = {
        "email": current_user,
        "amount": amount_to_add,
        "date": datetime.now(),
        "balance_after_transaction": new_balance,
        "transaction_type": "add_funds"
    }
    payment_history_collection.insert_one(payment_record)
    
    return jsonify({'success': True, 'message': f'Funds added successfully! New balance: ${new_balance}', 'wallet_balance': new_balance}), 200


@app.route('/withdraw_funds', methods=['POST'])
@jwt_required()
def withdraw_funds():
    current_user = get_jwt_identity()
    amount_to_withdraw = request.form.get('amount')
    
    if not amount_to_withdraw or not amount_to_withdraw.isdigit():
        return jsonify({'success': False, 'message': 'Invalid amount'}), 400
    
    amount_to_withdraw = int(amount_to_withdraw)
    user_data = users_collection.find_one({"email": current_user})
    
    if not user_data:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    current_balance = user_data.get("wallet_balance", 0)
    if amount_to_withdraw > current_balance:
        return jsonify({'success': False, 'message': 'Insufficient funds'}), 400
    
    # Update the user's wallet balance
    new_balance = current_balance - amount_to_withdraw
    users_collection.update_one(
        {"email": current_user}, 
        {"$set": {"wallet_balance": new_balance}}
    )
    
    # Record the transaction in the payment history
    payment_record = {
        "email": current_user,
        "amount": -amount_to_withdraw,
        "date": datetime.now(),
        "balance_after_transaction": new_balance,
        "transaction_type": "withdraw_funds"
    }
    payment_history_collection.insert_one(payment_record)
    
    return jsonify({
        'success': True, 
        'message': f'Withdrawal successful! New balance: ${new_balance}',
        'wallet_balance': new_balance
    }), 200



@app.route("/get_team_stats", methods=["GET"])
def get_team_stats():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get('per_page', 10)) 
    year = request.args.get("year", "").strip()
    team = request.args.get("team", "").strip()

    if not year and not team:
        year = "2024"
        team = ""

    query = {}
    if year:
        query["Year"] = {"$regex": f"{year}", "$options": "i"}
    if team:
        query["Team"] = {"$regex": f"{team}", "$options": "i"}

    pipeline = [
        {"$match": query},
        {"$addFields": {
            "RankInt": {
                "$cond": {
                    "if": {"$eq": [{"$type": "$Rank"}, "string"]},
                    "then": {"$toInt": "$Rank"},
                    "else": "$Rank"
                }
            }
        }},
        {"$sort": {"RankInt": 1}},
        {"$project": {"RankInt": 0}}
    ]

    teams = list(teams_collection.aggregate(pipeline))

    years = teams_collection.distinct("Year")
    teams_list = teams_collection.distinct("Team")

    if not teams:
        return render_template(
            "stats.html",
            stats=[],
            error=f"No stats found for year '{year}' and team '{team}'. Please check your input.",
            years=sorted(years),
            teams=sorted(teams_list),
        )

    for team in teams:
        team.pop('_id', None)

    return render_template(
        "stats.html",
        stats=teams,
        error=None,
        years=sorted(years),
        teams=sorted(teams_list),
    )

@app.route("/get_filters", methods=["GET"])
def get_filters():
    # Fetch distinct years and teams from MongoDB
    years = teams_collection.distinct("Year")
    teams = teams_collection.distinct("Team")

    return jsonify({"years": sorted(years), "teams": sorted(teams)})

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

        for item in matches:
            item['DateObj'] = datetime.strptime(item['Date'], '%a, %b %d, %Y')

        # Sort the JSON data based on the DateObj field
        sorted_data = sorted(matches, key=lambda x: x['DateObj'])

        # Remove the temporary DateObj field after sorting
        for item in sorted_data:
            del item['DateObj']

        matches = sorted_data

    elif team!=None and month == None:
        team = team.capitalize()
        matches = list(matches_collection.find({"$or": [
            {"Visitor/Neutral": {"$regex": team, "$options": "i"}},
            {"Home/Neutral": {"$regex": team, "$options": "i"}}
        ]}))

        for item in matches:
            item['DateObj'] = datetime.strptime(item['Date'], '%a, %b %d, %Y')

        # Sort the JSON data based on the DateObj field
        sorted_data = sorted(matches, key=lambda x: x['DateObj'])

        # Remove the temporary DateObj field after sorting
        for item in sorted_data:
            del item['DateObj']

        matches = sorted_data

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

        for item in matches:
            item['DateObj'] = datetime.strptime(item['Date'], '%a, %b %d, %Y')

        # Sort the JSON data based on the DateObj field
        sorted_data = sorted(matches, key=lambda x: x['DateObj'])

        # Remove the temporary DateObj field after sorting
        for item in sorted_data:
            del item['DateObj']

        matches = sorted_data
        
    else:
        print('------------------------------')
        current_month = datetime.now().strftime("%B")
        # matches = list(matches_collection.find().limit(10))
        month_abbreviation = current_month[:3].capitalize()
        
        matches = list(
            matches_collection.find({
                "Date": {"$regex": f"{month_abbreviation}", "$options": "i"}
            }))
        
        current_day = datetime.now().day
        trail = []
        # print(current_day)
        for match in matches:
            found_date = int(match['Date'].split(',')[1].strip().split(' ')[1])
            
            if found_date >= current_day:
                trail.append(match)

        for item in trail:
            item['DateObj'] = datetime.strptime(item['Date'], '%a, %b %d, %Y')

        # Sort the JSON data based on the DateObj field
        sorted_data = sorted(trail, key=lambda x: x['DateObj'])

        # Remove the temporary DateObj field after sorting
        for item in sorted_data:
            del item['DateObj']

        matches = sorted_data[:10]

    if len(matches) == 0:
        return jsonify({"error": "No matches found,check for the month"})

    for match in matches:
        match["_id"] = str(match["_id"])
    # print(matches)
    return jsonify(matches)


@app.route("/api/player_stats", methods=["GET"])
def api_player_stats():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get('per_page', 20))
    year = request.args.get("year", "").strip()
    player = request.args.get("player", "").strip()
    stat_type = request.args.get("stat_type", "perGame").strip()

    collection_map = {
        "perGame": perGame_collection,
        "perMinute": perMinute_collection,
        "total": total_collection
    }
    
    selected_collection = collection_map.get(stat_type, perGame_collection)

    query = {}
    if year:
        query["Year"] = {"$regex": f"{year}", "$options": "i"}
    if player:
        query["Player"] = {"$regex": f"{player}", "$options": "i"}

    pipeline = [
        {"$match": query},
        {"$match": {"Player": {"$ne": "League Average"}}},
        {"$addFields": {
            "RkInt": {
                "$convert": {
                    "input": "$Rk",
                    "to": "int",
                    "onError": 0,
                    "onNull": 0
                }
            }
        }},
        {"$sort": {"RkInt": 1}},
        {"$project": {"RkInt": 0}}
    ]

    players = list(selected_collection.aggregate(pipeline))
    
    total_players = len(players)
    total_pages = (total_players + per_page - 1) // per_page
    players_paginated = players[(page - 1) * per_page: page * per_page]

    for player in players_paginated:
        player.pop('_id', None)

    return jsonify({
        "stats": players_paginated,
        "current_page": page,
        "total_pages": total_pages
    })

@app.route("/get_player_stats", methods=["GET"])
def get_player_stats():
    years = sorted(perGame_collection.distinct("Year"))
    players_list = sorted(perGame_collection.distinct("Player"))

    return render_template(
        "player_stats.html",
        stats=[],
        error=None,
        years=years,
        players=players_list,
        stat_type="perGame"
    )

@app.route("/past_matches", methods=["GET"])
def past_matches():
        # Get distinct teams for filter dropdown
    teams_list = list(db["past_matches"].distinct("Visitor/Neutral")) + \
                 list(db["past_matches"].distinct("Home/Neutral"))
    teams_list = sorted(list(set(teams_list)))  # Remove duplicates and sort
    return render_template("past_matches.html",
                           teams=teams_list)

@app.route("/api/past_matches", methods=["GET"])
def api_past_matches():

    page = int(request.args.get("page", 1))  # Default to page 1
    per_page = int(request.args.get('per_page', 20))  # Get items per 
    month = request.args.get("month", "").strip()
    team = request.args.get("team", "").strip()

    query = {}
    if month:
        query["Date"] = {"$regex": f"{month[:3]}", "$options": "i"}
    if team:
        query["$or"] = [
            {"Visitor/Neutral": {"$regex": team, "$options": "i"}},
            {"Home/Neutral": {"$regex": team, "$options": "i"}}
        ]

    # Count total documents
    total_matches = db["past_matches"].count_documents(query)
    total_pages = (total_matches + per_page - 1) // per_page

    # Retrieve matches with pagination
    matches = list(db["past_matches"].find(query)
                   .skip((page - 1) * per_page)
                   .limit(per_page))

    for match in matches:
        match["_id"] = str(match["_id"])

    return jsonify({
        "matches": matches,
        "current_page": page,
        "total_pages": total_pages
    })

@app.route('/delete_user/<user_id>', methods=['DELETE'])
def delete_user(user_id):

    # Attempt to delete the user by user_id
    find_user = users_collection.find_one({"_id": ObjectId(user_id)})
    user_name = find_user["email"]
    find_details = list(payment_history_collection.find({"email": user_name}))
    for item in find_details:
        payment_history_collection.delete_one({"_id": item["_id"]})

    result = users_collection.delete_one({"_id": ObjectId(user_id)})
    
    if result.deleted_count == 1:
        return jsonify({"success": True, "message": "User deleted successfully."})
    else:
        return jsonify({"success": False, "message": "User not found."}), 404

@app.route('/bidding_history', methods=['GET'])
@jwt_required(optional=True)
def bidding_history():
    return render_template('bidding_history.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=4235, debug=True)