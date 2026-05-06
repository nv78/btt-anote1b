from flask import Blueprint, Response, current_app, request, jsonify, redirect

from shared import *

bp = Blueprint("auth", __name__)
app = bp

@bp.get("/public/auth/google/start")
def google_oauth_start():
    """Begin Google OAuth (requires ``GOOGLE_CLIENT_ID`` and Authlib)."""
    if _OAUTH is None:
        return jsonify({"success": False, "error": "OAuth not configured"}), 501
    # Prefer deriving redirect_uri from this request so localhost vs 127.0.0.1 matches Google Console.
    # Optional LEADERBOARD_OAUTH_PUBLIC_BASE_URL=https://api.example.com when TLS terminates at proxy (wrong Host in Flask).
    public_base = os.getenv("LEADERBOARD_OAUTH_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public_base:
        redirect_uri = public_base + "/public/auth/google/callback"
    else:
        redirect_uri = request.url_root.rstrip("/") + "/public/auth/google/callback"
    logger.info("google_oauth_start", extra={"redirect_uri": redirect_uri})
    return _OAUTH.google.authorize_redirect(redirect_uri)


@bp.get("/public/auth/google/callback")
def google_oauth_callback():
    """OAuth callback: mint HS256 JWT (``LEADERBOARD_JWT_SECRET``) and redirect to the SPA."""
    if _OAUTH is None:
        return jsonify({"success": False, "error": "OAuth not configured"}), 501
    secret = os.getenv("LEADERBOARD_JWT_SECRET", "").strip()
    if not secret:
        return jsonify({"success": False, "error": "LEADERBOARD_JWT_SECRET required for OAuth login"}), 500
    try:
        token = _OAUTH.google.authorize_access_token()
    except Exception as e:
        logger.warning("google_oauth_failed", extra={"error": str(e)})
        return jsonify({"success": False, "error": "OAuth authorization failed"}), 400
    try:
        ui = token.get("userinfo")
        if not ui:
            resp = _OAUTH.google.get("https://www.googleapis.com/oauth2/v3/userinfo", token=token)
            ui = resp.json()
        sub = (ui.get("email") or ui.get("sub") or "").strip()
    except Exception as e:
        logger.warning("google_userinfo_failed", extra={"error": str(e)})
        return jsonify({"success": False, "error": "Could not read Google profile"}), 400
    if not sub:
        return jsonify({"success": False, "error": "No user identifier from Google"}), 400
    try:
        import jwt as pyjwt

        body = {
            "sub": sub[:255],
            "exp": int((utc_now() + timedelta(hours=24)).timestamp()),
        }
        jwt_token = pyjwt.encode(body, secret, algorithm="HS256")
        if isinstance(jwt_token, bytes):
            jwt_token = jwt_token.decode("ascii")
    except Exception as e:
        logger.exception("jwt_issue_failed", extra={"error": str(e)})
        return jsonify({"success": False, "error": "Token issue failed"}), 500
    front = os.getenv("LEADERBOARD_FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return redirect(f"{front}/oauth/callback#access_token={quote(jwt_token, safe='')}")
