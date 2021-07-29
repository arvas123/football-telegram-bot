import json
import logging
import os
import time as tim
from uuid import uuid4

from fuzzywuzzy import fuzz
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      InlineQueryResultArticle, InputTextMessageContent,
                      ParseMode, Update, replymarkup)
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, ConversationHandler, Filters,
                          InlineQueryHandler, MessageHandler, Updater)
from telegram.utils.helpers import escape_markdown

from fetchdata import *
from keep_alive import keep_alive

logging.basicConfig(filename='log.txt',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
                    )
cnt = 0
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
accepted_full = ['Premier League', 'La Liga', 'Bundesliga',
                 'Ligue Un', "Serie A", "UEFA Champions League", 'FIFA World Cup']
accepted_initials = ['PL',  'PD', 'BL1', 'FL1', "SA",  "CL", "WC"]
accepted_data_full = ['Premier League', 'Primera Division', 'Bundesliga',
                      'Ligue 1', "Serie A", "UEFA Champions League", 'FIFA World Cup']
FIRST, SECOND = range(2)
ONE, TWO, THREE, FOUR = range(4)
STATE = None


def start(update, context):
    '''
    Start by getting teams user wants
    '''
    global cnt
    first_name = update.message.chat.first_name
    # begin by gettin the compeititons they are interested in
    update.message.reply_text(
        f"Hi {first_name}, nice to meet you! You will be prompted to enter the competitions you want")
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data=str(ONE)),
            InlineKeyboardButton("No", callback_data=str(TWO)),
            InlineKeyboardButton("I'm finished", callback_data=str(THREE))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    d = {}
    d[first_name] = {}
    d[first_name]['comps'] = []
    d[first_name]['chatid'] = update.message.chat_id
    d[first_name]['teams'] = []
    json.dump(d, open('data.json', 'w'))
    update.message.reply_text(
        f"Would you like to add {accepted_full[cnt]}", reply_markup=reply_markup)
    return FIRST


def remove_job_if_exists(name: str, context) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def sendreminder(context):
    '''
    send reminder to user
    '''
    job = context.job
    data = job.context
    matchdata = data['match']

    mes = f"{ matchdata['Home'] } VS {matchdata['Away']} \n {'in one hour' if data['state'] else 'happening now'}"
    context.bot.send_message(data['chatid'], text=mes)


def set_update_all(context):
    '''
    set updates when program restarts and continue every day
    '''
    job = context.job
    d = json.load(open('data.json'))
    matches = json.load(open('matches.json'))
    for name in d:
        accepted_comps = list(filter(lambda x: accepted_initials[accepted_data_full.index(
            x)] in d[name]['comps'], accepted_data_full))
        for i in matches:
            if i['competition'] not in accepted_comps:
                continue
            if (i['Home'] not in d[name]['teams']) and (i['Away'] not in d[name]['teams']):
                continue
            data = {'match': i, 'chatid': d[name]['chatid'], 'state': 0}
            i['utcdate'] = datetime.strptime(
                i['utcdate'], '%Y-%m-%dT%H:%M:%SZ')
            diff = (i['utcdate'] - datetime.utcnow()).total_seconds()
            if diff > 0:
                context.job_queue.run_once(
                    sendreminder, i['utcdate'], context=data, name=str(d[name]['chatid']))
            diff2 = (i['utcdate'] - timedelta(hours=1) -
                     datetime.utcnow()).total_seconds()
            if diff2 > 0:
                data['state'] = 1
                context.job_queue.run_once(
                    sendreminder, i['utcdate'] - timedelta(hours=1), context=data, name=str(d[name]['chatid']))


def set_updates(context):
    '''
    set updates after user performs /add or /remove command
    '''
    job = context.job
    update = job.context
    chat_id = update.message.chat_id
    name = update.message.chat.first_name
    d = json.load(open('data.json'))
    comps = d[name]['comps']
    matches = json.load(open('matches.json'))
    job_removed = remove_job_if_exists(str(chat_id), context)
    accepted_comps = list(filter(lambda x: accepted_initials[accepted_data_full.index(
        x)] in d[name]['comps'], accepted_data_full))
    for i in matches:
        if i['competition'] not in accepted_comps:
            continue
        if (i['Home'] not in d[name]['teams']) and (i['Away'] not in d[name]['teams']):
            continue
        data = {'match': i, 'chatid': chat_id, 'state': 0}
        i['utcdate'] = datetime.strptime(i['utcdate'], '%Y-%m-%dT%H:%M:%SZ')
        diff = (i['utcdate'] - datetime.utcnow()).total_seconds()
        if diff > 0:
            context.job_queue.run_once(
                sendreminder, i['utcdate'], context=data, name=str(chat_id))
        diff2 = (i['utcdate'] - timedelta(hours=1) -
                 datetime.utcnow()).total_seconds()
        if diff2 > 0:
            data['state'] = 1
            context.job_queue.run_once(
                sendreminder, i['utcdate'] - timedelta(hours=1), context=data, name=str(chat_id))


def add_comp_list(update, context):
    '''
    add teams to get reminders
    '''
    d = json.load(open('data.json'))
    global cnt
    query = update.callback_query
    name = (query.from_user)['first_name']
    query.answer()
    query.edit_message_text(text=f"Added {accepted_full[cnt]}")
    d[name]['comps'].append(accepted_initials[cnt])
    json.dump(d, open('data.json', 'w'))
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data=str(ONE)),
            InlineKeyboardButton("No", callback_data=str(TWO)),
            InlineKeyboardButton("I'm finished", callback_data=str(THREE))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    cnt += 1
    if cnt >= len(accepted_full):
        return end(update, context)
    query.edit_message_text(
        text=f"Would you like to add {accepted_full[cnt]}", reply_markup=reply_markup)
    return FIRST


def remove_comp_list(update, context):
    '''
    dont add competition
    '''
    global cnt
    query = update.callback_query
    query.answer()
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data=str(ONE)),
            InlineKeyboardButton("No", callback_data=str(TWO)),
            InlineKeyboardButton("I'm finished", callback_data=str(THREE))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    cnt += 1
    if cnt >= len(accepted_full):
        return end(update, context)
    query.edit_message_text(
        text=f"Would you like to add {accepted_full[cnt]}", reply_markup=reply_markup)
    return FIRST


def stop(update, context):
    '''
    stop initial 
    '''
    global cnt
    query = update.callback_query
    query.answer()
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data=str(TWO)),
            InlineKeyboardButton("No", callback_data=str(ONE))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text=f"Are you sure you are done", reply_markup=reply_markup)
    return SECOND


def end(update, context):
    query = update.callback_query
    if cnt < len(accepted_full):
        query.answer()
    query.edit_message_text(text="Thank you for adding your competitons")
    d = json.load(open('data.json'))
    name = query.from_user['first_name']
    final = 'Final competition list\n' + \
        '\n'.join(
            list(map(lambda x: accepted_full[accepted_initials.index(x)], d[name]['comps'])))
    context.bot.send_message(d[name]['chatid'], text=final)
    txt = 'You can now use /add to add competitions.' if len(d[name]['teams']) else 'Your old teams are still saved. You can use /add to add new teams'
    context.bot.send_message(d[name]['chatid'], text=txt)
    return ConversationHandler.END


def resume(update, context):
    query = update.callback_query
    query.answer()
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data=str(ONE)),
            InlineKeyboardButton("No", callback_data=str(TWO)),
            InlineKeyboardButton("I'm finished", callback_data=str(THREE))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text=f"Would you like to add {accepted_full[cnt]}", reply_markup=reply_markup)
    return FIRST

def restart(update, context):
    global cnt
    cnt=0
    update.message.reply_text(
        f"Hi! You will be prompted to enter the competitions you want")
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data=str(ONE)),
            InlineKeyboardButton("No", callback_data=str(TWO)),
            InlineKeyboardButton("I'm finished", callback_data=str(THREE))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"Would you like to add {accepted_full[cnt]}", reply_markup=reply_markup)
    return FIRST
def print_comps(update, context):
    d = json.load(open('data.json'))
    update.message.reply_text(
        '\n'.join(d[update.message.chat.first_name]['comps']))


def inlinequery(update: Update, context: CallbackContext) -> None:
    """Handle the inline query."""
    teams = json.load(open('teams.json'))
    d = json.load(open('data.json'))
    query = update.inline_query.query
    user = update.inline_query.from_user
    chat_id = user['id']
    name = user['first_name']
    results = []
    l = []
    init = []
    idx = 0
    if STATE == 1:
        for i in filter(lambda x: teams[x] in d[name]['comps'], teams.keys()):

            if fuzz.WRatio(i, query) > 75:

                l.append([fuzz.WRatio(i, query), idx])
                init.append(InlineQueryResultArticle(id=str(uuid4()), title=i, input_message_content=InputTextMessageContent(
                    f"*{escape_markdown(i)}*", parse_mode=ParseMode.MARKDOWN)))
                idx += 1
        l.sort(reverse=True)
        results = []
        l = l[:min(len(l), 5)]
        for i in l:
            results.append(init[i[1]])
        update.inline_query.answer(results)
    elif STATE == 2:
        for i in filter(lambda x: x in d[name]['teams'], teams.keys()):
            print(i)
            if fuzz.WRatio(i, query) > 75:

                l.append([fuzz.WRatio(i, query), idx])
                init.append(InlineQueryResultArticle(id=str(uuid4()), title=i, input_message_content=InputTextMessageContent(
                    f"*{escape_markdown(i)}*", parse_mode=ParseMode.MARKDOWN)))
                idx += 1
        l.sort(reverse=True)
        results = []
        l = l[:min(len(l), 5)]
        for i in l:
            results.append(init[i[1]])
        update.inline_query.answer(results)


def error(update, context):
    update.message.reply_text('An error occured')


def show(update, context):
    for i in (context.job_queue.jobs()):
        try:
            matchdata = (i.context['match'])
            mes = f"{ matchdata['Home'] } VS {matchdata['Away']} \n on:{matchdata['date']}"
            update.message.reply_text(mes)
        except Exception:
            continue


def add_teams(update, context):
    global STATE
    STATE = 1
    update.message.reply_text(
        'Add the team names you would like to follow. Reply done when finished. Use @getfootydatabot to get team name suggestions.')


def remove_teams(update, context):
    global STATE
    STATE = 2
    update.message.reply_text(
        'Remove the team names you would like to follow. Reply done when finished. Use @getfootydatabot to get team name suggestions.')


def text(update, context):
    '''
    process team names added
    '''
    global STATE
    user_data = json.load(open('data.json'))
    d = json.load(open('teams.json'))
    if STATE == 1:
        name = (update.message.text)
        if name.lower() == 'done':
            team_str = '\n'.join(
                user_data[update.message.chat.first_name]['teams'])
            update.message.reply_text(f"Team list:\n {team_str}")
            context.job_queue.run_once(
                set_updates, timedelta(seconds=2), context=update)
            STATE = None
            return
        if name in user_data[update.message.chat.first_name]['teams']:
            update.message.reply_text('Team already in list')
        elif name in d.keys():
            user_data[update.message.chat.first_name]['teams'].append(name)
            update.message.reply_text(f'Added {name}')
        else:
            update.message.reply_text('Invalid team name')
        json.dump(user_data, open('data.json', 'w'))
    elif STATE == 2:
        name = (update.message.text)
        if name.lower() == 'done':
            team_str = '\n'.join(
                user_data[update.message.chat.first_name]['teams'])
            update.message.reply_text(f"Team list:\n {team_str}")
            context.job_queue.run_once(
                set_updates, timedelta(seconds=2), context=update)
            STATE = None
            return
        if name in user_data[update.message.chat.first_name]['teams']:
            update.message.reply_text(f'Team {name} removed.')
            user_data[update.message.chat.first_name]['teams'].remove(name)
        elif name in d.keys():
            update.message.reply_text(f'Team {name} has not been added')
        else:
            update.message.reply_text('Invalid team name')
        json.dump(user_data, open('data.json', 'w'))


def main():
    TOKEN = os.environ[__BOTKEY__]
    # create the updater, that will automatically create also a dispatcher and a queue to
    # make them dialoge
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    job = updater.job_queue
    job.run_daily(set_update_all, (datetime.utcnow() +
                  timedelta(seconds=3)).time())
    job.run_repeating(process_matches, timedelta(days=3))
    # add handlers for start and help commands
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('restart', restart)],
        states={
            FIRST: [
                CallbackQueryHandler(
                    add_comp_list, pattern='^' + str(ONE) + '$'),
                CallbackQueryHandler(
                    remove_comp_list, pattern='^' + str(TWO) + '$'),
                CallbackQueryHandler(stop, pattern='^' + str(THREE) + '$')
            ],
            SECOND: [
                CallbackQueryHandler(resume, pattern='^' + str(ONE) + '$'),
                CallbackQueryHandler(end, pattern='^' + str(TWO) + '$'),
            ]
        },
        fallbacks=[CommandHandler('start', start)],
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler("show", print_comps))
    dispatcher.add_handler(CommandHandler("add", add_teams))
    dispatcher.add_handler(CommandHandler("remove", remove_teams))
    dispatcher.add_handler(CommandHandler("jobs", show))
    dispatcher.add_handler(InlineQueryHandler(inlinequery))
    # add an handler for normal text (not commands)
    dispatcher.add_handler(MessageHandler(Filters.text, text))
    updater.start_polling()
    # run the bot until Ctrl-C
    updater.idle()


if __name__ == '__main__':
    # keep_alive()
    main()
