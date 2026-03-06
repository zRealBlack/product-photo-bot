"""
setup_dropbox.py — Run this ONCE locally to get your permanent Dropbox refresh token.

Steps:
1. Open your Dropbox app at https://www.dropbox.com/developers/apps
2. Find your App key and App secret
3. Run: python setup_dropbox.py
4. Follow the instructions to get your DROPBOX_REFRESH_TOKEN
5. Add the 3 variables to Railway:
   DROPBOX_APP_KEY, DROPBOX_APP_SECRET, DROPBOX_REFRESH_TOKEN
"""
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect

print("=" * 60)
print("Dropbox OAuth2 Setup — get your permanent refresh token")
print("=" * 60)

APP_KEY    = input("Enter your Dropbox App Key:    ").strip()
APP_SECRET = input("Enter your Dropbox App Secret: ").strip()

auth_flow = DropboxOAuth2FlowNoRedirect(
    APP_KEY,
    APP_SECRET,
    token_access_type="offline",   # <-- this gives a refresh token that never expires
)

authorize_url = auth_flow.start()
print("\nStep 1: Go to this URL in your browser:")
print(f"\n  {authorize_url}\n")
print("Step 2: Click 'Allow', then copy the authorization code shown.")

auth_code = input("Step 3: Paste the authorization code here: ").strip()

oauth_result = auth_flow.finish(auth_code)

print("\n" + "=" * 60)
print("SUCCESS! Add these 3 variables to Railway:")
print("=" * 60)
print(f"DROPBOX_APP_KEY      = {APP_KEY}")
print(f"DROPBOX_APP_SECRET   = {APP_SECRET}")
print(f"DROPBOX_REFRESH_TOKEN = {oauth_result.refresh_token}")
print("=" * 60)
print("\nThis refresh token never expires. Keep it secret!")
