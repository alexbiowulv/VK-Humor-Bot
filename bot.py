import vk_api
from vk_api.upload import VkUpload
import requests
from bs4 import BeautifulSoup
import os
import random
import sys
import time

# Настройки
VK_TOKEN = os.environ.get('VK_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID') # ID группы (число, без минуса)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_vk_session():
    if not VK_TOKEN or not GROUP_ID:
        print("Ошибка: Не заданы переменные окружения VK_TOKEN или GROUP_ID")
        sys.exit(1)
    return vk_api.VkApi(token=VK_TOKEN)

def get_random_joke():
    """
    Парсит случайный анекдот с anekdot.ru
    Возвращает: (текст, вложение)
    """
    try:
        url = 'https://www.anekdot.ru/random/anekdot/'
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        jokes_list = soup.find_all('div', class_='text')
        
        if not jokes_list:
            return None, None
            
        joke_div = random.choice(jokes_list)
        for br in joke_div.find_all("br"):
            br.replace_with("\n")
            
        joke_text = joke_div.get_text().strip()
        return joke_text, None
        
    except Exception as e:
        print(f"Ошибка при получении анекдота: {e}")
        return None, None

def get_random_meme(vk_session):
    """
    Парсит случайный мем с anekdot.ru и загружает его в ВК
    Возвращает: (текст, вложение)
    """
    try:
        url = 'https://www.anekdot.ru/random/mem/'
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        # Ищем картинки внутри блоков
        images = soup.select('div.text img')
        
        if not images:
            return None, None
            
        img_tag = random.choice(images)
        img_url = img_tag.get('src')
        
        # Скачиваем картинку
        if not img_url.startswith('http'):
            img_url = 'https:' + img_url
            
        img_data = requests.get(img_url, headers=HEADERS).content
        filename = 'temp_meme.jpg'
        
        with open(filename, 'wb') as f:
            f.write(img_data)
            
        # Загружаем в ВК
        upload = VkUpload(vk_session)
        photo = upload.photo_wall(photos=filename, group_id=int(GROUP_ID))[0]
        
        attachment = f"photo{photo['owner_id']}_{photo['id']}"
        os.remove(filename) # Удаляем временный файл
        
        return "", attachment
        
    except Exception as e:
        print(f"Ошибка при получении мема: {e}")
        if os.path.exists('temp_meme.jpg'):
            os.remove('temp_meme.jpg')
        return None, None

def get_random_video(vk_session):
    """
    Ищет случайное смешное видео в ВК
    Возвращает: (текст, вложение)
    """
    try:
        vk = vk_session.get_api()
        queries = ["смешное видео", "ржака", "прикол", "funny video", "мем видео"]
        query = random.choice(queries)
        
        # Ищем видео (короткие, по релевантности)
        videos = vk.video.search(q=query, sort=2, filters='short', count=20, adult=0)
        
        if not videos['items']:
            return None, None
            
        video = random.choice(videos['items'])
        attachment = f"video{video['owner_id']}_{video['id']}"
        
        # Получаем заголовок видео как текст поста (опционально)
        title = video.get('title', 'Видео')
        
        return title, attachment
        
    except Exception as e:
        print(f"Ошибка при поиске видео: {e}")
        return None, None

def get_last_post_type(vk_session):
    """
    Определяет тип последнего поста в группе
    Возвращает: 'text', 'photo', 'video' или 'unknown'
    """
    try:
        vk = vk_session.get_api()
        # owner_id для группы с минусом
        owner_id = -int(GROUP_ID)
        
        posts = vk.wall.get(owner_id=owner_id, count=1)
        
        if not posts['items']:
            return 'unknown'
            
        post = posts['items'][0]
        
        if 'attachments' in post:
            att_type = post['attachments'][0]['type']
            if att_type == 'photo':
                return 'photo'
            elif att_type == 'video':
                return 'video'
        
        # Если нет вложений или они другие, считаем текстом (если есть текст)
        return 'text'
        
    except Exception as e:
        print(f"Ошибка при проверке последнего поста: {e}")
        return 'unknown'

def post_to_vk(vk_session, message=None, attachment=None):
    """
    Публикует пост
    """
    try:
        vk = vk_session.get_api()
        owner_id = -int(GROUP_ID)
        
        vk.wall.post(
            owner_id=owner_id,
            message=message,
            attachment=attachment,
            from_group=1
        )
        print(f"Пост успешно опубликован! Тип: {'Вложение' if attachment else 'Текст'}")
        
    except Exception as e:
        print(f"Ошибка публикации в ВК: {e}")
        sys.exit(1)

def main():
    print("Запуск бота...")
    vk_session = get_vk_session()
    
    # Определяем, что постить
    last_type = get_last_post_type(vk_session)
    print(f"Тип последнего поста: {last_type}")
    
    # Логика чередования: Text -> Photo -> Video -> Text ...
    if last_type == 'text':
        target_type = 'photo'
    elif last_type == 'photo':
        target_type = 'video'
    elif last_type == 'video':
        target_type = 'text'
    else:
        target_type = 'text' # По умолчанию
        
    print(f"Выбран тип для публикации: {target_type}")
    
    message, attachment = None, None
    
    # Попытка получить контент выбранного типа
    if target_type == 'photo':
        message, attachment = get_random_meme(vk_session)
        # Если не вышло с мемом, фоллбек на текст
        if not attachment:
            print("Не удалось получить мем, переключаюсь на текст.")
            target_type = 'text'
            
    if target_type == 'video':
        message, attachment = get_random_video(vk_session)
        # Если не вышло с видео, фоллбек на текст
        if not attachment:
            print("Не удалось получить видео, переключаюсь на текст.")
            target_type = 'text'
            
    if target_type == 'text':
        message, attachment = get_random_joke()
        
    if message or attachment:
        post_to_vk(vk_session, message, attachment)
    else:
        print("Не удалось получить контент ни одного типа.")
        sys.exit(1)

if __name__ == "__main__":
    main()
