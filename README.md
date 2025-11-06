**Chats older than 1 day are deleted from mongoDB**
**Backend locally hosted hai jabtak mera laptop on rahega tabtak chalega**
**auth token sign in ke baad hi jayega**

run locally

multilingual:
uvicorn main:app --host 0.0.0.0 --port 8082 --reload   

ssh -o StrictHostKeyChecking=no -R falcon-chatbot:80:localhost:8000 serveo.net

pull changes- (go in project directory main folder)
git pull origin main
sudo systemctl restart falcon-chatbot

(venv) ubuntu@ip-172-31-28-160:/var/www/chemfalcon-chatbot$  sudo nano /etc/systemd/system/falcon-chatbot.service
 /etc/systemd/system/falcon-chatbot.service
code:
[Unit]
Description=Falcon Chatbot FastAPI Application
After=network.target
[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/var/www/chemfalcon-chatbot
Environment=PATH=/var/www/chemfalcon-chatbot/venv/bin
ExecStart=/var/www/falcon_chatbot/venv/bin/uvicorn main:app --host 0.0.0.0 --port 6000
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
nginx config:
server {
    listen 6001;
    server_name 107.20.145.214;
    # Proxy API routes
    location /api/ {
        proxy_pass http://127.0.0.1:6000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    # Proxy root endpoint
    location / {
        proxy_pass http://127.0.0.1:6000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
restart command:
sudo nginx -t
sudo systemctl restart nginx

test- 14 kg at 2433 per kg price, deliver by 2025-12-13 in Jerry can to the buyer factory, paid by LC, phone - 8876798676
**Changes**
Separate Caching (Done in mongoDB)
phonenumber verification using python library

Done: sample ka unit same rahega but minquantity kitna bhi low ho sakta hai
