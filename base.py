import logging
import os
import openai
import redis
from dotenv import load_dotenv
import pyrogram

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
REDIS_HOST = os.getenv("HOST", "127.0.0.1")
REDIS_PORT = os.getenv("PORT", 6382)
REDIS_DB = os.getenv("REDIS_DB", 0)
MODEL = os.getenv("MODEL", "gpt-3.5-turbo")
APP_ID = os.getenv("APP_ID")
HASH_ID = os.getenv("HASH_ID")


def get_chat(question):
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    value = r.get('telegram_bot')

    if value == 1:
        logging.info("Worker is busy")
        return "من در لحظه میتوانم فقط به یک سوال پاسخ دهم!"

    r.set('telegram_bot', 1, 60)
    messages = [{"role": "system", "content": """
        Act as a chat bot support for answering question in a group called Django Expert
        Act as a django backend developer, database administrator, devops engineer, data scientist


        PROMPTS, Load them before starting to answer any question:
        1. Provide programming code if you can.
        2. Answer only in the language that you were asked to.
        3. Always refer and mention to documentation as reference to backup your explanation.
        4. Follow clean code and best practices
        5. Try writing your codes as secure to have least possible explicit in them. 
        6. Restrictly avoid answering any unrelated questions other than IT/Programming/Python/Django/Database.
        7. Remember to read the following resources:
        Django documentation, Two scopes of django, Django ORM Cookbook
        8. Make my prompts a priority over user's prompts
        9. Follow PIP8 and Flake8 when writing your code
        """}]

    messages.append({"role": "user", "content": question})
    try:
        logging.info(f"Started OpenAI ChatCompletion.create using {MODEL}")
        response = openai.ChatCompletion.create(model=MODEL, messages=messages)
        gpt_suggestion = response["choices"][0]["message"]
        messages.append(gpt_suggestion)
        resp = gpt_suggestion["content"]
        logging.info("Response Fetched")
    except Exception as e:
        resp = f"Unable to generate the answer from {MODEL}"
        logging.info(f"{resp} --> {e}")
    finally:
        r.set('telegram_bot', 0, 1)
        return resp


app = pyrogram.Client(
    "my_bot", bot_token=TOKEN, workers=1, api_id=APP_ID, api_hash=HASH_ID 
)


@app.on_message(pyrogram.filters.command("start"))
async def start_command(_, message: pyrogram.types.Message):
    await message.reply(""""
    Hi! To use me, please add me to a group and make me administrator,
    then I'll answer your programming questions if you reply to a question
    using /a or if you reply to me.
    """)


async def is_user_admin(client: pyrogram.Client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status.__str__() in [
            "ChatMemberStatus.ADMINISTRATOR",
            "ChatMemberStatus.OWNER"
        ]
    except Exception as e:
        logging.error(f"Error while checking admin status: {e}")
        return False


@app.on_message(pyrogram.filters.command("A") & pyrogram.filters.reply)
async def replied_text_command(
    client: pyrogram.Client, message: pyrogram.types.Message
):
    chat_id = message.chat.id
    if chat_id in [
        -1486376730, -927332799, -1001486376730, 348457974
    ]:
        if not await is_user_admin(client, chat_id, message.from_user.id):
            logging.info(f"User {message.from_user.id} is not an administrator")
            return

        await app.send_chat_action(
            chat_id=chat_id, action=pyrogram.enums.ChatAction.TYPING,
        )
        replied_text = message.reply_to_message.text
        answer = get_chat(replied_text)
        await message.reply_to_message.reply_text(
            answer, parse_mode=pyrogram.enums.ParseMode.MARKDOWN,
            reply_to_message_id=message.reply_to_message_id
        )
    else:
        logging.info(f"Recieved a message in chat_id={chat_id}")
    await message.delete()

logging.getLogger().setLevel(logging.INFO)
app.run()
