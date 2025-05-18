from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'
]

def main():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=57475)
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    print("token.json created successfully!")

if __name__ == '__main__':
    main()
