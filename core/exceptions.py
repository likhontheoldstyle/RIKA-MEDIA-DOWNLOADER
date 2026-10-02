from core.constants import GENERIC_ERROR


class AppError(Exception):
    status_code = 500
    safe_message = GENERIC_ERROR


class InvalidURL(AppError):
    status_code = 400
    safe_message = "Invalid YouTube URL."


class UnsupportedPlatform(AppError):
    status_code = 400
    safe_message = "Only YouTube URLs are supported."


class APIError(AppError):
    status_code = 502
    safe_message = "Unable to process this video right now."


class MediaNotFound(AppError):
    status_code = 404
    safe_message = "No media found for this video."


class MediaExpired(AppError):
    status_code = 410
    safe_message = "This download link has expired. Please analyze the video again."


class ConversionError(AppError):
    status_code = 500
    safe_message = "MP3 conversion failed. Please try again later."


class ConversionUnavailable(AppError):
    status_code = 503
    safe_message = "MP3 conversion is temporarily unavailable."


class RateLimitExceeded(AppError):
    status_code = 429
    safe_message = "Rate limit exceeded. Please slow down and try again."


class ValidationError(AppError):
    status_code = 400
    safe_message = "Invalid request."
