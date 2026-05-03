from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ecommerce-support-agent is running"}

@app.get("/health")
def health():
    return {"status": "ok"}