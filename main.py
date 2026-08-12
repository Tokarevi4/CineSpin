from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")

if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY is not configured")

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

app = FastAPI(
    title="CineSpin API",
    version="1.0.0",
)


# ============================================================
# CACHE
# ============================================================

CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

CACHE_TTL = 60 * 60 * 24  # 24 часа


# ============================================================
# RATE LIMITING
# ============================================================

RATE_LIMIT = 30          # максимум запросов
RATE_WINDOW = 60         # за 60 секунд

request_history: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(client_ip: str) -> bool:
    """
    Проверяет, не превысил ли IP установленный лимит.

    Возвращает:
        True  - запрос разрешён
        False - лимит превышен
    """

    now = time.time()

    timestamps = request_history[client_ip]

    # Удаляем запросы старше RATE_WINDOW
    while timestamps and now - timestamps[0] > RATE_WINDOW:
        timestamps.popleft()

    # Проверяем лимит
    if len(timestamps) >= RATE_LIMIT:
        return False

    # Запоминаем текущий запрос
    timestamps.append(now)

    return True


# ============================================================
# TMDB
# ============================================================

def search_tmdb_movie(title: str) -> dict[str, Any]:

    params = {
        "api_key": TMDB_API_KEY,
        "query": title,
        "language": "en-US",
        "include_adult": False,
    }

    try:
        response = requests.get(
            TMDB_SEARCH_URL,
            params=params,
            timeout=7,
        )

        response.raise_for_status()

    except requests.Timeout:
        raise HTTPException(
            status_code=504,
            detail="TMDB request timed out",
        )

    except requests.RequestException as exc:
        print(f"TMDB error: {exc}")

        raise HTTPException(
            status_code=502,
            detail="TMDB request failed",
        )

    try:
        data = response.json()

    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="TMDB returned invalid JSON",
        )

    results = data.get("results", [])

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"Movie '{title}' not found",
        )

    movie = results[0]

    poster_path = movie.get("poster_path")

    poster_url = None

    if poster_path:
        poster_url = (
            f"{TMDB_IMAGE_BASE_URL}"
            f"{poster_path}"
        )

    return {
        "id": movie.get("id"),
        "title": movie.get("title"),
        "original_title": movie.get("original_title"),
        "release_date": movie.get("release_date"),
        "poster_url": poster_url,
    }


# ============================================================
# API ENDPOINT
# ============================================================

@app.get("/movie")
def get_movie(
    request: Request,
    title: str = Query(
        ...,
        min_length=1,
        max_length=200,
    ),
):
 
    # --------------------------------------------------------
    # Получаем IP клиента
    # --------------------------------------------------------

    client_ip = request.client.host

    if not client_ip:
        client_ip = "unknown"

    # --------------------------------------------------------
    # Rate limit
    # --------------------------------------------------------

    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many requests. "
                "Please try again later."
            ),
        )

    # --------------------------------------------------------
    # Нормализация названия
    # --------------------------------------------------------

    clean_title = (
        title
        .replace("-", " ")
        .strip()
    )

    if not clean_title:
        raise HTTPException(
            status_code=400,
            detail="Movie title cannot be empty",
        )

    # --------------------------------------------------------
    # Cache
    # --------------------------------------------------------

    cache_key = clean_title.lower()

    cached = CACHE.get(cache_key)

    if cached:
        timestamp, result = cached

        if time.time() - timestamp < CACHE_TTL:
            return result

        del CACHE[cache_key]

    # --------------------------------------------------------
    # TMDB
    # --------------------------------------------------------

    result = search_tmdb_movie(clean_title)

    # --------------------------------------------------------
    # Save to cache
    # --------------------------------------------------------

    CACHE[cache_key] = (
        time.time(),
        result,
    )

    return result