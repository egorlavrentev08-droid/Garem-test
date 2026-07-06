import logging
from datetime import datetime
from typing import Optional

from config import ADMIN_IDS

logger = logging.getLogger(__name__)

_test_mode_active = True
_test_start_time = None
TIME_MULTIPLIER = 1


def is_test_mode() -> bool:
    global _test_mode_active
    return _test_mode_active


def enable_test_mode():
    global _test_mode_active, _test_start_time
    _test_mode_active = True
    _test_start_time = datetime.now()
    logger.info("⏱️ ТЕСТОВЫЙ РЕЖИМ ВКЛЮЧЁН")


def disable_test_mode():
    global _test_mode_active, _test_start_time
    _test_mode_active = False
    _test_start_time = None
    logger.info("⏱️ ТЕСТОВЫЙ РЕЖИМ ВЫКЛЮЧЕН")


def get_test_status() -> dict:
    global _test_mode_active, _test_start_time
    return {
        'active': _test_mode_active,
        'started_at': _test_start_time,
        'multiplier': TIME_MULTIPLIER if _test_mode_active else 1
    }


async def cmd_test(message):
    from config import is_admin
    if not is_admin(message.from_user.id):
        await message.answer("❌ Ты не админ!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📝 *Тестовый режим*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "/test on — включить тестовый режим\n"
            "/test off — выключить тестовый режим\n"
            "/test status — статус\n\n"
            f"📊 Текущий статус: {'🟢 ВКЛЮЧЁН' if is_test_mode() else '🔴 ВЫКЛЮЧЕН'}",
            parse_mode='Markdown'
        )
    
    action = args[1].lower()
    
    if action == 'on':
        enable_test_mode()
        await message.answer(
            "⏱️ *Режим тестирования ВКЛЮЧЁН!*\n\n"
            "Теперь бот работает в тестовом режиме.",
            parse_mode='Markdown'
        )
    elif action == 'off':
        disable_test_mode()
        await message.answer(
            "⏱️ *Режим тестирования ВЫКЛЮЧЕН!*",
            parse_mode='Markdown'
        )
    elif action == 'status':
        status = get_test_status()
        await message.answer(
            f"📊 *Статус тестового режима*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Состояние: {'🟢 ВКЛЮЧЁН' if status['active'] else '🔴 ВЫКЛЮЧЕН'}\n"
            f"Множитель: x{status['multiplier']}\n"
            f"Включён: {status['started_at'].strftime('%d.%m.%Y %H:%M:%S') if status['started_at'] else '—'}",
            parse_mode='Markdown'
        )
    else:
        await message.answer("❌ Используй: `/test on`, `/test off` или `/test status`", parse_mode='Markdown')
