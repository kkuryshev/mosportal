from mosportal.account import Account
import logging
from datetime import datetime
import re
from time import sleep

logger = logging.getLogger(__name__)


class EpdException(BaseException):
    pass


class EpdNotExist(EpdException):
    pass


class Epd(Account):
    def get(self, **kwargs) -> set:
        month = kwargs.get('month', datetime.now().month)
        year = kwargs.get('year', datetime.now().year)

        response = self.session.get('https://www.mos.ru/pgu/ru/application/guis/-47/?onsite_from=popular')
        resp = re.search(r'name="uniqueFormHash"\svalue="(.*?)">', str(response.content))
        if not resp:
            raise EpdException(
                'не удалось получить хеш формы, необходмый для получения ЕПД'
            )

        form_hash = resp.group(1)

        response = self.session.post(
            url='https://www.mos.ru/pgu/ru/application/guis/-47/',
            data={
                'action': 'send',
                'field[new_epd_month][month]': month,
                'field[new_epd_month][year]': year,
                'field[new_epd_type]': '1',
                'field[new_flat]': self.flat,
                'field[new_payer_code]': self.paycode,
                'form_id': '-47',
                'org_id': 'guis',
                'send_from_step': '1',
                'step': '1',
                'uniqueFormHash': form_hash
            })
        if 'app_id' not in response:
            raise EpdException(
                'ошибка получения данных заявки для получения ЕПД'
            )

        app_id = response['app_id']

        sleep(4)  # TODO костыль, но без этого почему-то не отрабатвают сервисы с стороны портала

        data_json = self.session.post(
            url='https://www.mos.ru/pgu/ru/application/guis/-47/',
            data={
                'ajaxAction': 'give_data',
                'ajaxModule': 'GuisEPD',
                'app_id': app_id
            })
        data = data_json.get('data', None)
        if not data:
            raise EpdException(
                'данные от мос. портала не получены'
            )
        if 'requested_data' not in data:
            status_info = data.get('status_info', None)
            if status_info:
                raise EpdNotExist(
                    f'{status_info.get("status_title", "")} {data.get("extra_info", {}).get("value", "")}'
                )
            else:
                raise EpdException(str(data))

        try:
            need_to_pay = data['requested_data']['total']
            pdf_guid = data['files']['file_info']['file_url']
        except KeyError as e:
            raise EpdException(f'ошибка получения данных {e}')

        logger.debug('запрашиваем файл ЕПД')
        r = self.session.get(
            f'https://report.mos.ru/epd/epd.pdf?file_guid={pdf_guid}',
            stream=True
        )
        try:
            return need_to_pay, r.content, 'EPD_%04d_%02d.pdf' % (year, month)
        except BaseException as e:
            raise EpdException(f'ошибка извлечения данных pdf {e}')
