"""Scrape images from the web asynchronously."""
import asyncio
import datetime as dt
import random
from os.path import basename
from pathlib import Path
from typing import Optional, Dict, List, Any

import aiofiles
import regex
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from pip._vendor.urllib3.util import url
from tqdm import tqdm

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1 Safari/605.1.15",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
    "Content-Length": "0",
    "TE": "Trailers",
}
IMAGE_DIR = Path(__file__).parent.parent.joinpath("data")


class GoogleImagesScraper:
    """Scrape images from Google Image Search.

    Args:
        query (str): Search query.
        num_results (int): Number of images to download.
    """

    base_request_params = {
        "url": "https://www.google.com/search",
        "headers": HEADERS,
    }

    image_urls_regex = regex.compile(
        r"(https://[a-zA-Z0-9/_.-]+[.](?:jpg|jpeg|png|svg|gif|tiff))"
    )

    def __init__(self, query: str, num_results: int):
        self.query = query.strip()
        self.image_dir = IMAGE_DIR.joinpath(self.query.replace(" ", "-"))
        if not self.image_dir.exists():
            self.image_dir.mkdir(parents=True)
        self.num_results = num_results
        self.results = []

    @staticmethod
    def _filter_image_urls(url: str):
        if "gstatic" in url:
            return False
        return True

    @staticmethod
    def _get_session_params():
        timeout = ClientTimeout(total=60)
        connector = TCPConnector(use_dns_cache=False, ssl=False, limit=5)
        return {"timeout": timeout, "connector": connector}

    def _get_request_params(self):
        url_params = {"q": self.query, "tbm": "isch"}
        request_params = {**self.base_request_params, "params": url_params}
        return request_params

    async def _fetch_request(self, request_data: Dict[str, Any], return_format="raw"):
        async with ClientSession(**self._get_session_params(), loop=loop) as session:
            async with session.get(**request_data) as response:
                if return_format == "raw":
                    return await response.read()
                elif return_format == "html":
                    return await response.text()
                else:
                    raise TypeError("please enter a valid return format ('raw' or 'html')")

    async def _fetch_image_urls(self):
        html = await self._fetch_request(self._get_request_params(), return_format="html")
        image_urls = self.image_urls_regex.findall(html)
        image_urls = list(filter(self._filter_image_urls, image_urls))
        return image_urls

    async def _fetch_image(self, image_data: Dict[str, Any]):
        request_params = {"url": image_data["image_url"]}
        async with aiofiles.open(self.image_dir.joinpath(image_data["image_filename"]).as_posix(), "wb") as image_file:
            await image_file.write(await self._fetch_request(request_params))

    async def _get_image_data(self, url: str):
        datetime = dt.datetime.utcnow()
        filename = basename(url)
        image = dict(
            date=datetime.date(),
            time=datetime.time(),
            type="image",
            query=self.query,
            scraper=str(__class__.__name__),
            image_url=url,
            image_filename=filename,
            image_format=filename.split(".")[-1],
        )
        return image

    async def fetch(self):
        """Main function to run the scraper."""
        image_urls = await self._fetch_image_urls()
        loop_range = (
            self.num_results if self.num_results <= len(image_urls) else len(image_urls)
        )
        with tqdm(total=loop_range) as progress_bar:
            for _ in range(loop_range):
                image_url = image_urls.pop(image_urls.index(random.choice(image_urls)))
                image_data = await self._get_image_data(image_url)
                await self._fetch_image(image_data)
                progress_bar.update()


class GoogleImagesReverseScraper(GoogleImagesScraper):
    """Scrape images similar to a source image using Google Images reverse search."""

    base_request_params = {
        "url": "https://www.google.com/searchbyimage",
        "headers": HEADERS,
    }

    def _get_request_params(self):
        url_params = {
            "image_url": self.query,
            "encoded_image": "",
            "image_content": "",
            "filename": "",
            "hl": "en",
        }
        request_params = {**self.base_request_params, "params": url_params}
        return request_params


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", nargs=1, type=str, required=True)
    parser.add_argument("--num", nargs=1, type=int, required=False, default=100)
    args = parser.parse_args()
    scraper = GoogleImagesScraper(str(args.query.pop()), int(args.num.pop()))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(scraper.fetch())
    loop.close()
