import unittest
from unittest.mock import patch, MagicMock
from app import app
from flask import jsonify
import bcrypt

class FlaskAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This method runs once at the start, useful for setting up the client
        cls.client = app.test_client()  # Create a test client
        app.config['TESTING'] = True  # Enable testing mode for Flask

    @patch('app.users_collection')
    def test_signup_success(self, mock_users_collection):
        # Mock the users_collection to simulate no existing user with this username
        mock_users_collection.find_one.return_value = None
        mock_users_collection.insert_one.return_value = MagicMock()

        # Simulate a successful signup
        response = self.client.post('/signup', data={
            "username": "testuser",
            "password": "password123456",
            "Mobile": "1234567890",
            "Name": "Test User",
            "Address": "123 Test St"
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn(b"User created successfully", response.data)

    @patch('app.users_collection')
    def test_signup_existing_user(self, mock_users_collection):
        # Mock the users_collection to simulate an existing user with this username
        mock_users_collection.find_one.return_value = {"username": "testuser"}

        # Attempt to sign up with the same username
        response = self.client.post('/signup', data={
            "username": "testuser",
            "password": "password123456",
            "Mobile": "1234567890",
            "Name": "Test User",
            "Address": "123 Test St"
        })
        self.assertEqual(response.status_code, 409)
        self.assertIn(b"User already exists", response.data)

    @patch('app.users_collection')
    def test_signup_short_password(self, mock_users_collection):
        # Mock the users_collection to simulate no user with this username
        mock_users_collection.find_one.return_value = None

        # Attempt to sign up with a short password
        response = self.client.post('/signup', data={
            "username": "newuser",
            "password": "short",
            "Mobile": "1234567890",
            "Name": "New User",
            "Address": "456 New St"
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Password is too short", response.data)

    @patch('app.users_collection')
    def test_login_success(self, mock_users_collection):
        # Prepare a hashed password
        password = bcrypt.hashpw("password123456".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        # Mock the users_collection to return a user document with a hashed password
        mock_users_collection.find_one.return_value = {
            "username": "testuser",
            "password": password
        }

        # Attempt to log in with correct credentials
        response = self.client.post('/login', data={
            "username": "testuser",
            "password": "password123456"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"access_token", response.data)

    @patch('app.users_collection')
    def test_login_invalid_credentials(self, mock_users_collection):
        # Mock the users_collection to simulate a non-existent user
        mock_users_collection.find_one.return_value = None

        # Attempt to log in with incorrect credentials
        response = self.client.post('/login', data={
            "username": "nonexistentuser",
            "password": "wrongpassword"
        })
        self.assertEqual(response.status_code, 401)
        self.assertIn(b"Invalid username or password", response.data)

    def test_home_page(self):
        # Test if the home page loads successfully
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome to the Home Page", response.data)

if __name__ == '__main__':
    unittest.main()
