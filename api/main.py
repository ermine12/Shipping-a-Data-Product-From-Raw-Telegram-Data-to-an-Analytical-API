from fastapi import FastAPI

app = FastAPI(title="Medical Telegram Warehouse API", version="1.0.0")

@app.get("/")

def read_root():

    return {"message": "Welcome to Medical Telegram Warehouse API"}

@app.get("/health")

def health():

    return {"status": "healthy"}