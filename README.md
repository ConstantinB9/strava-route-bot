#  Strava Route Bot for Telegram
## What it does
This Telegram bot is supposed to support peope with strava-route obsessed friends.
If you find yourself in a situation where  friend sends you a strava route for a ride but you prefer to have turn-by-turn navigation you can use this Telegram Bot to download the GPX of the route and import it into your favourite routing app like Komoot.
An online bot can be found here: https://t.me/strava_route_bot 

## Getting Started
### Prerequisites
- `docker` and `docker-compose` installed
- strava account
- strava api access
	- checkout [this tutorial](https://developers.strava.com/docs/getting-started/) on how to register an app and get api access
- Telegram Api Token ([Documentation](https://core.telegram.org/bots))

### Setup

To start up your own bot, you can simply use the `docker-compose.yml` from this project or clone it using
```
git clone https://github.com/ConstantinB9/strava-route-bot.git
```
You will need to setup your own `config.toml` file within the folder of the `docker-compose.yml`
```
[Config]
email =  "your-strava-account@email.com"
password =  "your-top-secret-strava-password"
client_id =  (INT) STRAVA API CLIENT ID
client_secret =  "your strava api client secret"
access_token =  "" 
refresh_token =  "your strava api refresh token"
expires_at =  0 
telegram_api_token =  "YOUR-TELEGRAM-API-TOKEN"
jwt = ""
```

Now you're ready to start. Just run
```
docker-compose up -d
```
