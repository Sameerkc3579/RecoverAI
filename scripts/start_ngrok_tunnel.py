import time
import sys
from pyngrok import ngrok, conf
from pyngrok.exception import PyngrokNgrokError

def main():
    print("Starting ngrok tunnel for FastAPI (port 8000)...")
    
    try:
        # Open a HTTP tunnel on the default port 8000
        public_url = ngrok.connect(8000)
    except PyngrokNgrokError as e:
        if "ERR_NGROK_4018" in str(e) or "authentication failed" in str(e):
            print("\n❌ Ngrok requires an authentication token to start.")
            print("To get a free token:")
            print("  1. Sign up at https://dashboard.ngrok.com/signup")
            print("  2. Go to https://dashboard.ngrok.com/get-started/your-authtoken")
            print("  3. Copy your authtoken and paste it below.")
            
            token = input("\nEnter your Ngrok Authtoken: ").strip()
            if not token:
                print("No token provided. Exiting.")
                sys.exit(1)
            
            print("Saving authtoken...")
            ngrok.set_auth_token(token)
            
            print("Retrying connection...")
            try:
                public_url = ngrok.connect(8000)
            except Exception as retry_e:
                print(f"Failed to connect on retry: {retry_e}")
                sys.exit(1)
        else:
            raise e
            
    print("\n" + "="*60)
    print("✅ NGROK TUNNEL IS LIVE!")
    print(f"🔗 Forwarding URL: {public_url.public_url}")
    print("="*60 + "\n")
    print("Your Webhook URL for the Meta Developer Dashboard is:")
    print(f"{public_url.public_url}/api/webhooks/whatsapp\n")
    print("Keep this window open to keep the tunnel alive. Press Ctrl+C to stop.")
    
    try:
        # Block until CTRL-C or some other terminating event
        ngrok_process = ngrok.get_ngrok_process()
        ngrok_process.proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down ngrok tunnel.")

if __name__ == '__main__':
    main()
