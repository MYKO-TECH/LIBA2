import asyncio
import os
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import Application

from . import config
from .web_server import create_web_app
from .handlers import get_handlers

logger = logging.getLogger(__name__)

class ACTBot:
    def __init__(self):
        # Build the Telegram application
        self.app = Application.builder().token(config.settings.TELEGRAM_TOKEN).build()
        self.web_app = None
        self._setup_handlers()

    def _setup_handlers(self):
        """Attach all command / message handlers."""
        handlers = get_handlers()
        for handler in handlers:
            self.app.add_handler(handler)

    async def setup_webhook(self):
        """Register the webhook with Telegram."""
        webhook_url = f"{os.getenv('WEBHOOK_URL')}/webhook"

        await self.app.bot.set_webhook(
            url=webhook_url,
            secret_token=config.WEBHOOK_SECRET,
            allowed_updates=Update.ALL_TYPES,  # receive every update type
            drop_pending_updates=True          # clear old updates on restart
        )
        logger.info(f"Webhook configured for {webhook_url}")

    async def run(self):
        """Start the bot, web server, and keep everything running."""
        async with self.app:
            # ----- changed line: pass bot and app to create_web_app -----
            self.web_app = create_web_app(self.app.bot, self.app)

            runner = web.AppRunner(self.web_app)
            await runner.setup()

            # Start web server
            site = web.TCPSite(
                runner,
                host='0.0.0.0',
                port=config.WEB_PORT,
            )
            await site.start()
            logger.info(f"Web server started on port {config.WEB_PORT}")

            # Configure Telegram webhook
            await self.setup_webhook()

            # Start Telegram polling loop
            await self.app.start()

            try:
                # Keep the program alive
                while True:
                    await asyncio.sleep(3600)  # sleep for 1 hour
            except asyncio.CancelledError:
                logger.info("Shutdown signal received")
            finally:
                await self.shutdown(runner)

    async def shutdown(self, runner):
        """Graceful shutdown of services."""
        logger.info("Starting graceful shutdown...")
        await self.app.stop()
        await runner.cleanup()
        logger.info("Services stopped successfully")

async def main():
    bot = ACTBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown successfully")
    except Exception as e:
        logger.error(f"Critical error occurred: {str(e)}")
        raise
