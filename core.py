# core.py

import logging
import random
import json
import os
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

from config import (
    RANKS, ACHIEVEMENT_DAYS, REDEMPTION_TARGET, REDEMPTION_HOURS,
    TRIGGER_SYMBOLS, MOOD_SYMBOLS, TRIGGER_NAMES, MOOD_NAMES,
    get_rank_by_streak, DB_PATH, PICS_PATH, MEMS_PATH
)
from db import (
    get_user, register_user, update_last_activity, add_coins,
    get_streak, increment_streak, update_streak,
    increment_messages_today,
    get_shield_count, is_shield_active, use_shield, set_shield_until, deactivate_shield,
    start_redemption, update_redemption_progress, get_redemption_status,
    complete_redemption, fail_redemption,
    get_top_streak, get_top_messages_today,
    add_reward_history
)

logger = logging.getLogger(__name__)

PHRASES_FILE = "phrases.json"
_phrase_cache = {}
_last_rank_notified = {}


def load_phrases():
    global _phrase_cache
    if not os.path.exists(PHRASES_FILE):
        with open(PHRASES_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        _phrase_cache = {}
        return
    
    try:
        with open(PHRASES_FILE, 'r', encoding='utf-8') as f:
            _phrase_cache = json.load(f)
        logger.info(f"📚 Загружено фраз: {sum(len(v) for v in _phrase_cache.values())}")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки фраз: {e}")
        _phrase_cache = {}


def save_phrases():
    try:
        with open(PHRASES_FILE, 'w', encoding='utf-8') as f:
            json.dump(_phrase_cache, f, ensure_ascii=False, indent=2)
        logger.info("💾 Фразы сохранены")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения фраз: {e}")
        return False


def get_random_phrase(trigger: str, mood: str = None) -> Optional[str]:
    phrases = _phrase_cache.get(trigger, [])
    if not phrases:
        return None
    
    if mood:
        filtered = [p for p in phrases if p.get('mood') == mood]
        if filtered:
            return random.choice(filtered)['text']
    
    return random.choice(phrases)['text']


def get_rank_phrase(rank_name: str) -> Optional[str]:
    phrases = _phrase_cache.get('RANK_UP', [])
    rank_phrases = [p for p in phrases if rank_name.lower() in p['text'].lower()]
    if rank_phrases:
        return random.choice(rank_phrases)['text']
    return None


def get_streak_achievement(day: int) -> Optional[str]:
    phrases = _phrase_cache.get('STREAK_ACHIEVEMENT', [])
    day_phrases = [p for p in phrases if str(day) in p['text']]
    if day_phrases:
        return random.choice(day_phrases)['text']
    return None


def parse_phrase(text: str) -> Optional[Dict]:
    if len(text) < 2:
        return None
    
    trigger_symbol = text[0]
    mood_symbol = text[1]
    
    if trigger_symbol not in TRIGGER_SYMBOLS:
        return None
    if mood_symbol not in MOOD_SYMBOLS:
        return None
    
    phrase_text = text[2:].strip()
    if len(phrase_text) < 3:
        return None
    
    return {
        'trigger': TRIGGER_SYMBOLS[trigger_symbol],
        'mood': MOOD_SYMBOLS[mood_symbol],
        'text': phrase_text
    }


def add_phrase_from_text(text: str) -> Tuple[bool, str, Optional[Dict]]:
    parsed = parse_phrase(text)
    if not parsed:
        return False, "❌ Неверный формат! Используй: !₽ Текст", None
    
    trigger = parsed['trigger']
    mood = parsed['mood']
    phrase_text = parsed['text']
    
    if trigger not in _phrase_cache:
        _phrase_cache[trigger] = []
    
    for p in _phrase_cache[trigger]:
        if p['text'].lower() == phrase_text.lower():
            return False, "⚠️ Такая фраза уже есть!", None
    
    _phrase_cache[trigger].append({'text': phrase_text, 'mood': mood})
    save_phrases()
    
    return True, "✅ Фраза добавлена!", parsed


def delete_phrase(trigger: str, text: str) -> bool:
    if trigger not in _phrase_cache:
        return False
    
    for i, p in enumerate(_phrase_cache[trigger]):
        if p['text'] == text:
            del _phrase_cache[trigger][i]
            save_phrases()
            return True
    return False


def get_all_phrases() -> List[Dict]:
    result = []
    for trigger, phrases in _phrase_cache.items():
        for p in phrases:
            result.append({
                'trigger': trigger,
                'mood': p.get('mood', 'SARCASTIC'),
                'text': p['text']
            })
    return result


def _get_files_in_folder(folder_path: str) -> List[str]:
    if not os.path.exists(folder_path):
        return []
    files = []
    for f in os.listdir(folder_path):
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            files.append(os.path.join(folder_path, f))
    return files


def _get_trigger_code(trigger: str) -> Optional[str]:
    codes = {
        'DAILY_GREETING': 'gre',
        'ONE_DAY_INACTIVE': 'ina',
        'MULTI_DAY_INACTIVE': 'mul',
        'RETURN': 'ret',
        'RANK_UP': 'ran',
        'STREAK_ACHIEVEMENT': 'str'
    }
    return codes.get(trigger)


def _get_mood_code(mood: str) -> Optional[str]:
    codes = {
        'SARCASTIC': 'sar',
        'ANGRY': 'ang',
        'FURIOUS': 'fur'
    }
    return codes.get(mood)


def get_default_mood_for_trigger(trigger: str) -> str:
    defaults = {
        'DAILY_GREETING': 'SARCASTIC',
        'ONE_DAY_INACTIVE': 'ANGRY',
        'MULTI_DAY_INACTIVE': 'FURIOUS',
        'RETURN': 'SARCASTIC',
        'RANK_UP': 'SARCASTIC',
        'STREAK_ACHIEVEMENT': 'SARCASTIC'
    }
    return defaults.get(trigger, 'SARCASTIC')


def get_random_picture(trigger: str, mood: str = None) -> Optional[str]:
    trigger_code = _get_trigger_code(trigger)
    if not trigger_code:
        return None
    
    if not mood:
        mood = get_default_mood_for_trigger(trigger)
    
    mood_code = _get_mood_code(mood)
    if not mood_code:
        return None
    
    folder = f"{PICS_PATH}/{trigger_code}_{mood_code}"
    files = _get_files_in_folder(folder)
    if files:
        return random.choice(files)
    return None


def get_random_meme(trigger: str, mood: str = None) -> Optional[str]:
    trigger_code = _get_trigger_code(trigger)
    if not trigger_code:
        return None
    
    if not mood:
        mood = get_default_mood_for_trigger(trigger)
    
    mood_code = _get_mood_code(mood)
    if not mood_code:
        return None
    
    folder = f"{MEMS_PATH}/{trigger_code}_{mood_code}_mem"
    files = _get_files_in_folder(folder)
    if files:
        return random.choice(files)
    return None


async def process_user_message(user_id: int, chat_id: int) -> Dict:
    global _last_rank_notified
    
    user = await get_user(user_id)
    if not user:
        await register_user(user_id)
        user = await get_user(user_id)
    
    await update_last_activity(user_id)
    await increment_messages_today(user_id)
    
    response_data = {
        'text': None,
        'need_media': False,
        'trigger': None,
        'mood': None,
        'is_meme': False,
        'send_to_dm': False
    }
    
    redemption = await get_redemption_status(user_id)
    if redemption and redemption.get('active', False):
        await update_redemption_progress(user_id)
        progress = redemption['progress'] + 1
        target = redemption['target']
        
        if progress >= target:
            await complete_redemption(user_id)
            response_data['text'] = f"🎉 Ты восстановил стрик в {redemption['streak_to_restore']} дней! 🦊"
            response_data['send_to_dm'] = True
            return response_data
        elif progress % 50 == 0:
            remaining = target - progress
            response_data['text'] = f"📊 {progress}/{target} сообщений до восстановления. Осталось {remaining}!"
            response_data['send_to_dm'] = True
            return response_data
    
    last_activity = user.get('last_activity')
    if last_activity:
        try:
            last_time = datetime.fromisoformat(last_activity)
            hours_since = (datetime.now() - last_time).total_seconds()
            
            if hours_since >= 24:
                if await is_shield_active(user_id):
                    await deactivate_shield(user_id)
                    response_data['text'] = "🛡️ Щит спас стрик! Но он сгорел. Купи новый в /shop."
                    response_data['send_to_dm'] = True
                    return response_data
                else:
                    old_streak = user['streak']
                    await update_streak(user_id, 0)
                    await start_redemption(user_id, old_streak)
                    response_data['text'] = (
                        f"💔 Стрик в {old_streak} дней сброшен.\n\n"
                        f"🔄 **Шанс восстановить!**\n"
                        f"Напиши **{REDEMPTION_TARGET} сообщений** за {REDEMPTION_HOURS} часов!\n\n"
                        f"Прогресс: **/redemption**"
                    )
                    response_data['send_to_dm'] = True
                    return response_data
        except:
            pass
    
    should_increment = False
    messages_today = user.get('messages_today', 0)
    streak_awarded_today = user.get('streak_awarded_today', 0)
    
    if last_activity and streak_awarded_today == 0 and messages_today >= 100:
        should_increment = True
    
    if should_increment:
        new_streak = await increment_streak(user_id)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET streak_awarded_today = 1 WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()
    else:
        new_streak = user['streak']
    
    rank = get_rank_by_streak(new_streak)
    await add_coins(user_id, rank['income'])
    
    current_rank = user.get('rank', 'Без ранга')
    new_rank = get_rank_by_streak(new_streak)
    
    if new_rank['name'] != current_rank and new_rank['name'] != 'Без ранга':
        last_notified = _last_rank_notified.get(user_id)
        if last_notified != new_rank['name']:
            _last_rank_notified[user_id] = new_rank['name']
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET rank = ? WHERE user_id = ?", (new_rank['name'], user_id))
                await db.commit()
            
            phrase = get_rank_phrase(new_rank['name'])
            if phrase:
                response_data['text'] = f"🏆 Поздравляю! Ты достиг ранга {new_rank['name']}!\n\n{phrase}"
            else:
                response_data['text'] = f"🏆 Поздравляю! Ты достиг ранга {new_rank['name']}!"
            response_data['send_to_dm'] = True
            response_data['need_media'] = True
            response_data['trigger'] = 'RANK_UP'
            response_data['mood'] = 'SARCASTIC'
            return response_data
    
    if new_streak in ACHIEVEMENT_DAYS:
        phrase = get_streak_achievement(new_streak)
        if phrase:
            response_data['text'] = f"🎉 {new_streak} дней стрика!\n\n{phrase}"
        else:
            response_data['text'] = f"🎉 Ты достиг {new_streak} дней стрика! 🦊"
        response_data['send_to_dm'] = True
        response_data['need_media'] = True
        response_data['trigger'] = 'STREAK_ACHIEVEMENT'
        response_data['mood'] = 'SARCASTIC'
        return response_data
    
    if should_increment:
        phrase = get_random_phrase('DAILY_GREETING', 'SARCASTIC')
        if phrase:
            response_data['text'] = phrase
            response_data['need_media'] = True
            response_data['trigger'] = 'DAILY_GREETING'
            response_data['mood'] = 'SARCASTIC'
            return response_data
    
    return response_data


async def check_inactive_users() -> List[Dict]:
    from db import get_inactive_users
    
    inactive = await get_inactive_users()
    result = []
    
    for user in inactive:
        if not user.get('last_activity'):
            continue
        
        last_time = datetime.fromisoformat(user['last_activity'])
        seconds_since = (datetime.now() - last_time).total_seconds()
        
        if 24 <= seconds_since < 25:
            result.append({
                'user': user,
                'type': 'first',
                'trigger': 'ONE_DAY_INACTIVE',
                'mood': 'ANGRY'
            })
        elif seconds_since >= 25:
            if random.random() < 0.3:
                trigger = 'MULTI_DAY_INACTIVE' if seconds_since >= 72 else 'ONE_DAY_INACT
