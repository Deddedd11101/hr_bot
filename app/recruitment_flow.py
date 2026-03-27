from typing import List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


RECRUITMENT_FLOW_KEY = "recruitment_hiring"

CALLBACK_CONSENT_YES = "recruitment:consent:yes"
CALLBACK_CONSENT_NO = "recruitment:consent:no"

STATUS_WAIT_CONSENT = "recruitment_wait_consent"
STATUS_WAIT_FULL_NAME = "recruitment_wait_full_name"
STATUS_DECLINED = "recruitment_declined"
STATUS_WAIT_POSITION = "recruitment_wait_position"
STATUS_WAIT_RESUME = "recruitment_wait_resume"
STATUS_WAIT_SALARY = "recruitment_wait_salary"
STATUS_PRIMARY_DONE = "recruitment_primary_done"

CALLBACK_ROLE_DESIGNER = "recruitment:role:designer"
CALLBACK_ROLE_PM = "recruitment:role:pm"
CALLBACK_ROLE_ANALYST = "recruitment:role:analyst"

CONSENT_MESSAGE = (
    "Привет! Я HR‑бот. Я создал черновик вашей карточки в админке и привязал этот Telegram. "
    "HR может отредактировать данные и при необходимости привязать вас к существующей карточке.\n\n"
    "Чтобы начать наше сотрудничество, нам нужно твоё согласие на обработку персональных данных.\n"
    "Мы используем их исключительно в рамках процесса подбора"
)
CONSENT_DECLINED_MESSAGE = "Принято. Без согласия на обработку персональных данных мы завершаем сценарий."
ASK_FULL_NAME_MESSAGE = "Отлично! Подскажи, пожалуйста, свое полное ФИО."
ASK_POSITION_MESSAGE = "На какую должность ты рассматриваешься?"
ASK_RESUME_MESSAGE = "Пришли, пожалуйста, своё резюме файлом (PDF / DOC / DOCX)."
ASK_SALARY_MESSAGE = "Какой уровень дохода для тебя комфортен? Можешь указать диапазон."
PRIMARY_DONE_MESSAGE = (
    "Спасибо! Мы получили первичные данные.\n"
    "Дальше HR проверит информацию и вернётся к тебе со следующим шагом."
)


def _keyboard_from_options(options: List[str], callbacks: List[str]) -> InlineKeyboardMarkup:
    rows = []
    for idx, label in enumerate(options):
        callback = callbacks[idx] if idx < len(callbacks) else callbacks[-1]
        rows.append([InlineKeyboardButton(text=label, callback_data=callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def recruitment_consent_keyboard(options: Optional[List[str]] = None) -> InlineKeyboardMarkup:
    options = options or ["Да, согласен", "Нет"]
    if len(options) < 2:
        options = ["Да, согласен", "Нет"]
    return _keyboard_from_options(options[:2], [CALLBACK_CONSENT_YES, CALLBACK_CONSENT_NO])


def recruitment_role_keyboard(options: Optional[List[str]] = None) -> InlineKeyboardMarkup:
    options = options or ["Дизайнер", "Project manager", "Аналитик"]
    if len(options) < 3:
        options = ["Дизайнер", "Project manager", "Аналитик"]
    return _keyboard_from_options(
        options[:3],
        [CALLBACK_ROLE_DESIGNER, CALLBACK_ROLE_PM, CALLBACK_ROLE_ANALYST],
    )
