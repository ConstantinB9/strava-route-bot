import asyncio
import cgi
import logging
import pathlib
import re
import time
from dataclasses import dataclass

import toml as toml
from stravalib import Client
from stravaweblib import WebClient, DataFormat
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    CommandHandler,
    filters,
)

cfg_file = pathlib.Path(__name__).parent / "config.toml"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)
cfg_file = pathlib.Path(__name__).parent / 'config.toml'

@dataclass
class _Config:
    email: str
    password: str
    client_id: int
    client_secret: str
    access_token: str
    refresh_token: str
    expires_at: int
    telegram_api_token: str
    jwt: str

    def save(self):
        toml.dump({"Config": self.__dict__}, cfg_file.open("w"))


cfg_data = toml.load(cfg_file.open("r"))
Config = _Config(**cfg_data["Config"])

share_regex = r"https:\/\/strava.app.link\/(\w+)"
route_regex = r"https:\/\/www\.strava\.com\/routes\/(\d+)"
activity_regex = r"https:\/\/www\.strava\.com\/activities\/(\d+)"



class _RouteFetcher(WebClient):
    def __init__(self):
        if time.time() > Config.expires_at:
            client = Client(access_token=Config.access_token)
            refresh_response = client.refresh_access_token(
                client_id=int(Config.client_id),
                client_secret=Config.client_secret,
                refresh_token=Config.refresh_token,
            )
            Config.access_token = refresh_response["access_token"]
            Config.refresh_token = refresh_response["refresh_token"]
            Config.expires_at = refresh_response["expires_at"]

        try:
            super().__init__(
                access_token=Config.access_token,
                jwt=Config.jwt,
                email=Config.email,
                password=Config.password,
            )
        except ValueError as e:
            logger.warn(str(e))
            logger.info("JWT Expired, Fallback to email & password login")
            super().__init__(
                access_token=Config.access_token,
                email=Config.email,
                password=Config.password,
            )

        Config.jwt = self.jwt
        Config.save()

    async def download_route(self, route_id) -> pathlib.Path:
        resp = self._session.get(
            f"https://www.strava.com/routes/{route_id}/export_gpx", stream=True
        )
        if resp.status_code != 200:
            raise RuntimeError("Download Error")

        content_disposition = resp.headers.get("content-disposition", "")
        filename = cgi.parse_header(content_disposition)[1].get("filename")
        if filename is None:
            raise RuntimeError("Route could not be downloaded")
        with pathlib.Path(filename).open("wb+") as f:
            for chunk in resp.iter_content(chunk_size=16384):
                f.write(chunk)
        return pathlib.Path(filename)

    async def download_activity(self, activity_id) -> pathlib.Path:
        filename, data = self.get_activity_data(
            activity_id=activity_id, fmt=DataFormat.GPX
        )
        filename = pathlib.Path(filename)
        with filename.open("wb+") as f:
            for chunk in data:
                f.write(chunk)
        return filename
    
    async def download_from_share_link(self, share_id) -> pathlib.Path:
        resp = self._session.get(f"https://strava.app.link/{share_id}")
        routes = set(re.findall(route_regex, resp.content.decode()))
        return await self.download_route(routes.pop())


RouteFetcher = _RouteFetcher()


async def download_route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text

    downloads = []
    if not any(re.match(regex,  message) for regex in (share_regex, route_regex, activity_regex)):
        await update.message.reply_text("I did not find a link to a route or activity in your message.\n Check out \\start to learn more on how I work.")
        return
    
    msg_processing = asyncio.create_task(update.message.reply_text("Downloading..."))

    try:
        downloads += await asyncio.gather(
            *[
                RouteFetcher.download_from_share_link(link_id)
                for link_id in re.findall(share_regex, message)
            ]
        )
        downloads += await asyncio.gather(
            *[
                RouteFetcher.download_route(route_id)
                for route_id in re.findall(route_regex, message)
            ]
        )
        downloads += await asyncio.gather(
            *[
                RouteFetcher.download_activity(route_id)
                for route_id in re.findall(activity_regex, message)
            ]
        )
            
    except RuntimeError:
        await update.message.reply_text("Download Failed. Maybe the route or activity is not public?")
        if not downloads:
            msg = await msg_processing
            await msg.delete()
            return
    msg = await msg_processing
    delete_task = asyncio.create_task(msg.delete())
    await asyncio.gather(
        *[
            context.bot.send_document(update.message.chat_id, d.open("rb"))
            for d in downloads
        ]
    )
    map(lambda d: d.unlink(), downloads)
    await delete_task


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
    """
Hello 👋!
You can send me a link to a Strava route or activity and I will try to download the .gpx file for you.
As of right now I can only access public routes and activities so make sure that the link is for a public route / activity which any Strava user can see.
"""
    )


if __name__ == "__main__":
    app = ApplicationBuilder().token(Config.telegram_api_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, download_route))

    app.run_polling()
