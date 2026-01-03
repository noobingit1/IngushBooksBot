import config
import telebot
import json
import os
import logging
import sys 


BOOKS_DATABASE_FILE = 'books.json'
BOOKS_FOLDER = '.'

# Расширенная настройка логирования для вывода в консоль и файл
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout), # Логи в консоль
        logging.FileHandler("bot.log", encoding="utf-8") # Логи в файл
    ]
)

bot = telebot.TeleBot(config.TOKEN) 

def load_books_data():
    if not os.path.exists(BOOKS_DATABASE_FILE):
        logging.critical(f"Ошибка: Файл каталога книг '{BOOKS_DATABASE_FILE}' не найден. Создайте его!")
        sys.exit(1) # Критическая ошибка, завершаем выполнение
    try:
        with open(BOOKS_DATABASE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, list): # Проверка на корректный формат
                logging.critical(f"Ошибка: Файл '{BOOKS_DATABASE_FILE}' содержит некорректный формат. Ожидается список книг.")
                sys.exit(1)
            return data
    except json.JSONDecodeError as e:
        logging.critical(f"Ошибка при чтении JSON файла '{BOOKS_DATABASE_FILE}': {e}. Проверьте синтаксис JSON.")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"Неизвестная ошибка при загрузке книг: {e}")
        sys.exit(1)

library = load_books_data()
logging.info(f"Загружено {len(library)} книг в каталог.")

bot.current_search_results = {} # Инициализация словаря для результатов поиска

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """Марша доагӀалда шо!  ⛰️

Для поиска книг введите название произведения или имя автора. Если доступны разные языковые версии, будут отправлены обе. Я всегда готов помочь вам найти то, что ищете. 

ГӀоза дешалда оаш! 📖
"""
    bot.reply_to(message, welcome_text) # <-- Добавлена эта строка для отправки сообщения!
    logging.info(f"Отправлено приветствие пользователю {message.from_user.id}.")


@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_query = message.text.lower().strip()
    chat_id = message.chat.id
    
    if chat_id in bot.current_search_results:
        del bot.current_search_results[chat_id] # Очищаем старые результаты поиска

    found_books = []
    for book in library:
        # Использование .get() для безопасности, если ключи 'title' или 'author' отсутствуют
        title = book.get('title', '').lower()
        author = book.get('author', '').lower()
        
        if user_query in title or user_query in author:
            found_books.append(book)

    if found_books:
        if len(found_books) > 1:
            response_text = "Найдено несколько книг по вашему запросу:\n"
            for i, book in enumerate(found_books):
                response_text += f"{i+1}. {book.get('title', 'Без названия')} ({book.get('author', 'Неизвестен')})\n"
            response_text += "\nНапиши номер книги, которую хочешь получить."
            
            bot.current_search_results[chat_id] = found_books
            bot.reply_to(message, response_text)
            logging.info(f"Пользователь {chat_id} получил список из {len(found_books)} книг по запросу '{user_query}'.")
        else:
            book_to_send = found_books[0]
            send_book_file(chat_id, book_to_send)
            logging.info(f"Пользователю {chat_id} отправлена книга '{book_to_send.get('title')}' по запросу '{user_query}'.")
    else:
        bot.reply_to(message, "Извини, такой книги не найдено. Попробуй другое название или автора.")
        logging.info(f"Для пользователя {chat_id} не найдено книг по запросу '{user_query}'."
        )

def send_book_file(chat_id, book_data):
    # Использование .get() для безопасности
    filename_in_json = book_data.get('filename')
    title = book_data.get('title', 'Книга без названия')
    author = book_data.get('author', 'Неизвестный автор')

    if not filename_in_json:
        logging.error(f"В данных книги '{title}' отсутствует поле 'filename'.")
        bot.send_message(chat_id, f"Ошибка: В базе данных отсутствует информация о файле для книги '{title}'. Пожалуйста, сообщите администратору.")
        return

    file_path = os.path.join(BOOKS_FOLDER, filename_in_json)
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'rb') as doc:
                bot.send_document(chat_id, doc, caption=f"Вот твоя книга: {title} ({author})")
            logging.info(f"Файл '{filename_in_json}' успешно отправлен пользователю {chat_id}.")
        except telebot.apihelper.ApiTelegramException as e: # Специфическая ошибка API Telegram
            logging.error(f"Ошибка API Telegram при отправке файла '{file_path}' пользователю {chat_id}: {e}")
            bot.send_message(chat_id, "Произошла ошибка при отправке книги через Telegram. Возможно, файл слишком большой или возникла временная проблема.")
        except Exception as e:
            logging.error(f"Неизвестная ошибка при отправке файла '{file_path}': {e}")
            bot.send_message(chat_id, "Произошла ошибка при отправке книги. Пожалуйста, попробуй позже.")
    else:
        logging.error(f"Файл '{file_path}' не найден на сервере (указан в books.json, но отсутствует).")
        bot.send_message(chat_id, f"Ошибка: файл книги '{title}' не найден. Пожалуйста, сообщите администратору.")

# bot.current_search_results = {} # Эту строку перенес выше к другим инициализациям

@bot.message_handler(func=lambda message: message.text.isdigit() and message.chat.id in bot.current_search_results)
def choose_book_by_number(message):
    chat_id = message.chat.id
    try:
        choice_index = int(message.text) - 1
        results = bot.current_search_results.get(chat_id) # Использование .get()

        if results and 0 <= choice_index < len(results):
            book_to_send = results[choice_index]
            send_book_file(chat_id, book_to_send)
            del bot.current_search_results[chat_id]
            logging.info(f"Пользователь {chat_id} выбрал книгу по номеру {message.text}: '{book_to_send.get('title')}'.")
        else:
            bot.reply_to(message, "Неверный номер. Пожалуйста, выбери номер из предложенного списка.")
            logging.warning(f"Пользователь {chat_id} ввел неверный номер выбора книги: {message.text}.")
    except Exception as e:
        logging.error(f"Произошла ошибка при обработке выбора книги для пользователя {chat_id}: {e}")
        bot.reply_to(message, "Что-то пошло не так при выборе книги. Пожалуйста, попробуй ещё раз.")

logging.info("Бот запущен и готов к работе...")
try:
    bot.polling(none_stop=True, interval=0, timeout=30) # Увеличен timeout
except KeyboardInterrupt:
    logging.info("Бот остановлен пользователем (Ctrl+C).")
except telebot.apihelper.ApiTelegramException as e: # Обработка ошибок API Telegram
    logging.critical(f"Бот завершил работу из-за ошибки Telegram API: {e}. Возможно, токен недействителен или проблема с сетью.")
    sys.exit(1)
except Exception as e:
    logging.critical(f"Бот завершил работу с критической ошибкой: {e}")
    sys.exit(1)
