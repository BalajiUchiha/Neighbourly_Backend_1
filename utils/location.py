import httpx

async def reverse_geocode(latitude: float, longitude: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "format": "json",
                    "addressdetails": 1
                },
                headers={"User-Agent": "Neighbourly-App/1.0"}
            )
            data = response.json()
            address = data.get("address", {})

            # area_name fallback chain
            area_name = (
                address.get("suburb") or
                address.get("neighbourhood") or
                address.get("village") or
                address.get("hamlet") or
                address.get("town") or
                address.get("county") or
                ""
            )

            # city fallback chain
            city = (
                address.get("city") or
                address.get("town") or
                address.get("county") or
                ""
            )

            # state
            state = address.get("state") or ""

            # district fallback chain
            district = (
                address.get("county") or
                address.get("state_district") or
                address.get("district") or
                state
            )

            # if area_name still empty use district
            if not area_name:
                area_name = district

            return {
                "area_name": area_name,
                "city": city,
                "state": state,
                "district": district,
                "location_accuracy": "exact"
            }

    except Exception:
        # Nominatim failed — return empty, frontend shows district dropdown
        return {
            "area_name": "",
            "city": "",
            "state": "",
            "district": "",
            "location_accuracy": "district_level"
        }
