import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exception import GetStatusException, SendMessageError
load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler('logfile.log', maxBytes=50000000, backupCount=5)
    ]
)

logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def get_api_answer(timestamp):
    """Выполняет запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}

    try:
        homework_statuses = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except requests.exceptions.RequestException as error:
        error_message = f'Ошибка при запросе к API: {error}'
        logging.error(error_message)

    status_code = homework_statuses.status_code
    if status_code != HTTPStatus.OK:
        raise GetStatusException(
            f'"{ENDPOINT}" - недоступен. Код ответа API: {status_code}'
        )

    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if response is None:
        logger.error('API вернул неверный ответ')
        raise TypeError('API вернул неверный ответ')
    elif 'homeworks' not in response:
        logger.error('API вернул ответ без списка домашних работ')
        raise TypeError('API вернул ответ без списка домашних работ')
    elif not isinstance(response['homeworks'], list):
        logger.error('API вернул список неправильного формата')
        raise TypeError('API вернул список неправильного формата')
    elif len(response['homeworks']) == 0:
        logger.debug('API вернул пустой список домашних работ')
        return False
    return True


def parse_status(homeworks):
    """Извлекает статус работы из информации о конкретной домашней работе."""
    if 'homework_name' not in homeworks:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')


    homework_name = homeworks.get('homework_name')
    homework_status = homeworks.get('status')

    if homework_status not in HOMEWORK_VERDICTS.keys():
        message = 'Недокументированный статус домашней работы'
        logging.error(message)
        raise KeyError(message)

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступ к переменным окружения, необходимых для работы бота."""
    tokens = [
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID),
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
    ]
    for token, value in tokens:
        if value is None:
            logger.critical(f'{token} переменная недоступна.')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug(f'Бот отправил сообщение {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        error_message = f'Ошибка при отправке сообщения: {error}'
        logging.error(error_message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    logger.debug(f'Старт работы бота {timestamp}')
    while True:
        logger.debug(f'Старт новой этерации {timestamp}')
        try:
            response = get_api_answer(timestamp)
            if check_response(response):
                for homework in response['homeworks']:
                    status = parse_status(homework)
                    if status:
                        send_message(bot, status)
                timestamp = response.get('current_date')
            else:
                logger.debug('статус работы не обновился')
        except Exception as e:
            logger.error(f'ошибка: {str(e)}')
            send_message(bot, f'Произошла ошибка: {str(e)}')
        time.sleep(RETRY_PERIOD)




if __name__ == '__main__':
    main()
