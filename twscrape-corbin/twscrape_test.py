import asyncio
from twscrape import API, gather
from twscrape.logger import set_log_level

async def main():
    api = API()  # or API("path-to.db") – default is `accounts.db`

    # ADD ACCOUNTS (for CLI usage see next readme section)

    # Option 1. Adding account with cookies (more stable)
    cookies = {
        "__cf_bm": "raQnDpArIKTD2bt_thRLoGo6PbeePb_GugKBJplHaDM-1776452584.0366037-1.0.1.1-9Welifqi9xOesMyOqdurtP30GQhzaoFFjjrU_gyjwpafDCCt43lRML5T9qTNq.1sGkIdGH_MB.TJqar5Y04gaPJH2B4CMCnXLGCrAWAnLojeiXGSDPuThCV7AgYe.5Jn",
        "__cuid": "8ed00907590e4d2f8da6a9faa12ccc47",
        "_twitter_sess": "BAh7BiIKZmxhc2hJQzonQWN0aW9uQ29udHJvbGxlcjo6Rmxhc2g6OkZsYXNo%0ASGFzaHsABjoKQHVzZWR7AA%3D%3D--1164b91ac812d853b877e93ddb612b7471bebc74",
        "auth_token": "3b17b91b8e399a9fd0e2e10fc52f039f8a1f77bb",
        "ct0": "f968c1ab998dd607d0baf231464f01f7675cc7e19c5f5812e13f1af202f7b66d511ab0f4df3cfbdb1b70ec73c4cbb5ab906f49579cdfd40ef7c5b4d4a492c7be27084dca6a10436027a75f1f86578e41",
        "gt": "2045208905148494252",
        "guest_id": "v1:176992521667345536",
        "guest_id_ads": "v1:176992521667345536",
        "guest_id_marketing": "v1:176992521667345536",
        "kdt": "YHOEn8AKQRaShpIXb819k2cqkK3161JqUuGNbmGP",
        "lang": "en",
        "personalization_id": "\"v1_LHTt1ixCW7g5YCEoH9pX8Q==\"",
        "twid": "u=2045210232721145856"
    }

    cookies=";".join([f"{cookies[c]}={c}" for c in cookies.keys()])
    print(cookies)
    await api.pool.add_account("nibroc680061", "Y9&8wLaoTq", "xaccount@nibroc.net", "mail_pass3", cookies=cookies)

    # Option2. Adding account with login / password (less stable)
    # email login / password required to receive the verification code via IMAP protocol
    # (not all email providers are supported, e.g. ProtonMail)
    #await api.pool.login_all() # try to login to receive account cookies

    # API USAGE

    # search (latest tab)
    await gather(api.search("elon musk", limit=20))  # list[Tweet]
    # change search tab (product), can be: Top, Latest (default), Media
    await gather(api.search("elon musk", limit=20, kv={"product": "Top"}))

    # tweet info
    tweet_id = 20
    await api.tweet_details(tweet_id)  # Tweet
    await gather(api.retweeters(tweet_id, limit=20))  # list[User]

    # Note: this method have small pagination from X side, like 5 tweets per query
    await gather(api.tweet_replies(tweet_id, limit=20))  # list[Tweet]

    # get user by login
    user_login = "xdevelopers"
    await api.user_by_login(user_login)  # User

    # user info
    user_id = 2244994945
    await api.user_by_id(user_id)  # User
    await gather(api.following(user_id, limit=20))  # list[User]
    await gather(api.followers(user_id, limit=20))  # list[User]
    await gather(api.verified_followers(user_id, limit=20))  # list[User]
    await gather(api.subscriptions(user_id, limit=20))  # list[User]
    await gather(api.user_tweets(user_id, limit=20))  # list[Tweet]
    await gather(api.user_tweets_and_replies(user_id, limit=20))  # list[Tweet]
    await gather(api.user_media(user_id, limit=20))  # list[Tweet]

    # list info
    await gather(api.list_timeline(list_id=123456789))

    # trends
    await gather(api.trends("news"))  # list[Trend]
    await gather(api.trends("sport"))  # list[Trend]
    await gather(api.trends("VGltZWxpbmU6DAC2CwABAAAACHRyZW5kaW5nAAA"))  # list[Trend]

    # NOTE 1: gather is a helper function to receive all data as list, FOR can be used as well:
    async for tweet in api.search("elon musk"):
        print(tweet.id, tweet.user.username, tweet.rawContent)  # tweet is `Tweet` object

    # NOTE 2: all methods have `raw` version (returns `httpx.Response` object):
    async for rep in api.search_raw("elon musk"):
        print(rep.status_code, rep.json())  # rep is `httpx.Response` object

    # change log level, default info
    set_log_level("DEBUG")

    # Tweet & User model can be converted to regular dict or json, e.g.:
    doc = await api.user_by_id(user_id)  # User
    doc.dict()  # -> python dict
    doc.json()  # -> json string

if __name__ == "__main__":
    asyncio.run(main())