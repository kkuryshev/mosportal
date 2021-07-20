import logging
from requests import cookies
from requests import Session as ReqSession
from requests.utils import dict_from_cookiejar, cookiejar_from_dict
from requests.exceptions import BaseHTTPError
from json import JSONDecodeError
import json
import re
from os.path import join, exists
from datetime import datetime
logger = logging.getLogger(__name__)


class SessionException(BaseException):
    pass


class InvalidSession(SessionException):
    pass

class Session(ReqSession):
    def __init__(self, login, password, **kwargs):
        self.login = login
        self.password = password
        self.cookie_save_path = kwargs.get('cookie_save_path', None)
        self.token = None
        self.id_profile = None
        self.__refresh_date = None

        super(Session, self).__init__()

    def __establish(self) -> None:
        try:
            self.cookies.clear()
            session = super(Session, self)
            logger.debug('попытка чистой авторизации (без сохраненных куки)...')
            resp = session.get('https://stats.mos.ru/eds.gif',
                headers = self.__get_header(),
                params = {
                    "eventType":"home_page",
                    "eventDst":"stats",
                    "eventSrc":"mos.ru",
                    "eventObject":{"Главная":{"Поиск":"view"}},
                    "eventTime":datetime.now().microsecond,
                    "mosId":None
                }
            )
            resp = session.get('https://www.mos.ru/api/acs/v1/login?back_url=https%3A%2F%2Fwww.mos.ru%2F',headers=self.__get_header())
            js = re.search(r'<script charset=\"utf-8\" src=\"(.+?)\"><\/script>', str(resp.content)).group(1)
            logger.debug(f'получили код {js}')

            resp = session.get(f'https://login.mos.ru{js}',headers=self.__get_header())
            js = re.search(r'COORDS:\"/(.+?)\"', str(resp.content)).group(1)
            logger.debug(f'получили COORDS {js}')
            #-->

            resp = session.get('https://login.mos.ru/sps/login/methods/password',
                headers=self.__get_header({
                    "referer": "https://login.mos.ru/sps/login/methods/password",
                    "origin":"https://login.mos.ru",
                    "content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "host": "login.mos.ru",
                    "accept":"text/css,*/*;q=0.1",
                })
            )
            csrftokenw = re.search(r"meta name='csrf-token-value' content='(.+?)'\/>", resp.text).group(1)
            cid = re.search(r'session_promise|(\d+)|find',resp.text).group(1)
            
            resp = session.get(f'https://mstat.gosuslugi.ru/oxwdsq?cid={cid}',
                headers=self.__get_header({
                    "referer": "https://login.mos.ru/sps/login/methods/password",
                    "origin":"https://login.mos.ru",
                    "sec-ch-ua":"\"Google Chrome\";v=\"87\", \" Not;A Brand\";v=\"99\", \"Chromium\";v=\"87\"",
                    "sec-ch-ua-mobile":"?0",
                    "Referer":"https://login.mos.ru/",
                    "accept":"text/css,*/*;q=0.1",
                })
            )
            id1,id2,id3 = re.search(r'window\.kfp\.jsonp_oxwdsq\(\{ "id":"(.+?)", "e":"(\d+?)", "t":"(\d+?)"', resp.text).groups()
            cookie = cookies.create_cookie(domain='.mos.ru',name='oyystart',value=f'{id1}_1')
            self.cookies.set_cookie(cookie)
            cookie = cookies.create_cookie(domain='.mos.ru',name='oxxfgh',value=f'{id1}#2#{id2}#{id3}#600000')
            self.cookies.set_cookie(cookie)
            #<---
            session.post(f'https://login.mos.ru/{js}',headers=self.__get_header())

            logger.debug(f'переходим к аутентификации')
            resp = session.post(
                url="https://login.mos.ru/sps/login/methods/password",
                headers=self.__get_header({
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "referer": "https://login.mos.ru/sps/login/methods/password",
                    "origin":"https://login.mos.ru",
                    "content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "host": "login.mos.ru",
                    "accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                }),
                data={
                    "isDelayed":"false",
                    "login": self.login,
                    "password": self.password,
                    "csrftokenw":csrftokenw,
                    "alien":"false"
                },
                allow_redirects=False
            )
            if resp.headers.get('location') == None:
                raise SessionException('аутентификация провалилась, так как УЗ заблокирована')

            logger.debug(f"переходим на адрес, который вернул запрос аутентификации {resp.headers.get('location')}")
            session.get(
                resp.headers.get('location'),
                headers=self.__get_header()
            )

            if not self.authenticated():
                raise SessionException('аутентификация прошла успешно но сессия осталась не валидной')
            self.__refresh_date = datetime.now()
            logger.debug("авторизация на портале Москвы прошла успешно!")
        except BaseException as e:
            raise SessionException(f'ошибка авторизации на портале Москвы: {e}')

    def post(self, url, data=None, **kwargs):
        if not self.__init_est:
            self.__establish()

        resp = None
        for item in range(2):
            resp = super(Session, self).post(
                url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                },
                data=data
            )
            if resp.status_code == 200 and 'login' not in resp.url:
                break

            self.__establish()
        return self.extract_json(resp)

    @staticmethod
    def extract_json(resp):
        try:
            return resp.json()
        except JSONDecodeError as e:
            raise SessionException(f'получен не корректный ответ от портала {e}')

    def get(self, url, **kwargs):
        if not self.__init_est:
            self.__establish()

        for item in range(2):
            resp = super(Session, self).get(url, **kwargs)
            if resp.status_code == 200 and 'login' not in resp.url:
                return resp

            self.__establish()

        raise SessionException('ошибка выполнения запроса')

    def authenticated(self):

        response = super(Session, self).get(
            'https://www.mos.ru/api/oauth20/v1/frontend/json/ru/process/enter?redirect='
            'https://www.mos.ru/services/catalog/popular/'
        )
        if response.status_code != 200:
            return
        if not response.headers.get('x-session-fingerprint', None):
            return

        return True

    @property
    def __init_est(self):
        return self.__refresh_date and (datetime.now() - self.__refresh_date).total_seconds() < 7200


    def __get_header(self,header:dict=None) -> dict:
        if not header: 
            header = {}
        
        header.update({
            "pragma":"no-cache",
            "cache-control":"no-cache",
            "accept-Encoding": "gzip, deflate, br",
            "user-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:65.0) Gecko/20100101 Firefox/65.0",
            "accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
            "Upgrade-Insecure-Requests": "1",
            "sec-fetch-site":"same-origin",
            "sec-fetch-mode":"navigate",
            "sec-fetch-user":"?1",
            "sec-fetch-dest":"document",
        })

        return header
    
    def logout(self):
        self.__refresh_date = None
        resp = super(Session, self).get('https://www.mos.ru/api/acs/v1/logout',
                headers = self.__get_header(),
                params = {
                    "back_url":"https://www.mos.ru/uslugi/",
                }
            )
        print(resp)