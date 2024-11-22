from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)
client = MongoClient("mongodb+srv://court-metrics:k2vCw0PaWW2v7k7N@cluster0.tqzmo.mongodb.net/")
db = client["courtmetrics_db"]
perGame_collection = db["Player_stats_perGame"]
perMinute_collection = db["Player_stats_perMinute"]
total_collection = db["Player_stats_totals"]

@app.route("/get_player_stats", methods=["GET"])
def get_player_stats():
    year = request.args.get("year")
    typeOf_stat = request.args.get("typeOf_stat")

    if year is None and typeOf_stat is None:
        default = "2024"
        players = list(perGame_collection.find({
            "Year": {"$regex": f"{default}", "$options": "i"}
        }))
    
    elif year is None and typeOf_stat == "perGame":
        default = "2024"
        players = list(perGame_collection.find({
            "Year": {"$regex": f"{default}", "$options": "i"}
        }))

    elif year is None and typeOf_stat == "perMinute":
        default = "2024"
        players = list(perMinute_collection.find({
            "Year": {"$regex": f"{default}", "$options": "i"}
        }))
    
    elif year is None and typeOf_stat == "total":
        default = "2024"
        players = list(total_collection.find({
            "Year": {"$regex": f"{default}", "$options": "i"}
        }))

    elif year is not None and typeOf_stat == "perGame":
        players = list(perGame_collection.find({
            "Year": {"$regex": f"{year}", "$options": "i"}
        }))
    
    elif year is not None and typeOf_stat == "perMinute":
        players = list(perMinute_collection.find({
            "Year": {"$regex": f"{year}", "$options": "i"}
        }))

    elif year is not None and typeOf_stat == "total":
        players = list(total_collection.find({
            "Year": {"$regex": f"{year}", "$options": "i"}
        }))

    else:
        players = list(perGame_collection.find({
            "Year": {"$regex": f"{year}", "$options": "i"}
        }))

    if len(players) == 0:
        return jsonify({"error": "No Stats found,check for the year"})

    for name in players:
        name["_id"] = str(name["_id"])
    print(players)
    return jsonify(players)

if __name__ == "__main__":
    app.run(debug=False)