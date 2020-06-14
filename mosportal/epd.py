from mosportal.account import Account
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EpdException(BaseException):
    pass


class EpdNotExist(EpdException):
    pass


EPD_TYPE = {
    'REGULAR': 'Обычный'
}

PAYMENT_STATUS = {
    'NOT_PAID': 'Не оплачен',
    'PAID': 'Оплачен'
}


class Epd(Account):
    def __init__(self, *args, **kwargs):
        super(Epd, self).__init__(*args, **kwargs)
        self.__info = None

    @property
    def amount(self) -> float:
        """
        сумма оплаты (в прошлых периодах или сколько нужно оплатить
        :return:
        """
        key = 'PaymentAmount' if 'PaymentAmount' in self.__info else 'AccrualAmount'
        value = self.__info.get(key, None)
        return float(value) if value else None

    @property
    def insurance_amount(self) -> float:
        """
        сумма страховки
        :return:
        """
        value = self.__info.get('InsuranceAmmount', None)
        return float(value) if value else None

    @property
    def status(self) -> (str, str):
        """
        Статус оплаты (опачен, не оплачен)
        :return:
        """
        key = self.__info['PaymentStatus']
        return key, PAYMENT_STATUS.get(key, None)

    @property
    def epd_type(self) -> (str, str):
        """
        Тип ЕПД (долговой, регулярный)
        :return:
        """
        key = self.__info['EpdType']
        return key, EPD_TYPE.get(key, None)

    @property
    def penalty(self) -> float:
        """
        Сумма пени
        :return:
        """
        value = self.__info.get('PenaltyAmount', None)
        return float(value) if value else None

    @property
    def period(self) -> str:
        """
        Период, за который получен ЕПД
        :return:
        """
        return self.__info.get('Period', None)

    @property
    def payment_date(self) -> str:
        """
        Дата оплаты
        :return:
        """
        return self.__info.get('PaymentDate', None)

    @property
    def create_date(self) -> datetime:
        """
        Дата формирования ЕПД
        :return:
        """
        date = self.__info.get('CreateDate', None)
        if date:
            return datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f")
        return None

    @property
    def content(self) -> str:
        """
        PDF файл с ЕПД в формате base64
        :return:
        """
        url = f'https://www.mos.ru/pgu/common/ajax/Guis062301/GetEpdPdf' \
            f'?payer_code={self.paycode}&uin={self.__info["Uin"]}'

        response = self.session.extract_json(
            self.session.get(url))

        logger.debug('запрашиваем файл ЕПД')
        epd_data = self.session.get(
            url=response['url'],
            stream=True
        )

        try:
            return epd_data.content
        except BaseException as e:
            raise EpdException(f'ошибка извлечения данных pdf {e}')

    def get(self, **kwargs):
        month = kwargs.get('month', datetime.now().month)
        year = kwargs.get('year', datetime.now().year)

        period = '%02d-%02d-01' % (year, month)

        response = self.session.extract_json(
            self.session.get(
                url=f'https://www.mos.ru/pgu/common/ajax/Guis062301/GetEpdData?payer_code='
                f'{self.paycode}&flat={self.flat}&beginperiod={period}&endperiod={period}&not_paid=false'
            )
        )
        try:
            self.__info = response["EpdList"][0]["Epd"][0]
        except (KeyError, IndexError):
            if 'EpdList' not in response or not len(response["EpdList"]):
                raise EpdException('Ошибка получения ЕПД')
            if 'Epd' not in response["EpdList"][0] or not len(response["EpdList"][0]['Epd']):
                raise EpdNotExist(f'За указанный период ({year}.{month}) ЕПД не сформирован')

        return self
