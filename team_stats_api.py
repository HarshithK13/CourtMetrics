from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)
client = MongoClient("mongodb+srv://court-metrics:k2vCw0PaWW2v7k7N@cluster0.tqzmo.mongodb.net/")
db = client["courtmetrics_db"]
teams_collection = db["Team_stats"]

@app.route("/get_team_stats", methods=["GET"])
def get_player_stats():
    year = request.args.get("year")
    team = request.args.get("team")

    if year == "" and team != "":
        # default = "2024"
        teams = list(teams_collection.find({
            "Team": {"$regex": f"{team}", "$options": "i"}
        }))
    elif year != "" and team =="" :
        teams = list(teams_collection.find({
            "Year": {"$regex": f"{year}", "$options": "i"}
        }))
    elif year != "" and team != "":
        teams = list(teams_collection.find({"$and": [
            {"Year": {"$regex": f"{year}", "$options": "i"}},
            {"Team": {"$regex": f"{team}", "$options": "i"}}
        ]}))
    else:
        default = "2024"
        teams = list(teams_collection.find({
            "Year": {"$regex": f"{default}", "$options": "i"}
        }))


    if len(teams) == 0:
        return jsonify({"error": "No Stats found,check for the year"})

    for name in teams:
        name["_id"] = str(name["_id"])
    print(teams)
    return jsonify(teams)

if __name__ == "__main__":
    app.run(debug=False)