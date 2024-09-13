# Bobik Telegram Bot

This project allows to interact to bobik with telegram.


# Installation

Tested on simple aws ec2 ubuntu instance.

## Install Bobik
```
cd ~
git clone https://github.com/andrejsstepanovs/bobik.git
# configure config.yaml following bobik docs
```

## Install Telegram Bot
```
cd ~
git clone https://github.com/andrejsstepanovs/bobik-telegram-bot.git
ln -s ../bobik-telegram-bot/task_telegram.py bobik/task_telegram.py
ln -s ../../bobik-telegram-bot/prompts/telegram_markdown.md bobik/prompts/telegram_markdown.md

cd bobik-telegram-bot
# enable pyenv
pip install -r requirements.txt
```


# Supervisor
Supervisor is handling the bot process. It will restart the bot if it crashes.

## Installation
```
sudo apt-get install supervisor
sudo mkdir -p /var/log/supervisor
sudo chown supervisor:supervisor /var/log/supervisor

cp etc/supervisor/conf.d/bobik-telegram-bot.conf /etc/supervisor/conf.d/bobik-telegram-bot.conf
```

## Supervisor Commands
```
sudo supervisorctl start bobik-telegram-bot
sudo supervisorctl stop bobik-telegram-bot
sudo supervisorctl restart bobik-telegram-bot
sudo supervisorctl tail bobik-telegram-bot
```

# Remember functionality
Cronjob crawls user history file (if enabled) and finds relevant short and long term information about the user.
This information is summarized and stored in special prompt that is fed back to the bobik.
This feedback loop will keep user information up to date.

## Setup
enable in `task_telegram.yaml` file for each user:
```
    remember:
        enabled: true
        use_model: sonnet
        use_model_summary: opus
        target: /home/ubuntu/bobik/prompts/user/remember_knowledge.md
```

and configure this target prompt (`remember_knowledge.md`) in bobik user config file. 
