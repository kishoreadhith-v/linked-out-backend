import requests
import json
import time
import unittest
from datetime import datetime, timedelta

class TestAPI(unittest.TestCase):
    BASE_URL = "http://localhost:8888"
    HEADERS = {"Content-Type": "application/json"}
    
    @classmethod
    def setUpClass(cls):
        """Set up test data before running tests"""
        cls.test_user = {
            "username": f"testuser_{int(time.time())}",
            "email": f"test_{int(time.time())}@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        cls.test_url = "https://example.com"
        cls.token = None

    def test_1_registration(self):
        """Test user registration"""
        print("\nTesting Registration...")
        response = requests.post(
            f"{self.BASE_URL}/api/register",
            json=self.test_user,
            headers=self.HEADERS
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("user_id", response.json())
        print("✓ Registration successful")

    def test_2_login(self):
        """Test user login"""
        print("\nTesting Login...")
        response = requests.post(
            f"{self.BASE_URL}/api/login",
            json={
                "email": self.test_user["email"],
                "password": self.test_user["password"]
            },
            headers=self.HEADERS
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())
        self.token = response.json()["token"]
        print("✓ Login successful")

    def test_3_add_url(self):
        """Test adding a URL"""
        print("\nTesting Add URL...")
        headers = {**self.HEADERS, "Authorization": f"Bearer {self.token}"}
        
        # Test successful URL addition
        response = requests.post(
            f"{self.BASE_URL}/api/urls",
            json={"url": self.test_url},
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "URL added successfully")
        print("✓ URL addition successful")

        # Test invalid URL
        response = requests.post(
            f"{self.BASE_URL}/api/urls",
            json={"url": "not-a-url"},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        print("✓ Invalid URL test successful")

        # Test missing URL
        response = requests.post(
            f"{self.BASE_URL}/api/urls",
            json={},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        print("✓ Missing URL test successful")

    def test_4_list_urls(self):
        """Test listing URLs"""
        print("\nTesting List URLs...")
        headers = {**self.HEADERS, "Authorization": f"Bearer {self.token}"}
        
        response = requests.get(
            f"{self.BASE_URL}/api/urls",
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        print("✓ URL listing successful")

    def test_5_search_urls(self):
        """Test searching URLs"""
        print("\nTesting Search URLs...")
        headers = {**self.HEADERS, "Authorization": f"Bearer {self.token}"}
        
        # Test basic search
        response = requests.get(
            f"{self.BASE_URL}/api/search?q=example",
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        print("✓ Basic search successful")

        # Test empty search
        response = requests.get(
            f"{self.BASE_URL}/api/search",
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        print("✓ Empty search successful")

    def test_6_delete_url(self):
        """Test deleting a URL"""
        print("\nTesting Delete URL...")
        headers = {**self.HEADERS, "Authorization": f"Bearer {self.token}"}
        
        # Test successful deletion
        response = requests.delete(
            f"{self.BASE_URL}/api/urls/{self.test_url}",
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "URL deleted successfully")
        print("✓ URL deletion successful")

        # Test deleting non-existent URL
        response = requests.delete(
            f"{self.BASE_URL}/api/urls/https://nonexistent.com",
            headers=headers
        )
        self.assertEqual(response.status_code, 404)
        print("✓ Non-existent URL deletion test successful")

    def test_7_error_handling(self):
        """Test error handling"""
        print("\nTesting Error Handling...")
        
        # Test invalid token
        headers = {**self.HEADERS, "Authorization": "Bearer invalid_token"}
        response = requests.get(
            f"{self.BASE_URL}/api/urls",
            headers=headers
        )
        self.assertEqual(response.status_code, 401)
        print("✓ Invalid token test successful")

        # Test missing authorization
        response = requests.get(
            f"{self.BASE_URL}/api/urls",
            headers=self.HEADERS
        )
        self.assertEqual(response.status_code, 401)
        print("✓ Missing authorization test successful")

        # Test malformed JSON
        headers = {**self.HEADERS, "Authorization": f"Bearer {self.token}"}
        response = requests.post(
            f"{self.BASE_URL}/api/urls",
            data="invalid json",
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        print("✓ Malformed JSON test successful")

def run_tests():
    """Run the test suite with detailed output"""
    print("Starting API Tests...")
    print("=" * 50)
    
    # Create a test suite
    suite = unittest.TestSuite()
    
    # Add tests in order
    suite.addTest(TestAPI('test_1_registration'))
    suite.addTest(TestAPI('test_2_login'))
    suite.addTest(TestAPI('test_3_add_url'))
    suite.addTest(TestAPI('test_4_list_urls'))
    suite.addTest(TestAPI('test_5_search_urls'))
    suite.addTest(TestAPI('test_6_delete_url'))
    suite.addTest(TestAPI('test_7_error_handling'))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 50)
    print(f"Tests completed. {result.testsRun} tests run.")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    run_tests() 