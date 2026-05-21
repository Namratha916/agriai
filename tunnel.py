from pyngrok import ngrok
import subprocess

url = ngrok.connect(5000)
print("Share this link:", url)
input("Press enter to stop the tunnel...")