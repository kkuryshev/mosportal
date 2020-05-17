import logging
from requests import Session as ReqSession
from requests.utils import dict_from_cookiejar,cookiejar_from_dict
from requests.exceptions import BaseHTTPError
from json import JSONDecodeError
import json
import re
from os.path import join,exists


logger = logging.getLogger(__name__)


class SessionException(BaseException):
    pass


class InvalidSession(SessionException):
    pass


class Session(ReqSession):
    def __init__(self, login, password,**kwargs):
        self.login = login
        self.password = password
        self.cookie_save_path = kwargs.get('cookie_save_path',None)
        self.token = None
        self.id_profile = None
        
        super(Session, self).__init__()

    def __establish(self) -> None:
        try:
            if self.authenticated():
                return
            session = super(Session, self)
            logger.debug('попытка чистой авторизации (без сохраненных куки)...')
            resp = session. get('https://www.mos.ru/api/acs/v1/login?back_url=https%3A%2F%2Fwww.mos.ru%2F')
            js = re.search(r'<script charset=\"utf-8\" src=\"(.+?)\"><\/script>', str(resp.content)).group(1)
            resp = session.get(f'https://login.mos.ru{js}')
            js = re.search(r'COORDS:\"/(.+?)\"', str(resp.content)).group(1)
            session.post(f'https://login.mos.ru/{js}')
            resp = session.post(
                url="https://login.mos.ru/sps/login/methods/password",
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Referer": "https://login.mos.ru/sps/login/methods/password",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Host": "login.mos.ru",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:65.0) Gecko/20100101 Firefox/65.0",
                    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
                    "Upgrade-Insecure-Requests": "1",
                },
                data={
                    "login": self.login,
                    "password": self.password,
                },
                allow_redirects=False
            )
            session.get(
                resp.headers.get('location'),
                headers={
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "same-site",
                    "sec-fetch-user": "?1",
                    "Upgrade-Insecure-Requests": "1"
                }
            )
            self.__save()
        except BaseHTTPError as e:
            raise SessionException(f'ошибка авторизации на портале Москвы: {e}')

    def post(self, url, data=None, **kwargs):
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

        try:
            return resp.json()
        except JSONDecodeError as e:
            raise SessionException(f'получен не корректный ответ от портала {e}')

    def get(self, url, **kwargs):
        for item in range(2):
            resp = super(Session, self).get(url,**kwargs)
            if resp.status_code == 200 and 'login' not in resp.url:
                return resp

            self.__establish()

        raise SessionException('ошибка выполнения запроса')

    def authenticated(self):
        if not self.__load():
            return

        response = super(Session, self).get(
            'https://www.mos.ru/api/oauth20/v1/frontend/json/ru/process/enter?redirect='
            'https://www.mos.ru/services/catalog/popular/'
        )
        if response.status_code != 200:
            return
        if not response.headers.get('x-session-fingerprint',None):
            return

        return True

    @property
    def cookiejar_file(self):
        if not self.cookie_save_path:
            return
        return join(self.cookie_save_path,'.mosportal_cookie')

    def __save(self):
        if not self.cookiejar_file:
            return
        try:
            with open(self.cookiejar_file,'w') as f:
                f.write(json.dumps(dict_from_cookiejar(self.cookies)))
        except (FileNotFoundError,JSONDecodeError) as e:
            raise SessionException(f'ошибка сохранения данных сессии на диск {e}')

    def __load(self):
        if not self.cookiejar_file:
            return

        if not exists(self.cookiejar_file):
            return

        try:
            with open(self.cookiejar_file, 'r') as f:
                self.cookies = cookiejar_from_dict(json.loads(f.read()))
        except (FileExistsError,JSONDecodeError) as e:
            raise SessionException(f'ошибка чтения файла с данными сессии {e}')
        return True
