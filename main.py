import asyncio
import cgi
import pathlib
import re
import time
from dataclasses import dataclass

import toml as toml
from stravalib import Client
from stravaweblib import WebClient
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, CommandHandler, \
    filters

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

    def save(self):
        toml.dump({'Config': self.__dict__}, cfg_file.open('w'))


cfg_data = toml.load(cfg_file.open('r'))
Config = _Config(**cfg_data['Config'])


class _RouteFetcher(WebClient):
    def __init__(self):
        if time.time() > Config.expires_at:
            client = Client(access_token = Config.access_token)
            refresh_response = client.refresh_access_token(
                client_id = int(Config.client_id),
                client_secret = Config.client_secret,
                refresh_token = Config.refresh_token,
            )
            Config.access_token = refresh_response['access_token']
            Config.refresh_token = refresh_response['refresh_token']
            Config.expires_at = refresh_response['expires_at']
            Config.save()

        super().__init__(
            access_token = Config.access_token,
            email = Config.email,
            password = Config.password)

    async def download_route(self, route_id):
        resp = self._session.get(f"https://www.strava.com/routes/{route_id}/export_gpx", stream = True)
        if resp.status_code != 200:
            raise RuntimeError("Download Error")

        content_disposition = resp.headers.get('content-disposition', "")
        filename = cgi.parse_header(content_disposition)[1].get('filename')
        if filename is None:
            raise RuntimeError("Route could not be downloaded")
        with pathlib.Path(filename).open("wb+") as f:
            for chunk in resp.iter_content(chunk_size = 16384):
                f.write(chunk)
        return filename


RouteFetcher = _RouteFetcher()


async def download_route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message.text  #
    route_regex = r'https:\/\/www\.strava\.com\/routes\/(\d+)'
    if not re.match(route_regex, message):
        return

    downloads = asyncio.gather(
        *[RouteFetcher.download_route(route_id) for route_id in re.findall(route_regex, message)])

    for download in downloads:
        await update.message.reply_document(document = download)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hi! You can paste any strava route link here, an I'll try to download the gpx "
                                    "for you!")


if __name__ == '__main__':
    app = ApplicationBuilder().token(Config.telegram_api_token).build()

    app.add_handler(MessageHandler(filters.ALL, download_route))
    app.add_handler(CommandHandler('start', start))

    app.run_polling()
