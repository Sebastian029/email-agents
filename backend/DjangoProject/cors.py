class CorsMiddleware:
    """Lightweight CORS for local React dev (no extra dependency)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = self.get_response(request)
        else:
            response = self.get_response(request)

        origin = request.headers.get("Origin", "")
        allowed = ("http://localhost:5173", "http://127.0.0.1:5173")
        if origin in allowed:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, Accept"
            )
            response["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )

        return response
