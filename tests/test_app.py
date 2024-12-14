import unittest
from unittest.mock import patch, MagicMock
from app import app
from flask import jsonify
import bcrypt
from flask_jwt_extended import create_access_token


class FlaskAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        app.config['TESTING'] = True

    @patch('app.users_collection')
    def test_signup_success(self, mock_users_collection):
        # Simulate new user 
        mock_users_collection.find_one.return_value = None
        # Simulate successful insertion
        mock_users_collection.insert_one.return_value = MagicMock()

        # Post signup data
        response = self.client.post('/signup', data={
            "email": "newuser@gmail.com", 
            "password": "securepassword123",
            "mobile": "1234567890",
            "username": "New User",
            "address": "123 New Street"
        })

        # Assert response code and message
        self.assertEqual(response.status_code, 201)
        self.assertIn(b"User created successfully", response.data)

    @patch('app.users_collection')
    def test_signup_existing_user(self, mock_users_collection):
        # Simulate an existing user with the given email
        mock_users_collection.find_one.return_value = {"email": "existinguser@gmail.com"}

        # Attempt to sign up with an existing email
        response = self.client.post('/signup', data={
            "email": "existinguser@gmail.com",  # Same email as mocked existing user
            "password": "anotherpassword123",
            "mobile": "0987654321",
            "name": "Existing User",
            "address": "456 Existing Lane"
        })

        # Assert response code and message
        self.assertEqual(response.status_code, 409)
        self.assertIn(b"User already exists", response.data)


    @patch('app.users_collection')
    def test_login_success(self, mock_users_collection):
        password = bcrypt.hashpw("password123456".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        mock_users_collection.find_one.return_value = {
            "username": "testuser",
            "email": "testuser@gmail.com",
            "password": password
        }

        response = self.client.post('/login', data={
            "email": "testuser@gmail.com",
            "password": "password123456"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"access_token", response.data)

    @patch('app.users_collection')
    def test_login_invalid_credentials(self, mock_users_collection):
        mock_users_collection.find_one.return_value = None

        response = self.client.post('/login', data={
            "email": "wronguser@gmail.com",
            "password": "wrongpassword"
        })
        self.assertEqual(response.status_code, 401)
        self.assertIn(b"Invalid username or password", response.data)

    def test_home_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"live_scores", response.data)

    @patch('app.db')  # Mock the MongoDB database
    def test_past_matches_endpoint(self, mock_db):
        # Mock the data returned by the database for past matches
        mock_db["past_matches"].find.return_value = [
            {
                "_id": "1",
                "Date": "Fri, Dec 8, 2023",
                "Visitor/Neutral": "Team A",
                "Home/Neutral": "Team B",
                "PTS": 100,
                "Home_PTS": 90,
                "no. of OT": 1
            },
            {
                "_id": "2",
                "Date": "Thu, Dec 7, 2023",
                "Visitor/Neutral": "Team C",
                "Home/Neutral": "Team D",
                "PTS": 110,
                "Home_PTS": 120,
                "no. of OT": 0
            }
        ]

        # Send a GET request to the past_matches endpoint
        response = self.client.get('/past_matches')

        # Assert that the response status code is 200
        self.assertEqual(response.status_code, 200)

    @patch('app.db')  # Mock the MongoDB database
    def test_past_matches_endpoint_with_pagination(self, mock_db):
        # Mock data for past matches
        mock_matches = [
            {
                "_id": "1",
                "Date": "Fri, Dec 8, 2023",
                "Visitor/Neutral": "Team A",
                "Home/Neutral": "Team B",
                "PTS": 100,
                "Home_PTS": 90,
                "no. of OT": 1
            },
            {
                "_id": "2",
                "Date": "Thu, Dec 7, 2023",
                "Visitor/Neutral": "Team C",
                "Home/Neutral": "Team D",
                "PTS": 110,
                "Home_PTS": 120,
                "no. of OT": 0
            },
            {
                "_id": "3",
                "Date": "Wed, Dec 6, 2023",
                "Visitor/Neutral": "Team E",
                "Home/Neutral": "Team F",
                "PTS": 90,
                "Home_PTS": 95,
                "no. of OT": 0
            }
        ]

        @patch('app.db')  # Mock the MongoDB database
        def test_past_matches_endpoint_with_pagination(self, mock_db):
            # Mock data for past matches
            mock_matches = [
                {
                    "_id": "1",
                    "Date": "Fri, Dec 8, 2023",
                    "Visitor/Neutral": "Team A",
                    "Home/Neutral": "Team B",
                    "PTS": 100,
                    "Home_PTS": 90,
                    "no. of OT": 1
                },
                {
                    "_id": "2",
                    "Date": "Thu, Dec 7, 2023",
                    "Visitor/Neutral": "Team C",
                    "Home/Neutral": "Team D",
                    "PTS": 110,
                    "Home_PTS": 120,
                    "no. of OT": 0
                },
                {
                    "_id": "3",
                    "Date": "Wed, Dec 6, 2023",
                    "Visitor/Neutral": "Team E",
                    "Home/Neutral": "Team F",
                    "PTS": 90,
                    "Home_PTS": 95,
                    "no. of OT": 0
                }
            ]

            # Mock `find()` and `count_documents()` behavior
            mock_cursor = MagicMock()
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = iter(mock_matches[:2])  # Return the first 2 matches for the test

            mock_db["past_matches"].find.return_value = mock_cursor
            mock_db["past_matches"].count_documents.return_value = len(mock_matches)

            # Test first page of pagination
            response = self.client.get('/api/past_matches', query_string={"page": 1, "per_page": 2})
            self.assertEqual(response.status_code, 200)
            response_data = response.get_json()

            # Validate first page results
            self.assertIn("matches", response_data)
            self.assertEqual(len(response_data["matches"]), 2)
            self.assertEqual(response_data["matches"][0]["Visitor/Neutral"], "Team A")
            self.assertEqual(response_data["matches"][1]["Visitor/Neutral"], "Team C")

            # Test second page of pagination
            mock_cursor.limit.return_value = iter(mock_matches[2:])  # Return the last match for the second page
            response = self.client.get('/api/past_matches', query_string={"page": 2, "per_page": 2})
            self.assertEqual(response.status_code, 200)
            response_data = response.get_json()

            # Validate second page results
            self.assertEqual(len(response_data["matches"]), 1)
            self.assertEqual(response_data["matches"][0]["Visitor/Neutral"], "Team E")

            # Validate pagination metadata
            self.assertEqual(response_data["current_page"], 2)
            self.assertEqual(response_data["total_pages"], 2)


    @patch('app.users_collection')
    def test_get_wallet_balance(self, mock_users_collection):
        # Mock database response
        mock_users_collection.find_one.return_value = {"wallet_balance": 1000}

        # Use Flask application context
        with app.app_context():
            # Generate a valid access token
            token = create_access_token(identity="testuser")

            # Use the generated token in the request header
            response = self.client.get('/get_wallet_balance', headers={
                "Authorization": f"Bearer {token}"  # Pass the token in the Authorization header
            })

            # Assert response status and content
            self.assertEqual(response.status_code, 200)
            self.assertEqual('{"wallet_balance":1000}', response.data.decode('utf-8').strip('\n'))

if __name__ == '__main__':
    unittest.main()
