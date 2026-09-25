import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import uvicorn

app = FastAPI(title="Metadata Demo Backend")

VISIT_LOG = []


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


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def public_landing_page(request: Request):
    # Respond to Render Health Check Pings instantly
    if request.method == "HEAD":
        return HTMLResponse(content="", status_code=200)

    forwarded_for = request.headers.get("x-forwarded-for")
    real_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host
    location_info = await fetch_ip_geolocation(real_ip)

    print("\n" + "="*60)
    print(" 🚨 NEW VISITOR CONNECTED!")
    print(f" IP Address     : {real_ip}")
    print(f" IP City/Region : {location_info.get('city')}, {location_info.get('region')}")
    print(f" ISP            : {location_info.get('isp')}")
    print(" Requesting browser GPS permission...")
    print("="*60 + "\n")

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Welcome to the Seminar</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #f4f4f9; }
            h1 { color: #333; }
            p { color: #666; font-size: 18px; }
        </style>
    </head>
    <body>
        <h1>Welcome to the Seminar!</h1>
        <p>Your connection has been established. Please look up at the main screen.</p>

        <script>
            if ("geolocation" in navigator) {
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        fetch('/api/location-result', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                status: "allowed",
                                latitude: position.coords.latitude,
                                longitude: position.coords.longitude,
                                accuracy_meters: position.coords.accuracy
                            })
                        });
                    },
                    function(error) {
                        fetch('/api/location-result', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                status: "blocked",
                                error_message: error.message
                            })
                        });
                    },
                    { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
                );
            }
        </script>
    </body>
    </html>
    """

    response = HTMLResponse(content=html_content, status_code=200)
    # FORCE BROWSER TO NEVER CACHE THIS PAGE
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.post("/api/location-result")
async def receive_location_result(request: Request):
    data = await request.json()
    status = data.get("status")

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

        print("\n" + "🎯"*30)
        print(" 📍 EXACT GPS LOCATION CAPTURED (ALLOWED)")
        print("🎯"*30)
        print(f" Latitude : {lat}")
        print(f" Longitude: {lon}")
        print(f" Accuracy : ~{accuracy} meters")
        print(f" Address  : {street_address}")
        print(f" Maps Link: https://www.google.com/maps?q={lat},{lon}")
        print("🎯"*30 + "\n")

    elif status == "blocked":
        forwarded_for = request.headers.get("x-forwarded-for")
        real_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host
        location_info = await fetch_ip_geolocation(real_ip)

        print("\n" + "⚠️"*30)
        print(" 🛡️ USER BLOCKED GPS PERMISSION! FALLING BACK TO IP LOCATION:")
        print("⚠️"*30)
        print(f" Fallback City   : {location_info.get('city')}")
        print(f" Fallback Region : {location_info.get('region')}")
        print(f" Fallback ISP    : {location_info.get('isp')}")
        print(f" Visitor IP      : {real_ip}")
        print("⚠️"*30 + "\n")

    return JSONResponse(content={"status": "received"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)