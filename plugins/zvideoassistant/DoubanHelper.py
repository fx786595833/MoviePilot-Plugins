from http.cookies import SimpleCookie

import requests
from app.helper.cookiecloud import CookieCloudHelper
from app.log import logger


class DoubanHelper:

    def __init__(self, user_cookie: str = None):
        if not user_cookie:
            self.cookiecloud = CookieCloudHelper()
            cookie_dict, msg = self.cookiecloud.download()
            if cookie_dict is None:
                logger.error(f"获取cookiecloud数据错误 {msg}")
            self.cookies = cookie_dict.get("douban.com")
        else:
            self.cookies = user_cookie
        self.cookies = {k: v.value for k, v in SimpleCookie(self.cookies).items()}
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.57'
        self.headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.6,en;q=0.4,en-GB;q=0.2,zh-TW;q=0.2',
            'Connection': 'keep-alive',
            'DNT': '1',
            'HOST': 'www.douban.com'
        }

        if self.cookies.get('__utmz'):
            self.cookies.pop("__utmz")

        # 移除用户传进来的comment-key
        if self.cookies.get('ck'):
            self.cookies.pop("ck")

        # 获取最新的ck
        self.set_ck()

        self.ck = self.cookies.get('ck')
        logger.debug(f"ck:{self.ck} cookie:{self.cookies}")

        if not self.cookies:
            logger.error(f"cookie获取为空，请检查插件配置或cookie cloud")
        if not self.ck:
            logger.error(f"请求ck失败，请检查传入的cookie登录状态")

    def set_ck(self):
        self.headers["Cookie"] = ";".join([f"{key}={value}" for key, value in self.cookies.items()])
        response = requests.get("https://www.douban.com/", headers=self.headers)
        ck_str = response.headers.get('Set-Cookie', '')
        logger.debug(ck_str)
        if not ck_str:
            logger.error('获取ck失败，检查豆瓣登录状态')
            self.cookies['ck'] = ''
            return
        cookie_parts = ck_str.split(";")
        ck = cookie_parts[0].split("=")[1].strip()
        logger.debug(ck)
        self.cookies['ck'] = ck

    def set_watching_status(self, subject_id: str, status: str = "do", private: bool = True) -> bool:
        self.headers["Referer"] = f"https://movie.douban.com/subject/{subject_id}/"
        self.headers["Origin"] = "https://movie.douban.com"
        self.headers["Host"] = "movie.douban.com"
        self.headers["Cookie"] = ";".join([f"{key}={value}" for key, value in self.cookies.items()])
        data_json = {
            "ck": self.ck,
            "interest": "do",
            "rating": "",
            "foldcollect": "U",
            "tags": "",
            "comment": ""
        }
        if private:
            data_json["private"] = "on"
        data_json["interest"] = status
        response = requests.post(
            url=f"https://movie.douban.com/j/subject/{subject_id}/interest",
            headers=self.headers,
            data=data_json)
        if not response:
            return False
        if response.status_code == 200:
            # 正常情况 {"r":0}
            ret = response.json().get("r")
            r = False if (isinstance(ret, bool) and ret is False) else True
            if r:
                return True
            # 未开播 {"r": false}
            else:
                logger.error(f"douban_id: {subject_id} 未开播")
                return False
        logger.error(response.text)
        return False
