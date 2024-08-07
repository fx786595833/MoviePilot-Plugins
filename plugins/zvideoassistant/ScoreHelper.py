from app.log import logger
from app.utils.http import RequestUtils


class ScoreHelper:

    def __init__(self, apikey: str):
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
        self.headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4,en-GB;q=0.2,zh-TW;q=0.2',
            'Connection': 'keep-alive',
        }
        self.apikey = apikey

    def get_douban_score(self, douban_id: str = None, title: str = None) -> float | None:
        data = {"apikey": self.apikey}

        response = RequestUtils(headers=self.headers).post_res(
            url=f"https://api.douban.com/v2/movie/subject/{douban_id}",
            json=data
        )

        if not response.status_code == 200:
            logger.debug(f"获取豆瓣评分失败,code={response.status_code},title={title},douban_id={douban_id}")
            return None

        json = response.json()
        if json and json['rating'] and json['rating']['average']:
            score = json['rating']['average']
            return float(score)
        else:
            logger.error(f"获取豆瓣评分失败,api接口返回结构解析失败,json={json}")
        return None
