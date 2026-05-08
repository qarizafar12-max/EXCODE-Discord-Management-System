import requests

def test_login():
    session = requests.Session()
    # Assume the flask server is running from the background command
    resp = session.post('http://localhost:5000/login', data={'username': 'admin', 'password': 'admin_pass'})
    print(f"Status code: {resp.status_code}")
    if 'Invalid username or password' in resp.text:
        print("Login failed! Flash message found in response.")
    else:
        print("Login succeeded! No flash message.")

if __name__ == "__main__":
    test_login()
