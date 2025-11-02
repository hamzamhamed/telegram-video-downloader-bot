from fastapi import FastAPI
app = FastAPI()

@app.post("/webhook")
async def telegram_webhook(update: dict):
    # process the update
    return {"ok": True}
