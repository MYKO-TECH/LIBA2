from aiohttp import web
from .config import settings
from .sessions import redis
import logging
from prometheus_client import generate_latest, Counter, Histogram
import time
from telegram import Update

logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status'])
RESPONSE_TIME = Histogram('http_response_time_seconds', 'Response time histogram')

async def handle_webhook(request: web.Request) -> web.Response:
    """Process Telegram webhook requests"""
    start_time = time.time()
    REQUEST_COUNT.labels('POST', '/webhook', 'received').inc()
    
    try:
        # Verify secret token
        if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != config.WEBHOOK_SECRET:
            REQUEST_COUNT.labels('POST', '/webhook', 'invalid_token').inc()
            return web.Response(status=403)

        # Process update
        data = await request.json()
        update = Update.de_json(data, request.app['bot'])
        await request.app['dispatcher'].process_update(update)
        
        # Log success
        RESPONSE_TIME.observe(time.time() - start_time)
        REQUEST_COUNT.labels('POST', '/webhook', 'success').inc()
        return web.Response(status=200)
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        REQUEST_COUNT.labels('POST', '/webhook', 'error').inc()
        return web.Response(status=500)

async def health_check(request: web.Request) -> web.Response:
    """System health endpoint"""
    checks = {
        "redis": await redis.ping(),
        "status": "ok",
        "version": config.version
    }
    status = 200 if all(checks.values()) else 503
    return web.json_response(checks, status=status)

async def metrics(request: web.Request) -> web.Response:
    """Prometheus metrics endpoint"""
    return web.Response(
        body=generate_latest(),
        content_type='text/plain'
    )

def create_web_app(bot, dispatcher) -> web.Application:
    """Configure web application"""
    app = web.Application()
    app['bot'] = bot
    app['dispatcher'] = dispatcher
    
    app.router.add_post('/webhook', handle_webhook)
    app.router.add_get('/health', health_check)
    app.router.add_get('/metrics', metrics)
    
    # Add startup/cleanup hooks
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    return app

async def on_startup(app: web.Application) -> None:
    """Startup tasks"""
    logger.info("Web server starting...")
    await redis.ping()  # Test Redis connection

async def on_cleanup(app: web.Application) -> None:
    """Cleanup tasks"""
    logger.info("Closing Redis connections...")
    await redis.close()
