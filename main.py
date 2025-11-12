from fastapi import FastAPI
from routes import agent_test, chat
from fastapi.middleware.cors import CORSMiddleware

# Update origins to include your PERMANENT ngrok domain
origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://0.0.0.0:3000",
    "http://localhost:3001",
    "http://0.0.0.0:3001",
    "https://chemfalcon.com/",
    "https://chemfalcon.com",
    "http://107.20.145.214:6001",
]

app = FastAPI(title="Falcon Chatbot API")

# Add CORS middleware FIRST
# Add authentication, Security, Logging and data compression as needed
app.add_middleware( 
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Then include routers defined for testing nd production
app.include_router(chat.router, prefix="/api/chat")
app.include_router(agent_test.router, prefix="/api")

# Health and access check of the base URL
@app.get("/")
async def root():
    return {"message": "ChemFalcon Chatbot Backend Running"}
# agar run button ya python command se chalna hua to for testing purposes
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127..0.0.1", port=8080)